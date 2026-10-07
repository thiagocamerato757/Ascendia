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
