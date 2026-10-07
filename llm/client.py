"""Single entry point for LLM calls (spec §5).

Provider and model come from the notebook's settings, never hardcoded (decision
D4). API keys come from the owner's account-level credentials. The client
resolves the provider, decrypts the key, applies an explicit timeout and a
limited retry, and returns usage (tokens, latency, cost estimate). Failures
surface as :class:`ProviderError` with a safe message; the API key and source
text are never logged.
"""
from __future__ import annotations

import logging
import time

from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from . import constants as c
from . import model_catalog
from . import providers as _providers
from .crypto import DecryptionError
from .providers import BaseProvider, ChatResult, EmbedResult, FakeProvider, LiteLLMProvider, ProviderError

logger = logging.getLogger('ascendia.llm')

DEFAULT_TIMEOUT = 30.0
MAX_ATTEMPTS = 2

#: Set by tests (e.g. via mock.patch) to inject a FakeProvider. When None, the
#: real LiteLLM-backed provider is used.
_provider_override: BaseProvider | None = None


def set_provider_override(provider: BaseProvider | None) -> None:
    """Install a provider for every subsequent call (tests only)."""
    global _provider_override
    _provider_override = provider


def build_provider(provider_name: str) -> BaseProvider:
    """Return the provider implementation for a provider name."""
    if _provider_override is not None:
        return _provider_override
    if provider_name == FakeProvider.name:
        return FakeProvider()
    return LiteLLMProvider()


def _decrypt(credential) -> str | None:
    if credential is None:
        return None
    try:
        return credential.get_key()
    except DecryptionError as exc:
        raise ProviderError(
            _('The stored API key could not be read. Save the key again.')
        ) from exc


def _with_retry(call, *, what: str):
    """Run a provider call with a limited retry on transient failures."""
    last_error: ProviderError | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return call()
        except ProviderError as exc:
            last_error = exc
            logger.warning('LLM %s failed (attempt %s/%s): %s', what, attempt, MAX_ATTEMPTS, exc.user_message)
            if not exc.retryable:
                break
            if attempt < MAX_ATTEMPTS:
                time.sleep(0.2 * attempt)
    assert last_error is not None
    raise last_error


def _run_chat(provider_name, model, api_key, messages, timeout) -> ChatResult:
    provider = build_provider(provider_name)
    return _with_retry(
        lambda: provider.chat(model, messages, api_key=api_key, timeout=timeout),
        what='chat',
    )


def chat(settings, messages: list[dict], *, timeout: float = DEFAULT_TIMEOUT) -> ChatResult:
    """Chat completion using the notebook's configured chat provider/model."""
    api_key = _decrypt(settings.credential_for(settings.chat_provider))
    return _run_chat(settings.chat_provider, settings.chat_model, api_key, messages, timeout)


def embed(settings, texts: list[str], *, timeout: float = DEFAULT_TIMEOUT) -> EmbedResult:
    """Embeddings using the notebook's configured embedding provider/model."""
    provider = build_provider(settings.embedding_provider)
    api_key = _decrypt(settings.credential_for(settings.embedding_provider))
    return _with_retry(
        lambda: provider.embed(settings.embedding_model, texts, api_key=api_key, timeout=timeout),
        what='embed',
    )


def available_models(user, provider_name: str, kind: str = 'chat') -> list[str]:
    """Models of ``kind`` to offer for a provider in notebook settings.

    The user's refreshed list when it has models of that kind, else the curated
    list. Ids are LiteLLM identifiers (provider-prefixed), ready to be saved.
    """
    from .models import ProviderConfig

    kind = model_catalog.KIND_EMBEDDING if kind == 'embedding' else model_catalog.KIND_CHAT
    config = ProviderConfig.objects.filter(user=user, provider=provider_name).first()
    refreshed = model_catalog.ids_of_kind(config.model_list, kind) if config else []
    if refreshed:
        return refreshed
    catalog = c.PROVIDER_EMBEDDING_MODELS if kind == model_catalog.KIND_EMBEDDING else c.PROVIDER_CHAT_MODELS
    return list(catalog.get(provider_name, []))


def _provider_base_url(user, provider_name: str) -> str:
    from .models import ProviderConfig

    config = ProviderConfig.objects.filter(user=user, provider=provider_name).first()
    return c.base_url_for(provider_name, config.base_url if config else '')


