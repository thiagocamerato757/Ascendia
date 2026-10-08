from __future__ import annotations

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from .parsing import SourceParseError, validate_pdf

MARKDOWN_EXTENSIONS = ('.md', '.markdown')


def kind_for_filename(name: str) -> str | None:
    """'pdf' / 'markdown' by extension, or None when the file type isn't accepted."""
    lower = name.lower()
    if lower.endswith('.pdf'):
        return 'pdf'
    if lower.endswith(MARKDOWN_EXTENSIONS):
        return 'markdown'
    return None


def _check_size(upload) -> None:
    max_bytes = settings.ASCENDIA_SOURCE_MAX_MB * 1024 * 1024
    if upload.size > max_bytes:
        raise forms.ValidationError(
            _('This file is larger than %(mb)s MB.') % {'mb': settings.ASCENDIA_SOURCE_MAX_MB}
        )


def validate_markdown_upload(upload) -> tuple[bytes, str]:
    """Check an uploaded Markdown file: size, valid UTF-8 (BOM allowed), real text.

    Returns ``(data, text)``; raises ``ValidationError`` with a user-facing message.
    """
    _check_size(upload)
    data = upload.read()
    upload.seek(0)
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise forms.ValidationError(_('This Markdown file is not valid UTF-8 text.')) from exc
    if '\x00' in text:
        raise forms.ValidationError(_('This file does not look like a text file.'))
    if not text.strip():
        raise forms.ValidationError(_('This file is empty.'))
    return data, text


def validate_pdf_upload(upload) -> tuple[bytes, int]:
    """Check one uploaded file (spec §7.1, §11): size, extension and real content.

    Returns ``(data, page_count)``; raises ``ValidationError`` with a user-facing message.
    """
    _check_size(upload)
    if not upload.name.lower().endswith('.pdf'):
        raise forms.ValidationError(_('Only PDF files are accepted.'))
    data = upload.read()
    upload.seek(0)
    try:
        pages = validate_pdf(data, max_pages=settings.ASCENDIA_SOURCE_MAX_PAGES)
    except SourceParseError as exc:
        raise forms.ValidationError(str(exc)) from exc
    return data, pages


class TextSourceForm(forms.Form):
    title = forms.CharField(
        label=_('Title'), max_length=255,
        widget=forms.TextInput(attrs={'class': 'c-field__input', 'placeholder': _('e.g. Class notes, week 3')}),
    )
    text = forms.CharField(
        label=_('Text'),
        widget=forms.Textarea(attrs={'class': 'c-field__input', 'rows': 6,
                                     'placeholder': _('Paste the text here.')}),
    )

    def clean_text(self) -> str:
        text = (self.cleaned_data.get('text') or '').strip()
        limit = settings.ASCENDIA_TEXT_SOURCE_MAX_CHARS
        if not text:
            raise forms.ValidationError(_('Paste some text.'))
        if len(text) > limit:
            raise forms.ValidationError(_('The text is longer than %(n)s characters.') % {'n': f'{limit:,}'})
        return text
