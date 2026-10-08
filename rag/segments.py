"""Split Markdown into prose, code and math, so text rules only touch prose.

The citation gate removes ``[n]`` markers and tidies spaces; doing that on the
whole answer corrupted code (``dp[3]`` → ``dp``, ``[0]`` dropped, indentation
collapsed). Every transformation of the model's text now goes through
:func:`split` and only rewrites ``prose`` segments.

Recognized (in this order of precedence):

* fenced code blocks (```` ``` ```` or ``~~~`` at line start, up to 3 spaces of
  indent), including an **unclosed** fence (common while an answer streams);
* inline code (a run of N backticks closed by a run of exactly N);
* display math ``$$…$$`` and ``\\[…\\]``; inline math ``\\(…\\)`` and ``$…$``.
  For ``$…$`` the Pandoc rule applies: no space right after the opening ``$`` or
  before the closing one, and the closing ``$`` is not followed by a digit, so
  "R$ 10 e R$ 20" stays prose.

Escaped dollars (``\\$``) stay prose.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

PROSE, CODE, MATH = 'prose', 'code', 'math'

_FENCE_OPEN = re.compile(r'^( {0,3})(`{3,}|~{3,})(.*)$')


@dataclass(frozen=True)
class Segment:
    kind: str
    text: str
    #: For math: 'inline' or 'display'; the delimiter-free TeX is in ``tex``.
    display: bool = False
    tex: str = ''


def _split_fences(text: str) -> list[tuple[bool, str]]:
    """[(is_fenced_code, chunk)] by lines; an unclosed fence runs to the end."""
    out: list[tuple[bool, str]] = []
    lines = text.splitlines(keepends=True)
    buf: list[str] = []
    i = 0
    while i < len(lines):
        m = _FENCE_OPEN.match(lines[i].rstrip('\r\n'))
        if m and not (m.group(2)[0] == '`' and '`' in m.group(3)):
            if buf:
                out.append((False, ''.join(buf)))
                buf = []
            fence = m.group(2)
            block = [lines[i]]
            i += 1
            close = re.compile(r'^ {0,3}' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}\s*$')
            while i < len(lines):
                block.append(lines[i])
                i += 1
                if close.match(block[-1].rstrip('\r\n')):
                    break
            out.append((True, ''.join(block)))
            continue
        buf.append(lines[i])
        i += 1
    if buf:
        out.append((False, ''.join(buf)))
    return out


def _inline_code_end(text: str, i: int) -> int | None:
    """End index (exclusive) of the inline code starting at text[i] (a backtick), or None."""
    run = len(text[i:]) - len(text[i:].lstrip('`'))
    j = i + run
    while True:
        k = text.find('`' * run, j)
        if k == -1:
            return None
        # exactly `run` backticks (not part of a longer run)
        if (k + run < len(text) and text[k + run] == '`') or text[k - 1] == '`':
            j = k + 1
            while j < len(text) and text[j] == '`':
                j += 1
            continue
        return k + run


def _dollar_inline_end(text: str, i: int) -> int | None:
    """End (exclusive) of ``$…$`` math opening at text[i], following the Pandoc rule."""
    if i + 1 >= len(text) or text[i + 1] in ' \t\n$':
        return None
    j = i + 1
    while j < len(text):
        c = text[j]
        if c == '\n' and text[j:j + 2] == '\n\n':
            return None
        if c == '\\':
            j += 2
            continue
        if c == '$':
            if text[j - 1] in ' \t' or (j + 1 < len(text) and text[j + 1].isdigit()):
                return None
            return j + 1
        j += 1
    return None


def _split_inline(chunk: str) -> list[Segment]:
    segments: list[Segment] = []
    prose_start = 0
    i = 0

    def flush(end: int) -> None:
        if end > prose_start:
            segments.append(Segment(PROSE, chunk[prose_start:end]))

    while i < len(chunk):
        c = chunk[i]
        nxt = chunk[i + 1] if i + 1 < len(chunk) else ''
        end = None
        seg = None
        if c == '\\' and nxt == '$':
            i += 2  # escaped dollar: prose
            continue
        if c == '`':
            end = _inline_code_end(chunk, i)
            if end is not None:
                seg = Segment(CODE, chunk[i:end])
            else:  # unmatched backticks: literal prose, skip the whole run
                while i < len(chunk) and chunk[i] == '`':
                    i += 1
                continue
        elif c == '$' and nxt == '$':
            k = chunk.find('$$', i + 2)
            if k != -1:
                end = k + 2
                seg = Segment(MATH, chunk[i:end], display=True, tex=chunk[i + 2:k].strip())
        elif c == '$':
            end = _dollar_inline_end(chunk, i)
            if end is not None:
                seg = Segment(MATH, chunk[i:end], display=False, tex=chunk[i + 1:end - 1])
        elif c == '\\' and nxt in '[(':
            closer = r'\]' if nxt == '[' else r'\)'
            k = chunk.find(closer, i + 2)
            if k != -1:
                end = k + 2
                seg = Segment(MATH, chunk[i:end], display=nxt == '[', tex=chunk[i + 2:k].strip())
        if seg is not None:
            flush(i)
            segments.append(seg)
            i = prose_start = end
            continue
        i += 1
    flush(len(chunk))
    return segments


def split(text: str) -> list[Segment]:
    """Segments of ``text`` in order; joining their ``text`` gives back the input."""
    out: list[Segment] = []
    for fenced, chunk in _split_fences(text or ''):
        if fenced:
            out.append(Segment(CODE, chunk))
        else:
            out.extend(_split_inline(chunk))
    return out


def map_prose(text: str, fn) -> str:
    """Apply ``fn`` to prose segments only; code and math are kept byte for byte."""
    return ''.join(fn(s.text) if s.kind == PROSE else s.text for s in split(text))


def normalize_math(text: str) -> str:
    """Rewrite ``\\(…\\)`` as ``$…$`` and ``\\[…\\]`` as a ``$$`` block, for the Markdown renderer."""
    parts = []
    for s in split(text):
        if s.kind == MATH and s.text.startswith('\\('):
            parts.append(f'${s.tex}$')
        elif s.kind == MATH and s.text.startswith('\\['):
            parts.append(f'\n$$\n{s.tex}\n$$\n')
        else:
            parts.append(s.text)
    return ''.join(parts)
