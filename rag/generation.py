"""Answer generation in the background, independent of any HTTP connection.

``ask`` creates the messages and calls :func:`start`; a worker thread then runs
:func:`generate`. The stream endpoint only *follows* the message in the
database (``rag.answer.follow``), so leaving the page, reloading or opening a
second tab never interrupts or duplicates an answer.

While writing, the thread saves the partial text and a heartbeat
(``updated_at``) every ~0.3 s with one conditional UPDATE: if no row matches
``status='streaming'``, the user pressed Stop (or a follower declared the
answer orphaned), and the thread stops. A thread killed by a restart leaves no
heartbeat; followers then mark the answer as interrupted.

Why a thread and not the ``django-tasks`` queue: answers are interactive. The
queue worker polls every ~1 s and runs one task at a time, so a long PDF
ingestion would delay answers; durability is covered by the heartbeat.

No source text, question or answer is ever logged (spec §11).
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import close_old_connections, connections, transaction
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from llm import client
from llm.models import NotebookSettings
from llm.providers import ChatResult, ProviderError

from .citations import validate
from .models import Message, MessageCitation
from .prompt import build_messages, citation_reminder
from .retrieval import retrieve

logger = logging.getLogger('ascendia.rag')

#: The partial answer (and heartbeat) is saved at most every N tokens or T seconds.
SAVE_EVERY_TOKENS = 12
SAVE_EVERY_SECONDS = 0.3

_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


def not_found_text() -> str:
    return _("I couldn't find this in the sources of this notebook.")


def _pool() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=max(1, settings.ASCENDIA_ANSWER_THREADS), thread_name_prefix='ascendia-answer',
            )
        return _executor


def start(message_id: int, language: str) -> None:
    """Generate the answer after the current transaction commits.

    ``ASCENDIA_ANSWER_THREADS = 0`` runs it inline (tests).
    """
    def launch():
        if settings.ASCENDIA_ANSWER_THREADS <= 0:
            generate(message_id, language)
        else:
            _pool().submit(_run_in_thread, message_id, language)

    transaction.on_commit(launch)


def _run_in_thread(message_id: int, language: str) -> None:
    close_old_connections()
    try:
        generate(message_id, language)
    except Exception:  # noqa: BLE001 - last resort: never let a thread die silently
        logger.exception('Answer generation crashed for message %s', message_id)
        _finish(message_id, status=Message.STATUS_ERROR, content=None,
                error=_('Something went wrong while writing this answer. Ask again.'))
    finally:
        connections.close_all()


# --------------------------------------------------------------------------- helpers

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


class _Usage:
    def __init__(self, model: str):
        self.model, self.input_tokens, self.output_tokens, self.latency_ms, self.cost_usd = model, 0, 0, 0, None

    def add(self, result: ChatResult | None) -> None:
        if result is None:
            return
        self.model = result.model or self.model
        self.input_tokens += result.input_tokens
        self.output_tokens += result.output_tokens
        self.latency_ms += result.latency_ms
        if result.cost_usd is not None:
            self.cost_usd = (self.cost_usd or 0.0) + result.cost_usd

    def fields(self) -> dict:
        return {'model': self.model, 'input_tokens': self.input_tokens, 'output_tokens': self.output_tokens,
                'latency_ms': self.latency_ms, 'cost_usd': self.cost_usd}


def _save_partial(message_id: int, text: str) -> bool:
    """Save the text so far + heartbeat. False when the answer is no longer streaming (Stop)."""
    return bool(Message.objects.filter(pk=message_id, status=Message.STATUS_STREAMING).update(
        content=text, updated_at=timezone.now(),
    ))


def _finish(message_id: int, *, status: str, content: str | None, cited=frozenset(), not_found=False,
            error: str = '', usage: _Usage | None = None) -> None:
    """Write the final state, unless the user stopped the answer meanwhile (then keep 'stopped')."""
    fields = {'status': status, 'not_found': not_found, 'error': error[:500], 'updated_at': timezone.now()}
    if content is not None:
        fields['content'] = content
    if usage is not None:
        fields.update(usage.fields())
    with transaction.atomic():
        updated = Message.objects.filter(pk=message_id, status__in=Message.OPEN_STATUSES).update(**fields)
        if not updated and content is not None:
            # Stopped meanwhile: keep the status, store the gated partial text.
            Message.objects.filter(pk=message_id).update(content=content, updated_at=timezone.now())
        citations = MessageCitation.objects.filter(message_id=message_id)
        citations.update(cited=False)
        if cited:
            citations.filter(n__in=list(cited)).update(cited=True)


# --------------------------------------------------------------------------- the pipeline

def generate(message_id: int, language: str | None = None) -> None:
    """Write the answer of a pending assistant message (retrieve → stream → gate → save)."""
    with translation.override(language or settings.LANGUAGE_CODE):
        _generate(message_id)


def _generate(message_id: int) -> None:
    claimed = Message.objects.filter(pk=message_id, status=Message.STATUS_PENDING).update(
        status=Message.STATUS_STREAMING, updated_at=timezone.now(),
    )
    if not claimed:
        return  # already running elsewhere, finished, or abandoned
    message = Message.objects.select_related('conversation__notebook').get(pk=message_id)
    nb_settings, _created = NotebookSettings.objects.get_or_create(notebook=message.conversation.notebook)
    Message.objects.filter(pk=message_id).update(provider=nb_settings.chat_provider, model=nb_settings.chat_model)
    usage = _Usage(nb_settings.chat_model)
    question, history = _question_and_history(message)

    try:
        retrieved = retrieve(nb_settings, question, source_ids=message.source_filter)
    except ProviderError as exc:
        _finish(message_id, status=Message.STATUS_ERROR, content='', error=exc.user_message)
        return
    if not retrieved:
        _finish(message_id, status=Message.STATUS_COMPLETE, content=not_found_text(), not_found=True)
        return

    passages = _snapshot(message, retrieved)
    allowed = {p.n for p in passages}
    prompt = build_messages(nb_settings, question, passages, history)
    parts: list[str] = []
    last_save, unsaved = time.monotonic(), 0
    stopped = False
    try:
        stream = client.stream_chat(nb_settings, prompt)
        for delta in stream:
            parts.append(delta)
            unsaved += 1
            now = time.monotonic()
            if unsaved >= SAVE_EVERY_TOKENS or now - last_save >= SAVE_EVERY_SECONDS:
                if not _save_partial(message_id, ''.join(parts)):
                    stopped = True
                    break
                last_save, unsaved = now, 0
        result = None if stopped else stream.result
    except ProviderError as exc:
        partial = validate(''.join(parts), allowed)
        _finish(message_id, status=Message.STATUS_ERROR, content=partial.text, cited=partial.cited,
                error=exc.user_message, usage=usage)
        return

    text = ''.join(parts)
    if stopped:
        partial = validate(text, allowed)
        _finish(message_id, status=Message.STATUS_STOPPED, content=partial.text, cited=partial.cited, usage=usage)
        return

    usage.add(result)
    gate = validate(text, allowed)
    if not gate.cited:
        # D9: an answer must cite. One non-streamed retry with an explicit reminder.
        try:
            retry = client.chat(nb_settings, prompt + [{'role': 'assistant', 'content': text}, citation_reminder()])
            usage.add(retry)
            gate = validate(retry.text, allowed)
        except ProviderError:
            logger.warning('Citation retry failed for message %s', message_id)
    if gate.cited:
        _finish(message_id, status=Message.STATUS_COMPLETE, content=gate.text, cited=gate.cited, usage=usage)
    else:
        _finish(message_id, status=Message.STATUS_COMPLETE, content=not_found_text(), not_found=True, usage=usage)
