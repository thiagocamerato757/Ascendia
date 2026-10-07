"""LLM provider abstraction (spec §5, decision D3).

A single interface (:class:`BaseProvider`) with ``chat`` and ``embed``. The real
implementation delegates to LiteLLM (lazily imported so the heavy dependency is
not loaded in the test suite). :class:`FakeProvider` lets tests exercise the
whole layer without spending API credits.
"""
from __future__ import annotations

import math
import re
import time
import zlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from django.utils.translation import gettext as _

from . import constants as c


class ProviderError(Exception):
    """A provider failure already mapped to a safe, user-facing message.

    ``args[0]`` is the user-facing message; it never contains the API key or
    source content (spec §5, §11).
    """

    #: ``code`` for a model the provider lists but will not serve (404 / 410).
    MODEL_UNAVAILABLE = 'model_unavailable'

    def __init__(self, user_message: str, *, retryable: bool = True, level: str = 'error', code: str = ''):
        super().__init__(user_message)
        self.user_message = user_message
        #: False for failures that a retry cannot fix (bad key, unknown model).
        self.retryable = retryable
        #: 'warning' when the user just has to do something first (e.g. save a
        #: key); 'error' when the provider call itself failed.
        self.level = level
        self.code = code


@dataclass
class ChatResult:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float | None = None


@dataclass
class EmbedResult:
    vectors: list[list[float]] = field(default_factory=list)
    model: str = ''
    input_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float | None = None


class ChatStream:
    """A streamed chat answer.

    Iterate it to receive text deltas as they arrive; once the iteration ends,
    :attr:`result` holds the full :class:`ChatResult` (text, tokens, latency,
    cost). Provider errors raised mid-stream are :class:`ProviderError`.
    """

    def __init__(self, deltas: Iterable[str], finish):
        self._deltas = deltas
        self._finish = finish  # callable(full_text) -> ChatResult
        self.result: ChatResult | None = None

    def __iter__(self) -> Iterator[str]:
        parts: list[str] = []
        for delta in self._deltas:
            if delta:
                parts.append(delta)
                yield delta
        self.result = self._finish(''.join(parts))


class BaseProvider:
    """Interface implemented by every provider.

    ``api_base`` overrides the provider endpoint (local servers); ``input_type``
    tells asymmetric embedding models whether texts are passages (indexing) or
    queries (search).
    """

    name: str = ''

    def chat(self, model: str, messages: list[dict], *, api_key: str | None = None,
             timeout: float = 30.0, api_base: str | None = None) -> ChatResult:
        raise NotImplementedError

    def stream_chat(self, model: str, messages: list[dict], *, api_key: str | None = None,
                    timeout: float = 30.0, api_base: str | None = None) -> ChatStream:
        raise NotImplementedError

    def embed(self, model: str, texts: list[str], *, api_key: str | None = None,
              timeout: float = 30.0, api_base: str | None = None,
              input_type: str | None = None) -> EmbedResult:
        raise NotImplementedError


#: Dimension of the fake hashing embedder: large enough that word hashes rarely
#: collide (at 64, unrelated texts outranked related ones in retrieval tests).
FAKE_EMBEDDING_DIM = 512


