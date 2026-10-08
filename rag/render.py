"""Answer rendering: Markdown → sanitized HTML, with math, highlighted code and
citation chips (spec §10.8).

Order matters for safety:

1. citation markers in **prose** become inert sentinels (never inside code or
   math: ``dp[3]`` is code, not a citation — see :mod:`rag.segments`);
2. ``\\(…\\)``/``\\[…\\]`` are normalized to ``$``/``$$``; Markdown is rendered
   with raw HTML **disabled**; math becomes ``.math`` elements holding escaped
   TeX (KaTeX renders them in the browser); fenced code is highlighted with
   Pygments (``tok-*`` classes);
3. nh3 sanitizes against an allowlist that accepts only those classes;
4. only then the sentinels become chips — markup we generate ourselves.
"""
from __future__ import annotations

import re
from functools import lru_cache

import nh3
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext as _

from .citations import MARKER
from .segments import map_prose, normalize_math

_ALLOWED_TAGS = {
    'p', 'br', 'strong', 'em', 'code', 'pre', 'blockquote', 'ul', 'ol', 'li', 'h3', 'h4', 'hr', 's',
    'table', 'thead', 'tbody', 'tr', 'th', 'td', 'span', 'div',
}
_ALLOWED_ATTRIBUTES = {'span': {'class'}, 'div': {'class'}, 'code': {'class'}}
_TOKEN_CLASS = re.compile(r'tok-[a-z0-9]{1,4}')
_LANGUAGE_CLASS = re.compile(r'language-[a-z0-9_+#.-]{1,30}')
_MATH_CLASSES = {'math', 'inline', 'block'}

#: Inert sentinels around a citation number, placed before Markdown rendering.
_SENTINEL = re.compile('(\\d{1,3})')


def _class_filter(tag: str, attr: str, value: str) -> str | None:
    """Keep only the classes our renderer produces (math, Pygments tokens, code language)."""
    if attr != 'class':
        return None
    classes = value.split()
    if tag == 'span' and all(_TOKEN_CLASS.fullmatch(c) or c in _MATH_CLASSES for c in classes):
        return value
    if tag == 'div' and set(classes) <= _MATH_CLASSES:
        return value
    if tag == 'code' and len(classes) == 1 and _LANGUAGE_CLASS.fullmatch(classes[0]):
        return value
    return None


def _highlight(code: str, lang: str, _attrs) -> str:
    """Pygments highlighting for fenced code; '' lets markdown-it escape it as plain text."""
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name
    from pygments.util import ClassNotFound

    if not lang:
        return ''
    try:
        lexer = get_lexer_by_name(lang.strip().split()[0].lower())
    except ClassNotFound:
        return ''
    return highlight(code, lexer, HtmlFormatter(nowrap=True, classprefix='tok-'))


@lru_cache(maxsize=1)
def _markdown():
    from markdown_it import MarkdownIt
    from mdit_py_plugins.dollarmath import dollarmath_plugin

    md = MarkdownIt('commonmark', {'html': False, 'linkify': False, 'highlight': _highlight})
    # Pandoc rule: "R$ 10 e R$ 20" is money, not math.
    md.use(dollarmath_plugin, allow_space=False, allow_digits=False, double_inline=True)
    return md.enable(['table', 'strikethrough']).disable(['image', 'link'])


def _sentinels(text: str, keep=lambda n: True) -> str:
    """Citation markers in prose → sentinels (only numbers accepted by ``keep``)."""
    def repl(match: re.Match) -> str:
        numbers = [int(n) for n in re.split(r'\s*[,;]\s*', match.group(1).strip())]
        return ''.join(f'{n}' for n in numbers if keep(n))

    return map_prose(text, lambda prose: MARKER.sub(repl, prose))


def _to_safe_html(text: str) -> str:
    html = _markdown().render(normalize_math(text or ''))
    # Headings from the model are demoted so they never compete with the page's.
    html = re.sub(r'<(/?)h[12]>', r'<\1h3>', html)
    return nh3.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRIBUTES,
                     attribute_filter=_class_filter, link_rel=None)


def markdown_to_safe_html(text: str) -> str:
    """Model or source text (untrusted) as sanitized HTML; citation markers stay as text."""
    return _to_safe_html(text)


def render_partial(text: str) -> str:
    """HTML of an answer still being written: citations shown but not clickable yet."""
    return _SENTINEL.sub(
        lambda m: f'<span class="c-citation c-citation--pending">{int(m.group(1))}</span>',
        _to_safe_html(_sentinels(text)),
    )


def render_answer(message) -> str:
    """Sanitized HTML of an assistant message, with valid ``[n]`` as clickable chips."""
    valid = {c.n for c in message.citations.all()} if message.pk else set()
    html = _to_safe_html(_sentinels(message.content, keep=lambda n: n in valid))

    def chip(match: re.Match) -> str:
        n = int(match.group(1))
        url = reverse('rag:citation', kwargs={'message_id': message.pk, 'n': n})
        return str(format_html(
            '<button type="button" class="c-citation" hx-get="{}" hx-target="#citation-viewer" '
            'hx-swap="innerHTML" aria-label="{}">{}</button>',
            url, _('Open source %(n)s') % {'n': n}, n,
        ))

    return _SENTINEL.sub(chip, html)


def rich_text_html(text: str) -> str:
    """For "Copy formatted": citations as plain superscript ``[n]``, no buttons."""
    return _SENTINEL.sub(lambda m: f'<sup>[{int(m.group(1))}]</sup>', _to_safe_html(_sentinels(text)))
