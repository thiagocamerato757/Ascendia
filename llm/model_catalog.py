"""Normalize live model lists ("Refresh models") into what notebooks can use.

Each provider's API lists models in its own shape and with its own ids. The
notebook settings need two things from that list:

* the **LiteLLM identifier** (``groq/llama-3.3-70b-versatile``), because that is
  what the client sends to LiteLLM to route the call — a bare
  ``llama-3.3-70b-versatile`` would not reach Groq;
* the **kind** of model, so the chat dropdown only offers chat models and the
  embedding dropdown only offers embedding models.

Stored entries are ``{"id": <litellm id>, "kind": "chat" | "embedding"}``.
Lists saved before this format (plain strings) are still read, classified by
name.
"""
from __future__ import annotations

from . import constants as c

KIND_CHAT = 'chat'
KIND_EMBEDDING = 'embedding'
KIND_OTHER = 'other'  # audio, image, moderation… — not offered in notebooks

#: Prefix LiteLLM expects for each provider. OpenAI ids are used bare. llama.cpp
#: speaks the OpenAI API, so it is routed as ``openai/<model>`` with its api_base.
LITELLM_PREFIX = {
    c.PROVIDER_OPENAI: '',
    c.PROVIDER_ANTHROPIC: 'anthropic/',
    c.PROVIDER_GEMINI: 'gemini/',
    c.PROVIDER_DEEPSEEK: 'deepseek/',
    c.PROVIDER_MISTRAL: 'mistral/',
    c.PROVIDER_GROQ: 'groq/',
    c.PROVIDER_XAI: 'xai/',
    c.PROVIDER_PERPLEXITY: 'perplexity/',
    c.PROVIDER_TOGETHER: 'together_ai/',
    c.PROVIDER_NVIDIA: 'nvidia_nim/',
    c.PROVIDER_OPENROUTER: 'openrouter/',
    c.PROVIDER_OLLAMA: 'ollama/',
    c.PROVIDER_LMSTUDIO: 'lm_studio/',
    c.PROVIDER_LLAMACPP: 'openai/',
}

_EMBEDDING_HINTS = ('embed', 'bge-', 'bge:', '/bge', 'e5-', 'gte-', 'nomic', 'mxbai', 'minilm', 'm2-bert')
_OTHER_HINTS = (
    'whisper', 'tts', 'dall-e', 'image', 'audio', 'realtime', 'transcribe', 'moderation',
    'davinci', 'babbage', 'search', 'computer-use', 'sora', 'guard', 'rerank', 'aqa',
)


def litellm_id(provider: str, raw_id: str) -> str:
    """The id LiteLLM routes on: the provider prefix + the API's model id."""
    prefix = LITELLM_PREFIX.get(provider, '')
    return raw_id if not prefix or raw_id.startswith(prefix) else f'{prefix}{raw_id}'


def classify(raw_id: str, hint: str | None = None) -> str:
    """Model kind from the API's own metadata (``hint``) or, failing that, its name."""
    if hint in (KIND_CHAT, KIND_EMBEDDING, KIND_OTHER):
        return hint
    name = raw_id.lower()
    if any(h in name for h in _EMBEDDING_HINTS):
        return KIND_EMBEDDING
    if any(h in name for h in _OTHER_HINTS):
        return KIND_OTHER
    return KIND_CHAT


def normalize(provider: str, entries) -> list[dict]:
    """Turn a provider listing into sorted, de-duplicated ``{id, kind}`` entries.

    ``entries`` items are plain ids or ``{"id": ..., "kind": <hint or None>}``.
    Models that are neither chat nor embedding are dropped.
    """
    seen: dict[str, str] = {}
    for entry in entries:
        raw, hint = (entry, None) if isinstance(entry, str) else (entry.get('id', ''), entry.get('kind'))
        if not raw:
            continue
        kind = classify(raw, hint)
        if kind == KIND_OTHER:
            continue
        seen.setdefault(litellm_id(provider, raw), kind)
    return [{'id': model_id, 'kind': kind} for model_id, kind in sorted(seen.items())]


def ids_of_kind(model_list, kind: str) -> list[str]:
    """Model ids of one kind from a stored list (new dict format or legacy strings)."""
    out = []
    for entry in model_list or []:
        if isinstance(entry, str):
            if classify(entry) == kind:
                out.append(entry)
        elif entry.get('kind') == kind:
            out.append(entry['id'])
    return out


def counts(model_list) -> dict[str, int]:
    return {
        KIND_CHAT: len(ids_of_kind(model_list, KIND_CHAT)),
        KIND_EMBEDDING: len(ids_of_kind(model_list, KIND_EMBEDDING)),
    }
