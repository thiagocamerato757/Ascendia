"""PDF validation and text extraction with PyMuPDF (spec §7.1).

Pure functions over bytes: no Django models, no network. Each page keeps its
number and the section it belongs to (from the PDF outline, when it has one),
so chunks — and therefore citations — can point at an exact page.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.utils.translation import gettext as _

PDF_MAGIC = b'%PDF-'


class SourceParseError(ValueError):
    """The file can't be used as a source; ``args[0]`` is a user-facing message."""


@dataclass(frozen=True)
class PageText:
    page: int | None  # 1-based; None for pasted text
    section: str
    text: str


def _open(data: bytes):
    import pymupdf

    if not data.startswith(PDF_MAGIC):
        raise SourceParseError(_('This file is not a PDF.'))
    try:
        doc = pymupdf.open(stream=data, filetype='pdf')
    except Exception as exc:  # noqa: BLE001 - any parser failure means "unreadable"
        raise SourceParseError(_('This PDF could not be read. It may be damaged.')) from exc
    if doc.needs_pass:
        doc.close()
        raise SourceParseError(_('This PDF is password-protected. Remove the password and upload it again.'))
    return doc


def validate_pdf(data: bytes, *, max_pages: int) -> int:
    """Check that ``data`` is a readable PDF within the page limit; return its page count."""
    doc = _open(data)
    try:
        pages = doc.page_count
    finally:
        doc.close()
    if pages == 0:
        raise SourceParseError(_('This PDF has no pages.'))
    if pages > max_pages:
        raise SourceParseError(
            _('This PDF has %(pages)s pages; the limit is %(max)s.') % {'pages': pages, 'max': max_pages}
        )
    return pages


def _section_by_page(toc: list, page_count: int) -> dict[int, str]:
    """Map each page to the most recent outline entry that starts on or before it."""
    starts = sorted((max(1, int(page)), str(title).strip()) for _level, title, page, *_ in toc if title)
    out: dict[int, str] = {}
    current = ''
    idx = 0
    for page in range(1, page_count + 1):
        while idx < len(starts) and starts[idx][0] <= page:
            current = starts[idx][1][:255]
            idx += 1
        out[page] = current
    return out


def extract_pdf(data: bytes) -> list[PageText]:
    """Text of every page, in reading order, with page number and section."""
    doc = _open(data)
    try:
        sections = _section_by_page(doc.get_toc(simple=True) or [], doc.page_count)
        pages = []
        for index, page in enumerate(doc, start=1):
            text = page.get_text('text', sort=True) or ''
            pages.append(PageText(page=index, section=sections.get(index, ''), text=text))
        return pages
    finally:
        doc.close()


def extract_text(text: str) -> list[PageText]:
    """Pasted text as a single page-less block."""
    return [PageText(page=None, section='', text=text)]
