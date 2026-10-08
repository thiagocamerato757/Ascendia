"""Copy an answer out of the app: as Markdown, or as formatted (rich) HTML.

Outside the app a bare ``[1]`` means nothing, so both versions end with the
list of the passages the answer actually cites (``cited=True``): source title,
page and section.
"""
from __future__ import annotations

import re

from django.utils.html import escape
from django.utils.translation import gettext as _

from .render import render_answer, rich_text_html


def _cited(message) -> list:
    return [c for c in message.citations.all() if c.cited]


def _reference(citation) -> str:
    parts = [citation.source_title]
    if citation.page:
        parts.append(_('p. %(page)s') % {'page': citation.page})
    if citation.section:
        parts.append(citation.section)
    return ', '.join(parts)


def as_markdown(message) -> str:
    """The answer's Markdown plus a "Sources" block with the cited passages."""
    text = (message.content or '').rstrip()
    cited = _cited(message)
    if not cited:
        return text
    lines = [text, '', '---', f'**{_("Sources")}**', '']
    lines += [f'[{c.n}] {_reference(c)}  ' for c in cited]
    return '\n'.join(lines).rstrip() + '\n'


def as_rich_html(message) -> str:
    """Sanitized HTML for pasting into Docs/Word/Notion; chips become plain ``[n]``."""
    body = rich_text_html(message.content)
    cited = _cited(message)
    if not cited:
        return body
    items = ''.join(f'<li>[{c.n}] {escape(_reference(c))}</li>' for c in cited)
    return f'{body}<hr><p><strong>{escape(_("Sources"))}</strong></p><ul>{items}</ul>'


def is_copyable(message) -> bool:
    """Finished (or stopped) answers with real content get the copy actions."""
    return (message.status in ('complete', 'stopped') and not message.not_found
            and bool(re.search(r'\S', message.content or '')))


def decorate(message):
    """Attach what the assistant bubble template shows: HTML and both copy versions."""
    if not message.is_open:
        message.html = render_answer(message)
    message.copyable = is_copyable(message)
    if message.copyable:
        message.copy_markdown = as_markdown(message)
        message.copy_html = as_rich_html(message)
    return message

