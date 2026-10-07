from __future__ import annotations

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from .parsing import SourceParseError, validate_pdf


class PdfUploadForm(forms.Form):
    """Upload validation (spec §7.1, §11): size, extension and real content."""

    file = forms.FileField(
        label=_('PDF file'),
        widget=forms.ClearableFileInput(attrs={'accept': 'application/pdf,.pdf', 'class': 'c-field__input'}),
    )

    def clean_file(self):
        upload = self.cleaned_data['file']
        max_bytes = settings.ASCENDIA_SOURCE_MAX_MB * 1024 * 1024
        if upload.size > max_bytes:
            raise forms.ValidationError(
                _('This file is larger than %(mb)s MB.') % {'mb': settings.ASCENDIA_SOURCE_MAX_MB}
            )
        if not upload.name.lower().endswith('.pdf'):
            raise forms.ValidationError(_('Only PDF files are accepted.'))
        data = upload.read()
        upload.seek(0)
        try:
            self.page_count = validate_pdf(data, max_pages=settings.ASCENDIA_SOURCE_MAX_PAGES)
        except SourceParseError as exc:
            raise forms.ValidationError(str(exc)) from exc
        self.data_bytes = data
        return upload


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
