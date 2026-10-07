from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.urls import reverse

from llm import client, model_catalog, providers
from llm import constants as c
from llm.models import NotebookSettings, ProviderConfig, ProviderCredential
from llm.providers import ProviderError
from workspace.models import Notebook

from . import FernetTestCase


class ModelCatalogTests(SimpleTestCase):
    def test_litellm_id_adds_provider_prefix_once(self):
        self.assertEqual(model_catalog.litellm_id(c.PROVIDER_GROQ, 'llama-3.3-70b'), 'groq/llama-3.3-70b')
        self.assertEqual(model_catalog.litellm_id(c.PROVIDER_GROQ, 'groq/llama-3.3-70b'), 'groq/llama-3.3-70b')
        self.assertEqual(model_catalog.litellm_id(c.PROVIDER_OPENAI, 'gpt-4o'), 'gpt-4o')

    def test_classify_by_name(self):
        self.assertEqual(model_catalog.classify('text-embedding-3-small'), 'embedding')
        self.assertEqual(model_catalog.classify('nomic-embed-text:latest'), 'embedding')
        self.assertEqual(model_catalog.classify('whisper-1'), 'other')
        self.assertEqual(model_catalog.classify('dall-e-3'), 'other')
        self.assertEqual(model_catalog.classify('gpt-4o-mini'), 'chat')

    def test_api_hint_wins_over_name(self):
        self.assertEqual(model_catalog.classify('weird-name', 'embedding'), 'embedding')

    def test_normalize_prefixes_filters_dedupes_and_sorts(self):
        out = model_catalog.normalize(c.PROVIDER_OPENAI, [
            'gpt-4o', 'whisper-1', 'text-embedding-3-small', 'gpt-4o', {'id': 'o4-mini', 'kind': None},
        ])
        self.assertEqual(out, [
            {'id': 'gpt-4o', 'kind': 'chat'},
            {'id': 'o4-mini', 'kind': 'chat'},
            {'id': 'text-embedding-3-small', 'kind': 'embedding'},
        ])

    def test_ids_of_kind_reads_legacy_string_lists(self):
        legacy = ['llama3.1', 'nomic-embed-text']
        self.assertEqual(model_catalog.ids_of_kind(legacy, 'chat'), ['llama3.1'])
        self.assertEqual(model_catalog.ids_of_kind(legacy, 'embedding'), ['nomic-embed-text'])


class ProviderRegistryTests(SimpleTestCase):
    """Every provider is fully wired for refresh and LiteLLM routing."""

    def test_every_provider_has_prefix_and_listing_endpoint(self):
        for provider, _label in c.PROVIDER_CHOICES:
            with self.subTest(provider=provider):
                self.assertIn(provider, model_catalog.LITELLM_PREFIX)
                self.assertTrue(c.base_url_for(provider), 'no URL to list models from')
                self.assertIn(provider, c.PROVIDER_CHAT_MODELS)
                self.assertIn(provider, c.PROVIDER_EMBEDDING_MODELS)

    def test_curated_ids_carry_the_provider_prefix(self):
        for catalog in (c.PROVIDER_CHAT_MODELS, c.PROVIDER_EMBEDDING_MODELS):
            for provider, models in catalog.items():
                for model in models:
                    with self.subTest(model=model):
                        self.assertEqual(model_catalog.litellm_id(provider, model), model)


def _response(payload, status=200):
    import requests

    resp = mock.Mock()
    resp.status_code = status
    resp.is_redirect = False
    resp.json.return_value = payload
    if status >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(response=resp)
    else:
        resp.raise_for_status.return_value = None
    return resp


