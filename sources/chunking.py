"""Paragraph-aware chunking with overlap (spec §7.1).

Rules, so a citation always points at one place:

* a chunk never crosses a page or a section boundary;
* paragraphs are packed together up to ``size`` characters;
* a paragraph longer than ``size`` is split at sentence, then word boundaries;
* consecutive chunks of the same page share ``overlap`` characters (whole
  words), so a fact split across a boundary is still found.

Sizes are in characters (configurable: ``ASCENDIA_CHUNK_SIZE`` /
``ASCENDIA_CHUNK_OVERLAP``); characters are a stable, model-independent proxy
for tokens (~4 characters per token in Portuguese/English).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .parsing import PageText


@dataclass(frozen=True)
class ChunkDraft:
    text: str
    page: int | None
    section: str


_PARAGRAPH_BREAK = re.compile(r'\n\s*\n')
_SENTENCE_END = re.compile(r'(?<=[.!?…])\s+')


def _clean(text: str) -> str:
    # Join hard-wrapped lines inside a paragraph, drop hyphenation at line ends.
    text = re.sub(r'-\n(?=\w)', '', text)
    text = re.sub(r'[ \t]*\n[ \t]*', ' ', text)
    return re.sub(r'\s{2,}', ' ', text).strip()


def _paragraphs(text: str) -> list[str]:
    return [p for p in (_clean(part) for part in _PARAGRAPH_BREAK.split(text)) if p]


def _split_long(paragraph: str, size: int) -> list[str]:
    """Split a paragraph longer than ``size`` at sentences, falling back to words."""
    pieces: list[str] = []
    current = ''
    for sentence in _SENTENCE_END.split(paragraph):
        units = [sentence] if len(sentence) <= size else sentence.split(' ')
        joiner = ' '
        for unit in units:
            candidate = f'{current}{joiner}{unit}' if current else unit
            if len(candidate) <= size:
                current = candidate
            else:
                if current:
                    pieces.append(current)
                current = unit[:size] if len(unit) > size else unit
    if current:
        pieces.append(current)
    return pieces


def _tail(text: str, overlap: int) -> str:
    """Last ``overlap`` characters of ``text``, starting at a word boundary."""
    if overlap <= 0 or len(text) <= overlap:
        return '' if overlap <= 0 else text
    tail = text[-overlap:]
    space = tail.find(' ')
    return tail[space + 1:] if space != -1 else tail


def chunk_pages(pages: list[PageText], *, size: int, overlap: int) -> list[ChunkDraft]:
    if size <= 0:
        raise ValueError('size must be positive')
    overlap = max(0, min(overlap, size // 2))
    drafts: list[ChunkDraft] = []

    for page in pages:
        units: list[str] = []
        for paragraph in _paragraphs(page.text):
            units.extend(_split_long(paragraph, size) if len(paragraph) > size else [paragraph])

        current = ''
        carried = ''  # overlap text at the start of `current`
        for unit in units:
            candidate = f'{current}\n\n{unit}' if current else unit
            if len(candidate) <= size or current == carried == '':
                current = candidate
                continue
            drafts.append(ChunkDraft(text=current, page=page.page, section=page.section))
            carried = _tail(current, overlap)
            current = f'{carried} {unit}'.strip() if carried and len(carried) + 1 + len(unit) <= size else unit
            if current == unit:
                carried = ''
        if current and current != carried:
            drafts.append(ChunkDraft(text=current, page=page.page, section=page.section))
    return drafts


# --------------------------------------------------------------------------- Markdown

def _markdown_blocks(text: str) -> list[str]:
    """Top-level blocks (paragraph, list, table, code, math, quote…) as their original text."""
    from markdown_it import MarkdownIt
    from mdit_py_plugins.dollarmath import dollarmath_plugin

    md = MarkdownIt('commonmark').enable(['table']).use(dollarmath_plugin, allow_space=False, allow_digits=False)
    lines = text.splitlines()
    blocks: list[str] = []
    for token in md.parse(text):
        if token.level == 0 and token.map and token.nesting in (0, 1):
            start, end = token.map
            block = '\n'.join(lines[start:end]).strip('\n')
            if block.strip():
                blocks.append(block)
    return blocks


def _split_oversized(block: str, size: int) -> list[str]:
    """A block larger than a chunk, split by lines; code keeps its fences in every piece."""
    lines = block.split('\n')
    fence_open = lines[0] if lines and lines[0].lstrip().startswith(('```', '~~~')) else None
    if fence_open:
        closing = lines[-1] if len(lines) > 1 and lines[-1].strip().startswith(fence_open.strip()[:3]) else ''
        inner = lines[1:-1] if closing else lines[1:]
        budget = max(1, size - len(fence_open) - len(closing) - 2)
        pieces, current = [], []
        for line in inner:
            if current and len('\n'.join(current + [line])) > budget:
                pieces.append(current)
                current = []
            current.append(line[:budget])
        if current:
            pieces.append(current)
        close = closing or fence_open.strip()[:3]
        return ['\n'.join([fence_open, *piece, close]) for piece in pieces]
    pieces, current = [], ''
    for line in lines:
        candidate = f'{current}\n{line}' if current else line
        if current and len(candidate) > size:
            pieces.append(current)
            candidate = line
        current = candidate[:size] if len(candidate) > size else candidate
    if current:
        pieces.append(current)
    return pieces


def chunk_markdown(pages: list[PageText], *, size: int, overlap: int) -> list[ChunkDraft]:
    """Markdown-aware chunking: whole blocks, original text (no reflow), per section.

    Code blocks, tables and formulas are never split unless a single block is
    larger than ``size``. Overlap repeats the previous block when it fits in
    ``overlap`` characters, so context crosses chunk boundaries without cutting
    a block in half.
    """
    if size <= 0:
        raise ValueError('size must be positive')
    drafts: list[ChunkDraft] = []
    for page in pages:
        blocks: list[str] = []
        for block in _markdown_blocks(page.text):
            blocks.extend(_split_oversized(block, size) if len(block) > size else [block])
        current: list[str] = []
        for block in blocks:
            candidate = '\n\n'.join(current + [block])
            if current and len(candidate) > size:
                drafts.append(ChunkDraft(text='\n\n'.join(current), page=page.page, section=page.section))
                carry = current[-1] if 0 < len(current[-1]) <= overlap else None
                current = [carry, block] if carry and len(carry) + 2 + len(block) <= size else [block]
            else:
                current.append(block)
        if current:
            drafts.append(ChunkDraft(text='\n\n'.join(current), page=page.page, section=page.section))
    return drafts

