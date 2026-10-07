"""Chat of a notebook: ask, stream the answer, stop, open a citation, clear.

All views are scoped to the notebook's owner (spec §11). The answer streams
over Server-Sent Events from a synchronous generator (see ``rag.answer``).
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from core.ratelimit import rate_limited
from sources.models import Source
from workspace.models import Notebook

from .answer import stream_answer
from .models import Conversation, Message, MessageCitation
from .render import render_answer

#: Longest question accepted (characters).
MAX_QUESTION_CHARS = 2000


def _ask_error(request, message: str):
    """Show a validation message under the composer instead of in the chat log."""
    response = render(request, 'components/notice.html', {'variant': 'warning', 'message': message})
    response['HX-Retarget'] = '#ask-error'
    response['HX-Reswap'] = 'innerHTML'
    return response


def _notebook(request, notebook_id: int) -> Notebook:
    return get_object_or_404(Notebook, id=notebook_id, user=request.user)


def _assistant_message(request, message_id: int) -> Message:
    return get_object_or_404(
        Message.objects.select_related('conversation__notebook'),
        id=message_id, role=Message.ROLE_ASSISTANT, conversation__notebook__user=request.user,
    )


def chat_context(notebook: Notebook, *, error: str = '', question: str = '') -> dict:
    """Context of the chat panel (also used by the notebook page)."""
    conversation = Conversation.objects.filter(notebook=notebook).first()
    messages = list(conversation.messages.prefetch_related('citations')) if conversation else []
    for message in messages:
        if message.role == Message.ROLE_ASSISTANT and not message.is_open:
            message.html = render_answer(message)
    ready = notebook.sources.filter(status=Source.STATUS_READY).exists()
    return {'notebook': notebook, 'messages': messages, 'has_ready_sources': ready,
            'error': error, 'question': question, 'max_question_chars': MAX_QUESTION_CHARS}


def _chat(request, notebook, **kwargs):
    return render(request, 'rag/_chat.html', chat_context(notebook, **kwargs))


@login_required
@require_POST
@rate_limited('ask', 'ASCENDIA_RATE_ASK_PER_MIN', htmx_target='#ask-error')
def ask(request, notebook_id: int):
    notebook = _notebook(request, notebook_id)
    question = (request.POST.get('question') or '').strip()
    if not question:
        return _ask_error(request, _('Type a question.'))
    if len(question) > MAX_QUESTION_CHARS:
        return _ask_error(request, _('The question is too long (limit: %(n)s characters).') % {'n': MAX_QUESTION_CHARS})

    source_filter = None
    if request.POST.get('source_selection'):  # the sources panel was on the page
        chosen = [int(v) for v in request.POST.getlist('source') if v.isdigit()]
        source_filter = list(notebook.sources.filter(id__in=chosen).values_list('id', flat=True))
        if not source_filter:
            return _ask_error(request, _('Select at least one source to search.'))

    conversation = Conversation.for_notebook(notebook)
    user_msg = Message.objects.create(conversation=conversation, role=Message.ROLE_USER, content=question)
    answer = Message.objects.create(conversation=conversation, role=Message.ROLE_ASSISTANT,
                                    status=Message.STATUS_PENDING, source_filter=source_filter)
    return render(request, 'rag/_exchange.html', {'user_msg': user_msg, 'message': answer})


@login_required
@require_GET
def stream(request, message_id: int):
    message = _assistant_message(request, message_id)
    response = StreamingHttpResponse(stream_answer(message), content_type='text/event-stream; charset=utf-8')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # no proxy buffering of the stream
    return response


@login_required
@require_POST
def stop(request, message_id: int):
    message = _assistant_message(request, message_id)
    Message.objects.filter(pk=message.pk).filter(
        Q(status=Message.STATUS_PENDING) | Q(status=Message.STATUS_STREAMING),
    ).update(status=Message.STATUS_STOPPED)
    return render(request, 'rag/_stopped.html')


@login_required
@require_GET
def citation(request, message_id: int, n: int):
    message = _assistant_message(request, message_id)
    item = get_object_or_404(MessageCitation, message=message, n=n)
    return render(request, 'rag/_citation.html', {'citation': item})


@login_required
@require_POST
def clear(request, notebook_id: int):
    notebook = _notebook(request, notebook_id)
    Message.objects.filter(conversation__notebook=notebook).delete()
    return _chat(request, notebook)


@login_required
@require_GET
def chat_panel(request, notebook_id: int):
    return _chat(request, _notebook(request, notebook_id))