class ListModelsParsingTests(SimpleTestCase):
    """The live listing understands each provider's response shape."""

    def call(self, provider, payload, status=200):
        with mock.patch('requests.get', return_value=_response(payload, status)) as get:
            out = providers.list_models(provider, api_key='k', base_url='https://x', timeout=1)
        return out, get

    def test_together_bare_array_with_types(self):
        out, _get = self.call(c.PROVIDER_TOGETHER, [
            {'id': 'meta-llama/Llama-3.3-70B', 'type': 'chat'},
            {'id': 'BAAI/bge-large', 'type': 'embedding'},
            {'id': 'black-forest-labs/FLUX', 'type': 'image'},
        ])
        normalized = model_catalog.normalize(c.PROVIDER_TOGETHER, out)
        self.assertEqual(normalized, [
            {'id': 'together_ai/BAAI/bge-large', 'kind': 'embedding'},
            {'id': 'together_ai/meta-llama/Llama-3.3-70B', 'kind': 'chat'},
        ])

    def test_gemini_uses_generation_methods_and_asks_for_all_pages(self):
        out, get = self.call(c.PROVIDER_GEMINI, {'models': [
            {'name': 'models/gemini-2.5-flash', 'supportedGenerationMethods': ['generateContent']},
            {'name': 'models/text-embedding-004', 'supportedGenerationMethods': ['embedContent']},
            {'name': 'models/old', 'supportedGenerationMethods': ['countTokens']},
        ]})
        normalized = model_catalog.normalize(c.PROVIDER_GEMINI, out)
        self.assertEqual(normalized, [
            {'id': 'gemini/gemini-2.5-flash', 'kind': 'chat'},
            {'id': 'gemini/text-embedding-004', 'kind': 'embedding'},
        ])
        self.assertEqual(get.call_args.kwargs['params']['pageSize'], 1000)

    def test_anthropic_asks_for_more_than_the_default_page(self):
        _out, get = self.call(c.PROVIDER_ANTHROPIC, {'data': [{'id': 'claude-sonnet-4'}]})
        self.assertEqual(get.call_args.kwargs['params']['limit'], 1000)

    def test_nvidia_nim_splits_chat_embedding_and_drops_rerank(self):
        out, get = self.call(c.PROVIDER_NVIDIA, {'data': [
            {'id': 'nvidia/llama-3.1-nemotron-70b-instruct'},
            {'id': 'nvidia/llama-3.2-nv-embedqa-1b-v1'},
            {'id': 'nvidia/nv-rerankqa-mistral-4b-v3'},
        ]})
        self.assertEqual(model_catalog.normalize(c.PROVIDER_NVIDIA, out), [
            {'id': 'nvidia_nim/nvidia/llama-3.1-nemotron-70b-instruct', 'kind': 'chat'},
            {'id': 'nvidia_nim/nvidia/llama-3.2-nv-embedqa-1b-v1', 'kind': 'embedding'},
        ])
        self.assertEqual(get.call_args.args[0], 'https://x/models')

    def test_missing_listing_endpoint_explains_fallback(self):
        with self.assertRaises(ProviderError) as ctx:
            self.call(c.PROVIDER_PERPLEXITY, {}, status=404)
        self.assertIn('lista', ctx.exception.user_message)  # pt-BR: "...lista embutida."


