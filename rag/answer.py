"""Grounded answer pipeline, streamed as Server-Sent Events (spec §7.5).

``stream_answer(message)`` is a synchronous generator of SSE strings, so it runs
the same under runserver (WSGI, dev) and uvicorn (ASGI, production):

* ``token`` — a text delta, appended as plain text by the client;
* ``done``  — the final, sanitized HTML (validated citations as chips);
* ``error`` — a safe message; the answer is marked as failed.

Steps: retrieve → (nothing? standard "not found", no LLM call) → snapshot the
passages as citations → stream the answer → gate the citations → if none is
valid, retry once with a reminder → still none? "not found" → persist.
No source text, question or answer is ever logged (spec §11).
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator

from django.db import transaction
from django.utils.translation import gettext as _

from llm import client
from llm.models import NotebookSettings
from llm.providers import ChatResult, ProviderError

from .citations import validate
from .models import Message, MessageCitation
from .prompt import build_messages, citation_reminder
from .render import render_answer
from .retrieval import retrieve

logger = logging.getLogger('ascendia.rag')

#: How often (in tokens) the stream checks whether the user pressed Stop.
STOP_CHECK_EVERY = 20


def not_found_text() -> str:
    return _("I couldn't find this in the sources of this notebook.")


def sse(event: str, data: dict) -> str:
    return f'event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'


def _done(message: Message) -> str:
    return sse('done', {'html': render_answer(message), 'status': message.status, 'not_found': message.not_found})


def _question_and_history(message: Message) -> tuple[str, list[Message]]:
    earlier = list(message.conversation.messages.filter(id__lt=message.id).order_by('created_at', 'id'))
    question_msg = next((m for m in reversed(earlier) if m.role == Message.ROLE_USER), None)
    question = question_msg.content if question_msg else ''
    history = [m for m in earlier if m is not question_msg and m.status == Message.STATUS_COMPLETE]
    return question, history


def _snapshot(message: Message, retrieved) -> list[MessageCitation]:
    citations = [
        MessageCitation(
            message=message, n=i, chunk=r.chunk, source=r.chunk.source, source_title=r.chunk.source.title,
            page=r.chunk.page, section=r.chunk.section, text=r.chunk.text, score=r.score,
        )
        for i, r in enumerate(retrieved, start=1)
    ]
    MessageCitation.objects.bulk_create(citations)
    return citations


def _add_usage(message: Message, result: ChatResult | None) -> None:
    if result is None:
        return
    message.model = result.model or message.model
    message.input_tokens += result.input_tokens
    message.output_tokens += result.output_tokens
    message.latency_ms += result.latency_ms
    if result.cost_usd is not None:
        message.cost_usd = (message.cost_usd or 0.0) + result.cost_usd


def _save(message: Message, *, content: str, status: str, cited=frozenset(), not_found=False, error='') -> None:
    message.content = content
    message.status = status
    message.not_found = not_found
    message.error = error[:500]
    with transaction.atomic():
        message.save()
        message.citations.update(cited=False)
        if cited:
            message.citations.filter(n__in=list(cited)).update(cited=True)


def _stop_requested(message: Message) -> bool:
    return Message.objects.filter(pk=message.pk, status=Message.STATUS_STOPPED).exists()


def stream_answer(message: Message) -> Iterator[str]:
    """Generate (or replay) the answer of an assistant message as SSE events."""
    claimed = Message.objects.filter(pk=message.pk, status=Message.STATUS_PENDING).update(
        status=Message.STATUS_STREAMING,
    )
    if not claimed:  # reconnect after the end, or a second tab: replay, never regenerate
        message.refresh_from_db()
        if message.status == Message.STATUS_ERROR:
            yield sse('error', {'message': message.error})
        elif message.is_open:
            yield sse('error', {'message': _('This answer is already being written in another tab.')})
        else:
            yield _done(message)
        return

    message.status = Message.STATUS_STREAMING
    notebook = message.conversation.notebook
    nb_settings, _created = NotebookSettings.objects.get_or_create(notebook=notebook)
    message.provider = nb_settings.chat_provider
    message.model = nb_settings.chat_model
    question, history = _question_and_history(message)

    try:
        retrieved = retrieve(nb_settings, question, source_ids=message.source_filter)
    except ProviderError as exc:
        _save(message, content='', status=Message.STATUS_ERROR, error=exc.user_message)
        yield sse('error', {'message': exc.user_message})
        return
    if not retrieved:
        _save(message, content=not_found_text(), status=Message.STATUS_COMPLETE, not_found=True)
        yield _done(message)
        return

    passages = _snapshot(message, retrieved)
    allowed = {p.n for p in passages}
    prompt = build_messages(nb_settings, question, passages, history)
    parts: list[str] = []
    stopped = False
    try:
        stream = client.stream_chat(nb_settings, prompt)
        for count, delta in enumerate(stream, start=1):
            parts.append(delta)
            yield sse('token', {'t': delta})
            if count % STOP_CHECK_EVERY == 0 and _stop_requested(message):
                stopped = True
                break
        result = None if stopped else stream.result
    except ProviderError as exc:
        partial = validate(''.join(parts), allowed)
        _save(message, content=partial.text, status=Message.STATUS_ERROR, cited=partial.cited,
              error=exc.user_message)
        yield sse('error', {'message': exc.user_message})
        return
    except GeneratorExit:  # the browser closed the stream (Stop or left the page)
        partial = validate(''.join(parts), allowed)
        _save(message, content=partial.text, status=Message.STATUS_STOPPED, cited=partial.cited)
        raise

    text = ''.join(parts)
    if stopped:
        partial = validate(text, allowed)
        _save(message, content=partial.text, status=Message.STATUS_STOPPED, cited=partial.cited)
        yield _done(message)
        return

    _add_usage(message, result)
    gate = validate(text, allowed)
    if not gate.cited:
        # D9: an answer must cite. One non-streamed retry with an explicit reminder.
        try:
            retry = client.chat(nb_settings, prompt + [{'role': 'assistant', 'content': text}, citation_reminder()])
            _add_usage(message, retry)
            gate = validate(retry.text, allowed)
        except ProviderError:
            logger.warning('Citation retry failed for message %s', message.pk)
    if gate.cited:
        _save(message, content=gate.text, status=Message.STATUS_COMPLETE, cited=gate.cited)
    else:
        _save(message, content=not_found_text(), status=Message.STATUS_COMPLETE, not_found=True)
    yield _done(message)
