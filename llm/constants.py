"""Curated choices for providers, models and answer style (spec §5 and §6).

Model names are a curated list per provider (see docs/decisions.md). Free-text
providers (the local endpoints and the OpenRouter gateway) take an arbitrary
model name. Any provider's list can also be refreshed live from its API
("Refresh models"), which is then shown in the notebook model selectors.
"""
from django.utils.translation import gettext_lazy as _

# --- Providers (spec §5, decision D3) --------------------------------------

PROVIDER_OPENAI = 'openai'
PROVIDER_GEMINI = 'gemini'
PROVIDER_ANTHROPIC = 'anthropic'
PROVIDER_DEEPSEEK = 'deepseek'
PROVIDER_MISTRAL = 'mistral'
PROVIDER_GROQ = 'groq'
PROVIDER_XAI = 'xai'
PROVIDER_PERPLEXITY = 'perplexity'
PROVIDER_TOGETHER = 'together'
PROVIDER_NVIDIA = 'nvidia_nim'
PROVIDER_OPENROUTER = 'openrouter'
# Local, self-hosted endpoints (each with its own Base URL).
PROVIDER_OLLAMA = 'ollama'
PROVIDER_LMSTUDIO = 'lmstudio'
PROVIDER_LLAMACPP = 'llamacpp'

PROVIDER_CHOICES = [
    (PROVIDER_OPENAI, 'OpenAI'),
    (PROVIDER_ANTHROPIC, 'Anthropic Claude'),
    (PROVIDER_GEMINI, 'Google Gemini'),
    (PROVIDER_DEEPSEEK, 'DeepSeek'),
    (PROVIDER_MISTRAL, 'Mistral'),
    (PROVIDER_GROQ, 'Groq'),
    (PROVIDER_XAI, 'xAI (Grok)'),
    (PROVIDER_PERPLEXITY, 'Perplexity'),
    (PROVIDER_TOGETHER, 'Together AI'),
    (PROVIDER_NVIDIA, 'NVIDIA NIM'),
    (PROVIDER_OPENROUTER, 'OpenRouter'),
    (PROVIDER_OLLAMA, 'Ollama'),
    (PROVIDER_LMSTUDIO, 'LM Studio'),
    (PROVIDER_LLAMACPP, 'llama.cpp'),
]

#: Local, self-hosted providers: no API key, a configurable Base URL.
LOCAL_PROVIDERS = {PROVIDER_OLLAMA, PROVIDER_LMSTUDIO, PROVIDER_LLAMACPP}

#: Default port and path of each local server (used until the user sets a URL).
LOCAL_DEFAULT_ENDPOINTS = {
    PROVIDER_OLLAMA: (11434, ''),
    PROVIDER_LMSTUDIO: (1234, '/v1'),
    PROVIDER_LLAMACPP: (8080, '/v1'),
}


def default_base_url(provider: str) -> str:
    """Default URL of a local server, on ``settings.ASCENDIA_LOCAL_LLM_HOST``."""
    if provider not in LOCAL_DEFAULT_ENDPOINTS:
        return ''
    from django.conf import settings

    host = getattr(settings, 'ASCENDIA_LOCAL_LLM_HOST', 'localhost') or 'localhost'
    port, path = LOCAL_DEFAULT_ENDPOINTS[provider]
    return f'http://{host}:{port}{path}'

#: Providers whose model names are free text instead of a curated list: the local
#: endpoints (arbitrary names) and gateways that expose hundreds of models.
FREE_TEXT_MODEL_PROVIDERS = LOCAL_PROVIDERS | {PROVIDER_OPENROUTER}

# --- Live model listing ("Refresh models") ---------------------------------
# Base URLs used to list models (GET /models etc.). Local providers use the
# user's configured Base URL instead.
PROVIDER_API_BASE = {
    PROVIDER_OPENAI: 'https://api.openai.com/v1',
    PROVIDER_OPENROUTER: 'https://openrouter.ai/api/v1',
    PROVIDER_GROQ: 'https://api.groq.com/openai/v1',
    PROVIDER_TOGETHER: 'https://api.together.xyz/v1',
    PROVIDER_NVIDIA: 'https://integrate.api.nvidia.com/v1',
    PROVIDER_PERPLEXITY: 'https://api.perplexity.ai',
    PROVIDER_DEEPSEEK: 'https://api.deepseek.com',
    PROVIDER_XAI: 'https://api.x.ai/v1',
    PROVIDER_MISTRAL: 'https://api.mistral.ai/v1',
    PROVIDER_ANTHROPIC: 'https://api.anthropic.com',
    PROVIDER_GEMINI: 'https://generativelanguage.googleapis.com/v1beta',
}


def base_url_for(provider: str, configured: str = '') -> str:
    """Effective Base URL: the user's value, else the local default, else the API base."""
    if configured:
        return configured
    if provider in LOCAL_DEFAULT_ENDPOINTS:
        return default_base_url(provider)
    return PROVIDER_API_BASE.get(provider, '')

# --- Curated model lists per provider --------------------------------------
# Stored as the identifier LiteLLM expects. Reviewed as providers ship models.

