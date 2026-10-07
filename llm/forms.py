from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from . import client
from . import constants as c
from .models import NotebookSettings, ProviderCredential

_STYLE_FIELDS = ['preset', 'tone', 'length', 'language', 'answer_format', 'detail_level']


def _is_free_text(provider: str, models: list[str]) -> bool:
    """Free-text only when the provider has no list at all (curated or refreshed)."""
    return provider in c.FREE_TEXT_MODEL_PROVIDERS and not models


def _grouped_model_widget(provider: str, models: list[str], current: str) -> forms.Widget:
    """A Select when models are known, a TextInput for free-text providers with none."""
    if _is_free_text(provider, models):
        return forms.TextInput(attrs={
            'class': 'c-field__input',
            'placeholder': 'llama3.1, mistral, ...',
        })
    choices = [(m, m) for m in models]
    if current and current not in models:
        # Keep a previously saved value selectable even if the list changed.
        choices = [(current, current)] + choices
    return forms.Select(choices=choices, attrs={'class': 'c-field__control c-select__control'})


class NotebookSettingsForm(forms.ModelForm):
    """Per-notebook provider, model and answer style (spec §4, §6)."""

    extra_instructions = forms.CharField(
        required=False,
        max_length=c.EXTRA_INSTRUCTIONS_MAX_LENGTH,
        widget=forms.Textarea(attrs={
            'class': 'c-field__input',
            'rows': 3,
            'placeholder': _('Optional preferences (kept subordinate to the safety rules).'),
        }),
    )

    class Meta:
        model = NotebookSettings
        fields = [
            'chat_provider', 'chat_model',
            'embedding_provider', 'embedding_model',
            *_STYLE_FIELDS,
            'extra_instructions',
        ]
        widgets = {
            'chat_provider': forms.Select(attrs={'class': 'c-field__control c-select__control'}),
            'embedding_provider': forms.Select(attrs={'class': 'c-field__control c-select__control'}),
            **{f: forms.Select(attrs={'class': 'c-field__control c-select__control'}) for f in _STYLE_FIELDS},
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        chat_provider = self._provider_value('chat_provider')
        emb_provider = self._provider_value('embedding_provider')
        self.chat_model_options = client.available_models(user, chat_provider, 'chat')
        self.embedding_model_options = client.available_models(user, emb_provider, 'embedding')
        self.fields['chat_model'].widget = _grouped_model_widget(
            chat_provider, self.chat_model_options, self._field_value('chat_model'),
        )
        self.fields['embedding_model'].widget = _grouped_model_widget(
            emb_provider, self.embedding_model_options, self._field_value('embedding_model'),
        )
        self.chat_is_free_text = _is_free_text(chat_provider, self.chat_model_options)
        self.embedding_is_free_text = _is_free_text(emb_provider, self.embedding_model_options)

    def _provider_value(self, name: str) -> str:
        return self._field_value(name) or self.fields[name].initial or c.PROVIDER_OPENAI

    def _field_value(self, name: str) -> str:
        if self.is_bound:
            return (self.data.get(name) or '').strip()
        if self.instance and self.instance.pk:
            return getattr(self.instance, name, '') or ''
        return self.initial.get(name, '') if self.initial else ''

    def _validate_model(self, field: str, provider_field: str, kind: str) -> str:
        value = (self.cleaned_data.get(field) or '').strip()
        provider = self.cleaned_data.get(provider_field)
        models = client.available_models(self.user, provider, kind)
        if _is_free_text(provider, models):
            if not value:
                raise forms.ValidationError(_('Enter the model name.'))
            return value
        saved = getattr(self.instance, field, '') if self.instance and self.instance.pk else ''
        saved_provider = getattr(self.instance, provider_field, '') if saved else ''
        # A model already saved for this provider stays valid even if a later
        # "Refresh models" no longer lists it (renamed, deprecated…).
        if value not in models and not (value == saved and provider == saved_provider):
            raise forms.ValidationError(_('Choose a model available for the selected provider.'))
        return value

    def clean_chat_model(self) -> str:
        return self._validate_model('chat_model', 'chat_provider', 'chat')

    def clean_embedding_model(self) -> str:
        # Embeddings are optional per provider; allow blank when none is known.
        provider = self.data.get('embedding_provider')
        models = client.available_models(self.user, provider, 'embedding')
        if not _is_free_text(provider, models) and not models:
            return (self.cleaned_data.get('embedding_model') or '').strip()
        return self._validate_model('embedding_model', 'embedding_provider', 'embedding')


class ProviderCredentialForm(forms.Form):
    """Set (write-only) a user's API key for one provider. ``provider`` is fixed
    per row on the API keys screen and submitted as a hidden field."""

    provider = forms.ChoiceField(choices=c.PROVIDER_CHOICES, widget=forms.HiddenInput)
    api_key = forms.CharField(
        label=_('API key'),
        widget=forms.PasswordInput(render_value=False, attrs={
            'class': 'c-field__input',
            'autocomplete': 'off',
            'placeholder': 'sk-...',
        }),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_provider(self) -> str:
        provider = self.cleaned_data['provider']
        if provider in c.LOCAL_PROVIDERS:
            raise forms.ValidationError(_('Local providers do not use an API key.'))
        return provider

    def clean_api_key(self) -> str:
        key = (self.cleaned_data.get('api_key') or '').strip()
        if not key:
            raise forms.ValidationError(_('Enter the API key.'))
        return key

    def save(self) -> ProviderCredential:
        provider = self.cleaned_data['provider']
        credential, _created = ProviderCredential.objects.get_or_create(user=self.user, provider=provider)
        credential.set_key(self.cleaned_data['api_key'])
        credential.save()
        return credential


class BaseUrlForm(forms.Form):
    """Set the Base URL for a local endpoint (Ollama / LM Studio / llama.cpp)."""

    provider = forms.ChoiceField(choices=c.PROVIDER_CHOICES, widget=forms.HiddenInput)
    base_url = forms.CharField(
        max_length=300,
        widget=forms.TextInput(attrs={'class': 'c-field__input', 'placeholder': 'http://localhost:11434'}),
    )

    def clean_provider(self) -> str:
        provider = self.cleaned_data['provider']
        if provider not in c.LOCAL_PROVIDERS:
            raise forms.ValidationError(_('Base URL applies only to local providers.'))
        return provider

    def clean_base_url(self) -> str:
        url = (self.cleaned_data.get('base_url') or '').strip()
        if not (url.startswith('http://') or url.startswith('https://')):
            raise forms.ValidationError(_('Enter a URL starting with http:// or https://.'))
        return url.rstrip('/')