class RefreshFlowTests(FernetTestCase):
    """Refresh → stored list → notebook dropdowns."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('rf', password='pw')

    def tearDown(self):
        providers.set_model_lister(None)
        super().tearDown()

    def test_cloud_refresh_without_key_asks_for_it(self):
        providers.set_model_lister(lambda p, *, api_key, base_url: ['x'])
        with self.assertRaises(ProviderError) as ctx:
            client.refresh_models(self.user, c.PROVIDER_GROQ)
        self.assertEqual(ctx.exception.level, 'warning')

    def test_openrouter_also_needs_a_key(self):
        providers.set_model_lister(lambda p, *, api_key, base_url: ['anthropic/claude-sonnet-4'])
        with self.assertRaises(ProviderError):
            client.refresh_models(self.user, c.PROVIDER_OPENROUTER)
        cred = ProviderCredential(user=self.user, provider=c.PROVIDER_OPENROUTER)
        cred.set_key('sk-or-1234')
        cred.save()
        self.assertEqual(
            client.refresh_models(self.user, c.PROVIDER_OPENROUTER),
            [{'id': 'openrouter/anthropic/claude-sonnet-4', 'kind': 'chat'}],
        )

    def test_local_refresh_needs_a_saved_url(self):
        calls = []
        providers.set_model_lister(lambda p, *, api_key, base_url: calls.append(base_url) or ['llama3.1'])
        with self.assertRaises(ProviderError) as ctx:
            client.refresh_models(self.user, c.PROVIDER_OLLAMA)
        self.assertEqual(ctx.exception.level, 'warning')
        self.assertEqual(calls, [])  # nothing was called
        ProviderConfig.objects.create(user=self.user, provider=c.PROVIDER_OLLAMA, base_url='http://localhost:11434')
        client.refresh_models(self.user, c.PROVIDER_OLLAMA)
        self.assertEqual(calls, ['http://localhost:11434'])

    def test_buttons_disabled_until_key_or_url_saved(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('llm:api_keys'))
        rows = {r['value']: r for r in resp.context['cloud_rows'] + resp.context['local_rows']}
        self.assertFalse(rows[c.PROVIDER_OPENAI]['ready'])
        self.assertFalse(rows[c.PROVIDER_OLLAMA]['ready'])
        self.assertContains(resp, 'id="setup-openai"')
        self.assertContains(resp, 'id="setup-ollama"')

        cred = ProviderCredential(user=self.user, provider=c.PROVIDER_OPENAI)
        cred.set_key('sk-test-1234')
        cred.save()
        ProviderConfig.objects.create(user=self.user, provider=c.PROVIDER_OLLAMA, base_url='http://localhost:11434')
        resp = self.client.get(reverse('llm:api_keys'))
        self.assertNotContains(resp, 'id="setup-openai"')
        self.assertNotContains(resp, 'id="setup-ollama"')

    def test_dropdowns_get_only_their_kind(self):
        cred = ProviderCredential(user=self.user, provider=c.PROVIDER_OPENAI)
        cred.set_key('sk-test-1234')
        cred.save()
        providers.set_model_lister(
            lambda p, *, api_key, base_url: ['gpt-4o', 'text-embedding-3-large', 'tts-1'],
        )
        counts = client.refresh_and_store(self.user, c.PROVIDER_OPENAI)
        self.assertEqual(counts, {'chat': 1, 'embedding': 1})
        self.assertEqual(client.available_models(self.user, c.PROVIDER_OPENAI, 'chat'), ['gpt-4o'])
        self.assertEqual(
            client.available_models(self.user, c.PROVIDER_OPENAI, 'embedding'), ['text-embedding-3-large'],
        )

    def test_kind_without_refreshed_models_falls_back_to_builtin(self):
        ProviderConfig.objects.create(
            user=self.user, provider=c.PROVIDER_MISTRAL,
            model_list=[{'id': 'mistral/mistral-large-latest', 'kind': 'chat'}],
        )
        self.assertEqual(
            client.available_models(self.user, c.PROVIDER_MISTRAL, 'embedding'),
            c.PROVIDER_EMBEDDING_MODELS[c.PROVIDER_MISTRAL],
        )

    def test_failed_refresh_keeps_previous_list(self):
        ProviderConfig.objects.create(
            user=self.user, provider=c.PROVIDER_OLLAMA, base_url='http://localhost:11434',
            model_list=[{'id': 'ollama/llama3.1', 'kind': 'chat'}],
        )

        def boom(p, *, api_key, base_url):
            raise ProviderError('down')

        providers.set_model_lister(boom)
        with self.assertRaises(ProviderError):
            client.refresh_and_store(self.user, c.PROVIDER_OLLAMA)
        self.assertEqual(client.available_models(self.user, c.PROVIDER_OLLAMA, 'chat'), ['ollama/llama3.1'])

    def test_saved_model_stays_valid_after_refresh_drops_it(self):
        notebook = Notebook.objects.create(user=self.user, title='NB')
        NotebookSettings.objects.create(notebook=notebook, chat_provider=c.PROVIDER_GROQ,
                                        chat_model='groq/llama-3.3-70b-versatile')
        ProviderConfig.objects.create(
            user=self.user, provider=c.PROVIDER_GROQ, model_list=[{'id': 'groq/qwen-qwq-32b', 'kind': 'chat'}],
        )
        self.client.force_login(self.user)
        url = reverse('llm:notebook_settings', kwargs={'notebook_id': notebook.id})
        self.client.post(url, {
            'chat_provider': c.PROVIDER_GROQ, 'chat_model': 'groq/llama-3.3-70b-versatile',
            'embedding_provider': c.PROVIDER_OPENAI, 'embedding_model': 'text-embedding-3-small',
            'preset': c.PRESET_CONCISE, 'tone': c.TONE_NEUTRAL, 'length': c.LENGTH_MEDIUM,
            'language': c.LANGUAGE_PT_BR, 'answer_format': c.FORMAT_PROSE,
            'detail_level': c.DETAIL_INTERMEDIATE, 'extra_instructions': '',
        })
        self.assertEqual(NotebookSettings.objects.get(notebook=notebook).preset, c.PRESET_CONCISE)

    def test_providers_page_groups_cloud_and_local(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('llm:api_keys'))
        self.assertEqual([r['value'] for r in resp.context['local_rows']], [
            c.PROVIDER_OLLAMA, c.PROVIDER_LMSTUDIO, c.PROVIDER_LLAMACPP,
        ])
        self.assertContains(resp, 'o-button-grid')

    def test_unknown_provider_is_404(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('llm:refresh_models', kwargs={'provider': 'nope'}))
        self.assertEqual(resp.status_code, 404)


class ConnectionTestFallbackTests(FernetTestCase):
    """The connection test skips models the provider lists but does not serve."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('ct', password='pw')
        cred = ProviderCredential(user=self.user, provider=c.PROVIDER_NVIDIA)
        cred.set_key('nvapi-test-1234')
        cred.save()

    def tearDown(self):
        client.set_provider_override(None)
        super().tearDown()

    def _provider(self, outcomes):
        """Fake provider answering per model: an exception to raise, or None for OK."""
        calls = []

        class _Scripted(providers.FakeProvider):
            def chat(self, model, messages, **kwargs):
                calls.append(model)
                outcome = outcomes.get(model)
                if outcome is not None:
                    raise outcome
                return super().chat(model, messages, **kwargs)

        client.set_provider_override(_Scripted())
        return calls

    def _unavailable(self):
        return ProviderError('gone', retryable=False, code=ProviderError.MODEL_UNAVAILABLE)

    def test_skips_unavailable_model_and_reports_the_one_that_answered(self):
        first, second = c.PROVIDER_CHAT_MODELS[c.PROVIDER_NVIDIA][:2]
        calls = self._provider({first: self._unavailable()})
        message = client.test_provider(self.user, c.PROVIDER_NVIDIA)
        self.assertEqual(calls, [first, second])
        self.assertIn(second, message)

    def test_bad_key_stops_immediately(self):
        first = c.PROVIDER_CHAT_MODELS[c.PROVIDER_NVIDIA][0]
        calls = self._provider({first: ProviderError('bad key', retryable=False)})
        with self.assertRaises(ProviderError) as ctx:
            client.test_provider(self.user, c.PROVIDER_NVIDIA)
        self.assertEqual(ctx.exception.user_message, 'bad key')
        self.assertEqual(calls, [first])

    def test_all_unavailable_is_a_warning(self):
        self._provider({m: self._unavailable() for m in c.PROVIDER_CHAT_MODELS[c.PROVIDER_NVIDIA]})
        with self.assertRaises(ProviderError) as ctx:
            client.test_provider(self.user, c.PROVIDER_NVIDIA)
        self.assertEqual(ctx.exception.level, 'warning')

    def test_provider_without_builtin_list_uses_refreshed_models(self):
        cred = ProviderCredential(user=self.user, provider=c.PROVIDER_OPENROUTER)
        cred.set_key('sk-or-1234')
        cred.save()
        ProviderConfig.objects.create(user=self.user, provider=c.PROVIDER_OPENROUTER, model_list=[
            {'id': 'openrouter/a/one', 'kind': 'chat'}, {'id': 'openrouter/b/two', 'kind': 'chat'},
        ])
        calls = self._provider({})
        client.test_provider(self.user, c.PROVIDER_OPENROUTER)
        self.assertEqual(calls, ['openrouter/a/one'])

    def test_gone_410_maps_to_model_unavailable(self):
        exc = Exception('Gone')
        exc.status_code = 410
        err = providers.LiteLLMProvider()._map_error(exc)
        self.assertEqual(err.code, ProviderError.MODEL_UNAVAILABLE)
        self.assertFalse(err.retryable)
