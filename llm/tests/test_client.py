from django.contrib.auth.models import User
from django.test import override_settings

from llm import client, providers
from llm import constants as c
from llm.models import NotebookSettings, ProviderConfig, ProviderCredential
from llm.providers import FakeProvider, ProviderError
from workspace.models import Notebook

from . import FernetTestCase


class ClientTests(FernetTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('carol', password='x')
        self.notebook = Notebook.objects.create(user=self.user, title='NB')
        self.settings = NotebookSettings.objects.create(
            notebook=self.notebook,
            chat_provider=c.PROVIDER_OPENAI, chat_model='gpt-4o-mini',
            embedding_provider=c.PROVIDER_OPENAI, embedding_model='text-embedding-3-small',
        )
        cred = ProviderCredential(user=self.user, provider=c.PROVIDER_OPENAI)
        cred.set_key('sk-openai-key-1234')
        cred.save()

    def tearDown(self):
        client.set_provider_override(None)
        providers.set_model_lister(None)
        super().tearDown()

    def test_chat_passes_configured_model_and_decrypted_key(self):
        fake = FakeProvider(reply='olá')
        client.set_provider_override(fake)
        result = client.chat(self.settings, [{'role': 'user', 'content': 'oi'}])
        self.assertEqual(result.text, 'olá')
        self.assertEqual(fake.last_chat_call['model'], 'gpt-4o-mini')
        self.assertEqual(fake.last_chat_call['api_key'], 'sk-openai-key-1234')

    def test_embed_uses_embedding_model(self):
        fake = FakeProvider()
        client.set_provider_override(fake)
        result = client.embed(self.settings, ['a', 'bb'])
        self.assertEqual(len(result.vectors), 2)
        self.assertEqual(fake.last_embed_call['model'], 'text-embedding-3-small')

    def test_provider_error_is_raised_with_safe_message(self):
        client.set_provider_override(FakeProvider(fail_with='mensagem segura'))
        with self.assertRaises(ProviderError) as ctx:
            client.chat(self.settings, [{'role': 'user', 'content': 'oi'}])
        self.assertEqual(ctx.exception.user_message, 'mensagem segura')

    def _counting_provider(self, retryable):
        class _Failing(FakeProvider):
            calls = 0

            def chat(self, model, messages, **kwargs):
                _Failing.calls += 1
                raise ProviderError('falha', retryable=retryable)

        return _Failing()

    def test_non_retryable_error_is_not_retried(self):
        failing = self._counting_provider(retryable=False)
        client.set_provider_override(failing)
        with self.assertRaises(ProviderError):
            client.chat(self.settings, [{'role': 'user', 'content': 'oi'}])
        self.assertEqual(failing.calls, 1)

    def test_transient_error_is_retried_once(self):
        transient = self._counting_provider(retryable=True)
        client.set_provider_override(transient)
        with self.assertRaises(ProviderError):
            client.chat(self.settings, [{'role': 'user', 'content': 'oi'}])
        self.assertEqual(transient.calls, client.MAX_ATTEMPTS)

    def test_cloud_test_provider_returns_message(self):
        client.set_provider_override(FakeProvider(reply='pong'))
        message = client.test_provider(self.user, c.PROVIDER_OPENAI)
        self.assertIn(c.PROVIDER_CHAT_MODELS[c.PROVIDER_OPENAI][0], message)

    def test_test_provider_without_key_raises(self):
        client.set_provider_override(FakeProvider())
        with self.assertRaises(ProviderError):
            client.test_provider(self.user, c.PROVIDER_GEMINI)  # no key saved

    def test_gateway_without_default_model_raises(self):
        client.set_provider_override(FakeProvider())
        with self.assertRaises(ProviderError):
            client.test_provider(self.user, c.PROVIDER_OPENROUTER)  # no default model

    # --- Refresh models / local endpoints ---------------------------------

    def test_refresh_models_uses_lister_and_base_url(self):
        seen = {}

        def lister(provider, *, api_key, base_url):
            seen['base_url'] = base_url
            return ['llama3.1', 'mistral']

        providers.set_model_lister(lister)
        ProviderConfig.objects.create(
            user=self.user, provider=c.PROVIDER_OLLAMA, base_url=c.default_base_url(c.PROVIDER_OLLAMA),
        )
        models = client.refresh_models(self.user, c.PROVIDER_OLLAMA)
        self.assertEqual(models, [
            {'id': 'ollama/llama3.1', 'kind': 'chat'},
            {'id': 'ollama/mistral', 'kind': 'chat'},
        ])
        self.assertEqual(seen['base_url'], c.default_base_url(c.PROVIDER_OLLAMA))

    def test_default_local_url_uses_configured_host(self):
        with override_settings(ASCENDIA_LOCAL_LLM_HOST='host.docker.internal'):
            self.assertEqual(c.default_base_url(c.PROVIDER_OLLAMA), 'http://host.docker.internal:11434')
            self.assertEqual(c.default_base_url(c.PROVIDER_LMSTUDIO), 'http://host.docker.internal:1234/v1')
        self.assertEqual(c.default_base_url(c.PROVIDER_OPENAI), '')

    def test_refresh_models_uses_configured_base_url(self):
        ProviderConfig.objects.create(
            user=self.user, provider=c.PROVIDER_OLLAMA, base_url='http://localhost:9999',
        )
        seen = {}
        providers.set_model_lister(lambda p, *, api_key, base_url: seen.setdefault('u', base_url) or ['m'])
        client.refresh_models(self.user, c.PROVIDER_OLLAMA)
        self.assertEqual(seen['u'], 'http://localhost:9999')

    def test_local_test_provider_pings_endpoint(self):
        ProviderConfig.objects.create(user=self.user, provider=c.PROVIDER_LMSTUDIO, base_url='http://localhost:1234/v1')
        providers.set_model_lister(lambda p, *, api_key, base_url: ['a', 'b', 'c'])
        message = client.test_provider(self.user, c.PROVIDER_LMSTUDIO)
        self.assertIn('3', message)

    def test_available_models_prefers_refreshed_list(self):
        ProviderConfig.objects.create(
            user=self.user, provider=c.PROVIDER_OPENAI, model_list=['custom-a', 'custom-b'],
        )
        self.assertEqual(client.available_models(self.user, c.PROVIDER_OPENAI, 'chat'), ['custom-a', 'custom-b'])

    def test_available_models_falls_back_to_curated(self):
        models = client.available_models(self.user, c.PROVIDER_OPENAI, 'chat')
        self.assertIn('gpt-4o-mini', models)
