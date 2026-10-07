from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from . import constants as c
from . import crypto
from .style import StyleSpec


class ProviderCredential(models.Model):
    """A user's API key for one LLM provider, encrypted at rest (spec §5, D6).

    The plaintext key is never stored, logged or returned to templates, and no
    part of it is ever shown again: only the ciphertext is persisted.
    Managed on the Providers screen, one row per provider.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='provider_credentials')
    provider = models.CharField(max_length=20, choices=c.PROVIDER_CHOICES)
    ciphertext = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'provider')
        ordering = ['provider']
        verbose_name = _('provider credential')
        verbose_name_plural = _('provider credentials')

    def __str__(self) -> str:
        return f'{self.user.username} · {self.get_provider_display()}'

    def set_key(self, plaintext: str) -> None:
        """Encrypt and store a new API key. The plaintext is not retained."""
        plaintext = (plaintext or '').strip()
        self.ciphertext = crypto.encrypt(plaintext)

    def get_key(self) -> str:
        """Decrypt and return the stored API key (never send this to a template)."""
        return crypto.decrypt(self.ciphertext)


class ProviderConfig(models.Model):
    """Per-user, per-provider endpoint and refreshed model list (spec §5).

    Holds the Base URL for local endpoints (Ollama / LM Studio / llama.cpp) and
    the list of models fetched live from the provider ("Refresh models"). API
    keys stay in :class:`ProviderCredential`.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='provider_configs')
    provider = models.CharField(max_length=20, choices=c.PROVIDER_CHOICES)
    base_url = models.CharField(max_length=300, blank=True, default='')
    model_list = models.JSONField(default=list, blank=True)
    models_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'provider')
        ordering = ['provider']
        verbose_name = _('provider config')
        verbose_name_plural = _('provider configs')

    def __str__(self) -> str:
        return f'{self.user.username} · {self.get_provider_display()} config'

    @property
    def effective_base_url(self) -> str:
        return c.base_url_for(self.provider, self.base_url)


class NotebookSettings(models.Model):
    """Per-notebook provider, model and answer style (spec §4, §6; decision D4).

    The provider and models are selected here, per notebook (which lets the same
    corpus be compared across models). API keys themselves live per user, on the
    account screen (:class:`ProviderCredential`).
    """

    notebook = models.OneToOneField(
        'workspace.Notebook',
        on_delete=models.CASCADE,
        related_name='settings',
    )

    # Provider and models (chat + embedding kept separate so embeddings can use a
    # different provider; the model name is stored as LiteLLM expects it).
    chat_provider = models.CharField(
        _('Chat provider'), max_length=20, choices=c.PROVIDER_CHOICES, default=c.PROVIDER_OPENAI,
    )
    chat_model = models.CharField(_('Chat model'), max_length=120, default='gpt-4o-mini')
    embedding_provider = models.CharField(
        _('Embedding provider'), max_length=20, choices=c.PROVIDER_CHOICES, default=c.PROVIDER_OPENAI,
    )
    embedding_model = models.CharField(_('Embedding model'), max_length=120, default='text-embedding-3-small')

    # Structured answer style (spec §6).
    preset = models.CharField(_('Preset'), max_length=20, choices=c.PRESET_CHOICES, default=c.PRESET_DIDACTIC)
    tone = models.CharField(_('Tone'), max_length=20, choices=c.TONE_CHOICES, default=c.TONE_NEUTRAL)
    length = models.CharField(_('Length'), max_length=20, choices=c.LENGTH_CHOICES, default=c.LENGTH_MEDIUM)
    language = models.CharField(_('Language'), max_length=10, choices=c.LANGUAGE_CHOICES, default=c.LANGUAGE_PT_BR)
    answer_format = models.CharField(
        _('Answer format'), max_length=20, choices=c.FORMAT_CHOICES, default=c.FORMAT_PROSE,
    )
    detail_level = models.CharField(
        _('Detail level'), max_length=20, choices=c.DETAIL_CHOICES, default=c.DETAIL_INTERMEDIATE,
    )
    extra_instructions = models.CharField(
        _('Extra instructions'),
        max_length=c.EXTRA_INSTRUCTIONS_MAX_LENGTH,
        blank=True,
        default='',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('notebook settings')
        verbose_name_plural = _('notebook settings')

    def __str__(self) -> str:
        return f'Settings for {self.notebook}'

    @property
    def style_spec(self) -> StyleSpec:
        """Pure, DB-free view of the style fields for ``compile_style``."""
        return StyleSpec(
            preset=self.preset,
            tone=self.tone,
            length=self.length,
            language=self.language,
            answer_format=self.answer_format,
            detail_level=self.detail_level,
            extra_instructions=self.extra_instructions,
        )

    def credential_for(self, provider: str) -> ProviderCredential | None:
        return ProviderCredential.objects.filter(user=self.notebook.user, provider=provider).first()