def _provider_api_key(user, provider_name: str) -> str | None:
    from .models import ProviderCredential

    return _decrypt(ProviderCredential.objects.filter(user=user, provider=provider_name).first())


def provider_ready(user, provider_name: str) -> bool:
    """Whether the user has set the provider up: a saved key, or a saved server URL."""
    from .models import ProviderConfig, ProviderCredential

    if provider_name in c.LOCAL_PROVIDERS:
        return ProviderConfig.objects.filter(user=user, provider=provider_name).exclude(base_url='').exists()
    return ProviderCredential.objects.filter(user=user, provider=provider_name).exists()


def _setup_message(provider_name: str) -> str:
    if provider_name in c.LOCAL_PROVIDERS:
        return _('Save the server URL first.')
    return _('Save an API key for this provider first.')


def refresh_models(user, provider_name: str, *, timeout: float = 10.0) -> list[dict]:
    """Fetch a provider's live model list, normalized to ``{id, kind}`` entries.

    Ids are LiteLLM identifiers and only chat/embedding models are kept (see
    :mod:`llm.model_catalog`). Only runs once the provider is set up — an API
    key saved (cloud) or a server URL saved (local), see :func:`provider_ready`;
    otherwise, or when the listing fails, raises :class:`ProviderError`.
    """
    if not provider_ready(user, provider_name):
        raise ProviderError(_setup_message(provider_name), retryable=False, level='warning')
    api_key = None if provider_name in c.LOCAL_PROVIDERS else _provider_api_key(user, provider_name)
    base_url = _provider_base_url(user, provider_name)
    raw = _providers.list_models(provider_name, api_key=api_key, base_url=base_url, timeout=timeout)
    return model_catalog.normalize(provider_name, raw)


def refresh_and_store(user, provider_name: str) -> dict[str, int]:
    """Refresh a provider's models and save them for the notebook dropdowns.

    Returns the number of chat and embedding models now available. On failure
    the previously saved list is kept untouched.
    """
    from django.utils import timezone

    from .models import ProviderConfig

    models = refresh_models(user, provider_name)
    config, _created = ProviderConfig.objects.get_or_create(user=user, provider=provider_name)
    config.model_list = models
    config.models_updated_at = timezone.now()
    config.save(update_fields=['model_list', 'models_updated_at'])
    return model_catalog.counts(models)


def test_provider(user, provider_name: str, *, timeout: float = 15.0) -> str:
    """Verify a provider is usable; returns a short status message.

    Local endpoints (Ollama / LM Studio / llama.cpp) are tested for reachability
    by listing their models. Cloud providers do a minimal chat call, trying the
    candidate models in order (see :func:`_test_candidates`) and skipping those
    the provider lists but does not serve (404/410); any other failure — bad key,
    rate limit, timeout — ends the test. Raises :class:`ProviderError`.
    """
    if provider_name in c.LOCAL_PROVIDERS:
        models = refresh_models(user, provider_name, timeout=timeout)
        return ngettext(
            'endpoint reachable — %(n)s model available',
            'endpoint reachable — %(n)s models available',
            len(models),
        ) % {'n': len(models)}

    api_key = _provider_api_key(user, provider_name)
    if api_key is None:
        raise ProviderError(_('No API key saved for this provider.'), retryable=False, level='warning')
    candidates = _test_candidates(user, provider_name)
    if not candidates:
        raise ProviderError(_(
            'There is no model to test with yet. Refresh the models first.'
        ), retryable=False, level='warning')
    for model in candidates:
        try:
            result = _run_chat(provider_name, model, api_key, [{'role': 'user', 'content': 'ping'}], timeout)
        except ProviderError as exc:
            if exc.code == ProviderError.MODEL_UNAVAILABLE:
                continue
            raise
        return _('%(model)s answered in %(ms)s ms') % {'model': result.model, 'ms': result.latency_ms}
    raise ProviderError(_(
        'The key works, but none of the test models is available to this account. '
        "Pick a model in a notebook's settings."
    ), retryable=False, level='warning')


#: How many refreshed models to try when a provider has no built-in list.
_REFRESHED_TEST_CANDIDATES = 3


def _test_candidates(user, provider_name: str) -> list[str]:
    """Models to try for a connection test: the built-in list, else the refreshed one."""
    curated = list(c.PROVIDER_CHAT_MODELS.get(provider_name, []))
    if curated:
        return curated
    return available_models(user, provider_name, 'chat')[:_REFRESHED_TEST_CANDIDATES]
