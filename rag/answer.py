"""Follow an answer as Server-Sent Events (spec §7.5).

The answer is written by a background thread (``rag.generation``); this module
only *follows* the message in the database and turns it into SSE events:

* ``html``  — the answer so far, as sanitized HTML (citations not yet clickable);
* ``done``  — the final assistant bubble (validated citations, copy actions,
  or the stopped/error state);
* ``error`` — only if following itself fails (e.g. it took far too long).

``follow`` is an **async** generator on purpose: under ASGI (production) Django
consumes a *synchronous* iterator in full before sending anything, which would
turn the stream into a single response at the end. Closing the connection only
stops following: the answer keeps being written, and any number of tabs can
follow it.

Orphans: an answer still ``streaming`` without a heartbeat for
``ASCENDIA_ANSWER_STALE_SECONDS`` lost its writer (restart, crash) and is marked
stopped with the text saved so far; a ``pending`` one that never started is
marked as an error.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from .export import decorate
from .generation import not_found_text  # noqa: F401 - re-exported for callers/tests
from .models import Message
from .render import render_partial

#: How often the follower re-reads the message.
POLL_SECONDS = 0.25
#: Comment line sent while nothing changes, so proxies keep the connection open.
KEEPALIVE_SECONDS = 15
#: Give up following after this long (the answer itself keeps its state).
MAX_FOLLOW_SECONDS = 15 * 60
#: A pending answer may wait for a free generation thread; be generous before calling it lost.
PENDING_STALE_FACTOR = 3


def sse(event: str, data: dict) -> str:
    return f'event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'


def _done_event(message_id: int, language: str) -> str:
    """Final event: the whole assistant bubble (answer, citations, copy actions or state)."""
    with translation.override(language):
        message = decorate(Message.objects.prefetch_related('citations').get(pk=message_id))
        bubble = render_to_string('rag/_assistant_message.html', {'message': message})
    return sse('done', {'bubble': bubble, 'status': message.status, 'not_found': message.not_found})


def _abandon_if_stale(message_id: int, language: str) -> bool:
    """Close an answer whose writer is gone. True if it was (or already is) closed."""
    stale = timedelta(seconds=settings.ASCENDIA_ANSWER_STALE_SECONDS)
    now = timezone.now()
    with translation.override(language):
        stopped = Message.objects.filter(
            pk=message_id, status=Message.STATUS_STREAMING, updated_at__lt=now - stale,
        ).update(status=Message.STATUS_STOPPED, updated_at=now)
        failed = Message.objects.filter(
            pk=message_id, status=Message.STATUS_PENDING, updated_at__lt=now - stale * PENDING_STALE_FACTOR,
        ).update(status=Message.STATUS_ERROR, updated_at=now,
                 error=_("This answer didn't start. Ask again."))
    return bool(stopped or failed)


async def follow(message_id: int, language: str) -> AsyncIterator[str]:
    """Stream an answer's progress until it is closed (complete, stopped or error)."""
    last_content = None
    last_sent = started = time.monotonic()
    while True:
        message = await Message.objects.only('id', 'status', 'content', 'updated_at').aget(pk=message_id)
        if not message.is_open or await sync_to_async(_abandon_if_stale)(message_id, language):
            yield await sync_to_async(_done_event)(message_id, language)
            return
        now = time.monotonic()
        if message.content and message.content != last_content:
            last_content = message.content
            yield sse('html', {'html': render_partial(message.content)})
            last_sent = now
        elif now - last_sent >= KEEPALIVE_SECONDS:
            yield ': keepalive\n\n'
            last_sent = now
        if now - started >= MAX_FOLLOW_SECONDS:
            with translation.override(language):
                yield sse('error', {'message': _('This answer is taking too long. Reload the page to check it.')})
            return
        await asyncio.sleep(POLL_SECONDS)