PROVIDER_CHAT_MODELS = {
    PROVIDER_OPENAI: [
        'gpt-4o',
        'gpt-4o-mini',
        'gpt-4.1',
        'gpt-4.1-mini',
        'o4-mini',
    ],
    PROVIDER_GEMINI: [
        'gemini/gemini-2.5-pro',
        'gemini/gemini-2.5-flash',
        'gemini/gemini-2.0-flash',
    ],
    PROVIDER_ANTHROPIC: [
        'anthropic/claude-opus-4-20250514',
        'anthropic/claude-sonnet-4-20250514',
        'anthropic/claude-3-7-sonnet-latest',
        'anthropic/claude-3-5-haiku-latest',
    ],
    PROVIDER_DEEPSEEK: [
        'deepseek/deepseek-chat',
        'deepseek/deepseek-reasoner',
    ],
    PROVIDER_MISTRAL: [
        'mistral/mistral-large-latest',
        'mistral/mistral-small-latest',
        'mistral/open-mistral-nemo',
    ],
    PROVIDER_GROQ: [
        'groq/llama-3.3-70b-versatile',
        'groq/llama-3.1-8b-instant',
        'groq/deepseek-r1-distill-llama-70b',
    ],
    PROVIDER_XAI: [
        'xai/grok-4',
        'xai/grok-3',
        'xai/grok-3-mini',
    ],
    PROVIDER_PERPLEXITY: [
        'perplexity/sonar',
        'perplexity/sonar-pro',
        'perplexity/sonar-reasoning',
    ],
    PROVIDER_TOGETHER: [
        'together_ai/meta-llama/Llama-3.3-70B-Instruct-Turbo',
        'together_ai/deepseek-ai/DeepSeek-V3',
        'together_ai/Qwen/Qwen2.5-72B-Instruct-Turbo',
    ],
    # NVIDIA's catalog lists many models that answer 404/410 (retired, or not
    # served to the account); keep only ones verified to respond (2026-10-07).
    PROVIDER_NVIDIA: [
        'nvidia_nim/nvidia/nemotron-3-super-120b-a12b',
        'nvidia_nim/openai/gpt-oss-20b',
    ],
    PROVIDER_OPENROUTER: [],  # free text (gateway to 200+ models)
    PROVIDER_OLLAMA: [],      # free text / refreshed from the endpoint
    PROVIDER_LMSTUDIO: [],    # free text / refreshed from the endpoint
    PROVIDER_LLAMACPP: [],    # free text / refreshed from the endpoint
}

PROVIDER_EMBEDDING_MODELS = {
    PROVIDER_OPENAI: [
        'text-embedding-3-small',
        'text-embedding-3-large',
    ],
    PROVIDER_GEMINI: [
        'gemini/text-embedding-004',
    ],
    PROVIDER_ANTHROPIC: [],  # Anthropic has no first-party embeddings; use another provider
    PROVIDER_DEEPSEEK: [],
    PROVIDER_MISTRAL: [
        'mistral/mistral-embed',
    ],
    PROVIDER_GROQ: [],
    PROVIDER_XAI: [],
    PROVIDER_PERPLEXITY: [],
    PROVIDER_TOGETHER: [
        'together_ai/togethercomputer/m2-bert-80M-8k-retrieval',
    ],
    # Verified 2026-10-07; the other listed embedders answer 404/410 or need
    # input_type (asymmetric models), which the client does not send yet.
    PROVIDER_NVIDIA: [
        'nvidia_nim/nvidia/nemotron-3-embed-1b',
    ],
    PROVIDER_OPENROUTER: [],  # free text
    PROVIDER_OLLAMA: [],      # free text / refreshed from the endpoint
    PROVIDER_LMSTUDIO: [],    # free text / refreshed from the endpoint
    PROVIDER_LLAMACPP: [],    # free text / refreshed from the endpoint
}


# --- Answer style (spec §6) ------------------------------------------------

PRESET_DIDACTIC = 'didatico'
PRESET_ANALYTIC = 'analitico'
PRESET_CONCISE = 'conciso'
PRESET_CUSTOM = 'personalizado'

PRESET_CHOICES = [
    (PRESET_DIDACTIC, _('Didactic')),
    (PRESET_ANALYTIC, _('Analytic')),
    (PRESET_CONCISE, _('Concise')),
    (PRESET_CUSTOM, _('Custom')),
]

TONE_FORMAL = 'formal'
TONE_NEUTRAL = 'neutro'
TONE_INFORMAL = 'informal'

TONE_CHOICES = [
    (TONE_FORMAL, _('Formal')),
    (TONE_NEUTRAL, _('Neutral')),
    (TONE_INFORMAL, _('Informal')),
]

LENGTH_SHORT = 'curto'
LENGTH_MEDIUM = 'medio'
LENGTH_LONG = 'longo'

LENGTH_CHOICES = [
    (LENGTH_SHORT, _('Short')),
    (LENGTH_MEDIUM, _('Medium')),
    (LENGTH_LONG, _('Long')),
]

LANGUAGE_PT_BR = 'pt-br'
LANGUAGE_EN = 'en'
LANGUAGE_ES = 'es'

LANGUAGE_CHOICES = [
    (LANGUAGE_PT_BR, _('Portuguese (Brazil)')),
    (LANGUAGE_EN, _('English')),
    (LANGUAGE_ES, _('Spanish')),
]

FORMAT_PROSE = 'prosa'
FORMAT_BULLETS = 'topicos'
FORMAT_STEPS = 'passo_a_passo'

FORMAT_CHOICES = [
    (FORMAT_PROSE, _('Prose')),
    (FORMAT_BULLETS, _('Bullet points')),
    (FORMAT_STEPS, _('Step by step')),
]

DETAIL_BEGINNER = 'iniciante'
DETAIL_INTERMEDIATE = 'intermediario'
DETAIL_ADVANCED = 'avancado'

DETAIL_CHOICES = [
    (DETAIL_BEGINNER, _('Beginner')),
    (DETAIL_INTERMEDIATE, _('Intermediate')),
    (DETAIL_ADVANCED, _('Advanced')),
]

#: Hard limit for the free-text extra instructions (spec §6).
EXTRA_INSTRUCTIONS_MAX_LENGTH = 500