def hashing_embedding(text: str, dim: int = FAKE_EMBEDDING_DIM) -> list[float]:
    """Deterministic bag-of-words vector (crc32 of each word), L2-normalized.

    Texts sharing words get similar vectors, so retrieval tests are meaningful
    without a real model.
    """
    vec = [0.0] * dim
    for word in re.findall(r'\w+', text.lower()):
        vec[zlib.crc32(word.encode()) % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class FakeProvider(BaseProvider):
    """Deterministic in-memory provider for tests and local demos.

    Records the last call so tests can assert the model/messages/key that the
    client passed through from the notebook settings.
    """

    name = 'fake'

    def __init__(self, reply: str = 'resposta simulada', fail_with: str | None = None,
                 fail_after_tokens: int | None = None):
        self.reply = reply
        self.fail_with = fail_with
        #: When set, stream_chat raises ``fail_with`` after this many deltas.
        self.fail_after_tokens = fail_after_tokens
        self.last_chat_call: dict | None = None
        self.last_embed_call: dict | None = None
        self.embed_calls: list[dict] = []

    def _result(self, model, messages, text) -> ChatResult:
        return ChatResult(
            text=text,
            model=model,
            input_tokens=sum(len(str(m.get('content', '')).split()) for m in messages),
            output_tokens=len(text.split()),
            latency_ms=1,
            cost_usd=0.0,
        )

    def chat(self, model, messages, *, api_key=None, timeout=30.0, api_base=None) -> ChatResult:
        self.last_chat_call = {'model': model, 'messages': messages, 'api_key': api_key,
                               'timeout': timeout, 'api_base': api_base}
        if self.fail_with and self.fail_after_tokens is None:
            raise ProviderError(self.fail_with)
        return self._result(model, messages, self.reply)

    def stream_chat(self, model, messages, *, api_key=None, timeout=30.0, api_base=None) -> ChatStream:
        self.last_chat_call = {'model': model, 'messages': messages, 'api_key': api_key,
                               'timeout': timeout, 'api_base': api_base, 'stream': True}
        if self.fail_with and self.fail_after_tokens is None:
            raise ProviderError(self.fail_with)
        words = re.findall(r'\S+\s*', self.reply)

        def deltas():
            for i, word in enumerate(words):
                if self.fail_after_tokens is not None and i >= self.fail_after_tokens:
                    raise ProviderError(self.fail_with or 'stream failed')
                yield word

        return ChatStream(deltas(), lambda text: self._result(model, messages, text))

    def embed(self, model, texts, *, api_key=None, timeout=30.0, api_base=None, input_type=None) -> EmbedResult:
        call = {'model': model, 'texts': texts, 'api_key': api_key, 'timeout': timeout,
                'api_base': api_base, 'input_type': input_type}
        self.last_embed_call = call
        self.embed_calls.append(call)
        if self.fail_with and self.fail_after_tokens is None:  # a mid-stream failure leaves embeddings working
            raise ProviderError(self.fail_with)
        vectors = [hashing_embedding(t) for t in texts]
        return EmbedResult(vectors=vectors, model=model, input_tokens=sum(len(t.split()) for t in texts), latency_ms=1)


# --- Live model listing ("Refresh models") ---------------------------------

#: Overridable in tests (set_model_lister) to avoid real HTTP.
_model_lister = None


def set_model_lister(func) -> None:
    """Install a model-listing function for tests. None restores the default."""
    global _model_lister
    _model_lister = func


def _gemini_entry(m: dict) -> dict:
    methods = m.get('supportedGenerationMethods') or []
    if 'embedContent' in methods:
        hint = 'embedding'
    elif 'generateContent' in methods:
        hint = None  # chat-capable; the name still filters out image/TTS variants
    else:
        hint = 'other'
    return {'id': m['name'].split('/')[-1], 'kind': hint}


def _openai_style_entry(m: dict) -> dict:
    """OpenAI-compatible item; Together and Mistral add type/capability metadata."""
    hint = None
    kind = m.get('type')  # Together: chat, language, embedding, image, rerank…
    if kind == 'embedding':
        hint = 'embedding'
    elif kind and kind not in ('chat', 'language', 'code'):
        hint = 'other'
    caps = m.get('capabilities')  # Mistral: {"completion_chat": bool, ...}
    if isinstance(caps, dict) and 'completion_chat' in caps and not caps['completion_chat']:
        hint = hint or ('embedding' if 'embed' in m['id'] else 'other')
    return {'id': m['id'], 'kind': hint}


def _refuse_redirect(resp) -> None:
    if resp.is_redirect:
        raise ProviderError(_(
            'The server answered with a redirect. Enter its final address as the server URL.'
        ), retryable=False)


def list_models(provider: str, *, api_key: str | None, base_url: str, timeout: float = 10.0) -> list:
    """Fetch the models a provider exposes, as ``{"id", "kind"}`` entries.

    ``id`` is the provider's own id (no LiteLLM prefix) and ``kind`` a hint from
    the API's metadata, or None when the API gives none; see
    :mod:`llm.model_catalog` for normalization. Raises :class:`ProviderError`
    with a safe message on any failure.
    """
    if _model_lister is not None:
        return _model_lister(provider, api_key=api_key, base_url=base_url)

    import requests

    base = base_url.rstrip('/')
    # Never follow redirects from a user-supplied local server: a redirect could
    # send the request to a host the allowlist forbids (llm/local_urls.py).
    follow = provider not in c.LOCAL_PROVIDERS
    try:
        if provider == c.PROVIDER_OLLAMA:
            resp = requests.get(f'{base}/api/tags', timeout=timeout, allow_redirects=follow)
            _refuse_redirect(resp)
            resp.raise_for_status()
            return [{'id': m['name'], 'kind': None} for m in resp.json().get('models', [])]
        if provider == c.PROVIDER_GEMINI:
            resp = requests.get(
                f'{base}/models', params={'key': api_key or '', 'pageSize': 1000}, timeout=timeout,
            )
            resp.raise_for_status()
            return [_gemini_entry(m) for m in resp.json().get('models', [])]
        if provider == c.PROVIDER_ANTHROPIC:
            headers = {'x-api-key': api_key or '', 'anthropic-version': '2023-06-01'}
            resp = requests.get(f'{base}/v1/models', headers=headers, params={'limit': 1000}, timeout=timeout)
            resp.raise_for_status()
            return [{'id': m['id'], 'kind': 'chat'} for m in resp.json().get('data', [])]
        # OpenAI-compatible: GET /models with a Bearer token. Together returns a
        # bare JSON array instead of {"data": [...]}.
        headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
        resp = requests.get(f'{base}/models', headers=headers, timeout=timeout, allow_redirects=follow)
        _refuse_redirect(resp)
        resp.raise_for_status()
        payload = resp.json()
        items = payload if isinstance(payload, list) else payload.get('data', [])
        return [_openai_style_entry(m) for m in items]
    except ProviderError:
        raise  # already a safe, specific message (e.g. a refused redirect)
    except requests.exceptions.Timeout as exc:
        raise ProviderError(_('The provider took too long to list its models.')) from exc
    except requests.exceptions.ConnectionError as exc:
        raise ProviderError(_('Could not connect to the provider. Check the URL/endpoint.')) from exc
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status in (401, 403):
            raise ProviderError(_('The provider API key is invalid or was rejected.')) from exc
        if status == 404:
            raise ProviderError(_(
                "This provider doesn't publish a model list. Notebooks keep using the built-in list."
            )) from exc
        raise ProviderError(_('The provider refused to list its models.')) from exc
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ProviderError(_('Unexpected response from the provider while listing models.')) from exc
    except Exception as exc:  # noqa: BLE001 - mapped to a safe message
        raise ProviderError(_('Failed to list the provider models.')) from exc


class LiteLLMProvider(BaseProvider):
    """Real provider backed by LiteLLM. LiteLLM is imported lazily."""

    name = 'litellm'

    def _map_error(self, exc: Exception) -> ProviderError:
        import litellm

        if isinstance(exc, litellm.AuthenticationError):
            return ProviderError(_('The provider API key is invalid or was rejected.'), retryable=False)
        if isinstance(exc, litellm.Timeout):
            return ProviderError(_('The provider took too long to respond. Try again.'))
        if isinstance(exc, litellm.RateLimitError):
            return ProviderError(_('The provider usage limit was reached. Try again shortly.'))
        # 404 / 410: the model is listed (or configured) but not served — some
        # catalogs, like NVIDIA's, list deprecated models or ones the account
        # cannot use. LiteLLM raises 410 as a generic APIError.
        if isinstance(exc, (litellm.BadRequestError, litellm.NotFoundError)) or getattr(
            exc, 'status_code', None
        ) in (404, 410):
            return ProviderError(
                _('The configured model is not available for this provider.'),
                retryable=False, code=ProviderError.MODEL_UNAVAILABLE,
            )
        return ProviderError(_('Failed to reach the LLM provider. Try again.'))

    @staticmethod
    def _cost(litellm, resp) -> float | None:
        try:
            return litellm.completion_cost(completion_response=resp)
        except Exception:  # noqa: BLE001 - cost estimation is best-effort
            return None

    def chat(self, model, messages, *, api_key=None, timeout=30.0, api_base=None) -> ChatResult:
        import litellm

        started = time.monotonic()
        try:
            resp = litellm.completion(
                model=model, messages=messages, api_key=api_key, timeout=timeout, api_base=api_base,
            )
        except Exception as exc:  # noqa: BLE001 - mapped to a safe message below
            raise self._map_error(exc) from exc
        latency_ms = int((time.monotonic() - started) * 1000)
        usage = getattr(resp, 'usage', None)
        return ChatResult(
            text=resp.choices[0].message.content or '',
            model=model,
            input_tokens=getattr(usage, 'prompt_tokens', 0) or 0,
            output_tokens=getattr(usage, 'completion_tokens', 0) or 0,
            latency_ms=latency_ms,
            cost_usd=self._cost(litellm, resp),
        )

    def stream_chat(self, model, messages, *, api_key=None, timeout=30.0, api_base=None) -> ChatStream:
        import litellm

        started = time.monotonic()
        try:
            stream = litellm.completion(
                model=model, messages=messages, api_key=api_key, timeout=timeout, api_base=api_base,
                stream=True, stream_options={'include_usage': True},
            )
        except Exception as exc:  # noqa: BLE001 - mapped to a safe message below
            raise self._map_error(exc) from exc
        chunks: list = []

        def deltas():
            try:
                for chunk in stream:
                    chunks.append(chunk)
                    choices = getattr(chunk, 'choices', None) or []
                    delta = getattr(choices[0], 'delta', None) if choices else None
                    content = getattr(delta, 'content', None) if delta else None
                    if content:
                        yield content
            except ProviderError:
                raise
            except Exception as exc:  # noqa: BLE001 - mid-stream failure, mapped to a safe message
                raise self._map_error(exc) from exc

        def finish(text: str) -> ChatResult:
            latency_ms = int((time.monotonic() - started) * 1000)
            built = None
            try:
                built = litellm.stream_chunk_builder(chunks, messages=messages)
            except Exception:  # noqa: BLE001 - usage/cost are best-effort for streams
                built = None
            usage = getattr(built, 'usage', None) if built is not None else None
            return ChatResult(
                text=text,
                model=model,
                input_tokens=getattr(usage, 'prompt_tokens', 0) or 0,
                output_tokens=getattr(usage, 'completion_tokens', 0) or 0,
                latency_ms=latency_ms,
                cost_usd=self._cost(litellm, built) if built is not None else None,
            )

        return ChatStream(deltas(), finish)

    def embed(self, model, texts, *, api_key=None, timeout=30.0, api_base=None, input_type=None) -> EmbedResult:
        import litellm

        started = time.monotonic()
        extra = {'input_type': input_type} if input_type else {}
        try:
            resp = litellm.embedding(
                model=model, input=texts, api_key=api_key, timeout=timeout, api_base=api_base, **extra,
            )
        except Exception as exc:  # noqa: BLE001 - mapped to a safe message below
            raise self._map_error(exc) from exc
        latency_ms = int((time.monotonic() - started) * 1000)
        vectors = [item['embedding'] for item in resp.data]
        usage = getattr(resp, 'usage', None)
        return EmbedResult(
            vectors=vectors,
            model=model,
            input_tokens=getattr(usage, 'prompt_tokens', 0) or 0,
            latency_ms=latency_ms,
        )
