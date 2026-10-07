"""Answer rendering: Markdown → sanitized HTML with clickable citation chips (§10.8).

Order matters for safety:

1. Markdown is rendered with raw HTML **disabled** (model output can't inject tags);
2. the HTML is sanitized with nh3 against a small allowlist;
3. only then ``[n]`` markers become chips — markup we generate ourselves from a
   number that matched ``\\d+``, pointing at a citation of this message.
"""
from __future__ import annotations

import re
from functools import lru_cache

import nh3
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext as _

_ALLOWED_TAGS = {'p', 'br', 'strong', 'em', 'code', 'pre', 'blockquote', 'ul', 'ol', 'li', 'h3', 'h4', 'hr'}
_CHIP = re.compile(r'\[(\d{1,3})\]')


@lru_cache(maxsize=1)
def _markdown():
    from markdown_it import MarkdownIt

    return MarkdownIt('commonmark', {'html': False, 'linkify': False}).disable(['image', 'link'])


def _to_safe_html(text: str) -> str:
    html = _markdown().render(text or '')
    # Headings from the model are demoted so they never compete with the page's.
    html = re.sub(r'<(/?)h[12]>', r'<\1h3>', html)
    return nh3.clean(html, tags=_ALLOWED_TAGS, attributes={}, link_rel=None)


def render_answer(message) -> str:
    """Sanitized HTML of an assistant message, with ``[n]`` as citation chips."""
    html = _to_safe_html(message.content)
    valid = {c.n for c in message.citations.all()} if message.pk else set()

    def chip(match: re.Match) -> str:
        n = int(match.group(1))
        if n not in valid:
            return ''  # defensive: the gate already removed unknown numbers
        url = reverse('rag:citation', kwargs={'message_id': message.pk, 'n': n})
        return str(format_html(
            '<button type="button" class="c-citation" hx-get="{}" hx-target="#citation-viewer" '
            'hx-swap="innerHTML" aria-label="{}">{}</button>',
            url, _('Open source %(n)s') % {'n': n}, n,
        ))

    return _CHIP.sub(chip, html)
