from django.contrib.auth.models import User
from django.urls import reverse

from llm import client, providers
from llm import constants as c
from llm.models import NotebookSettings, ProviderConfig, ProviderCredential
from llm.providers import FakeProvider
from workspace.models import Notebook

from . import FernetTestCase


class ApiKeysViewTests(FernetTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user('owner', password='pw')
        self.other = User.objects.create_user('other', password='pw')
        self.url = reverse('llm:api_keys')

    def test_requires_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_lists_cloud_and_local_providers(self):
        self.client.login(username='owner', password='pw')
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'OpenAI')
        self.assertContains(resp, 'Ollama')
        self.assertContains(resp, 'LM Studio')
        self.assertContains(resp, 'llama.cpp')

    def test_set_key_is_write_only_and_never_shown(self):
        self.client.login(username='owner', password='pw')
        resp = self.client.post(
            reverse('llm:credential_set'),
            {'provider': c.PROVIDER_OPENAI, 'api_key': 'sk-abcd-7777'},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(ProviderCredential.objects.filter(user=self.owner, provider=c.PROVIDER_OPENAI).exists())
        self.assertNotContains(resp, 'sk-abcd-7777')
        self.assertNotContains(resp, '7777')  # not even the last characters
        self.assertContains(resp, 'chave salva e criptografada')

    def test_local_provider_key_rejected(self):
        self.client.login(username='owner', password='pw')
        self.client.post(reverse('llm:credential_set'), {'provider': c.PROVIDER_OLLAMA, 'api_key': 'x'})
        self.assertFalse(ProviderCredential.objects.filter(provider=c.PROVIDER_OLLAMA).exists())

    def test_set_base_url_for_local(self):
        self.client.login(username='owner', password='pw')
        self.client.post(reverse('llm:base_url_set'), {
            'provider': c.PROVIDER_OLLAMA, 'base_url': 'http://localhost:12345/',
        })
        config = ProviderConfig.objects.get(user=self.owner, provider=c.PROVIDER_OLLAMA)
        self.assertEqual(config.base_url, 'http://localhost:12345')  # trailing slash stripped

    def test_base_url_rejected_for_cloud(self):
        self.client.login(username='owner', password='pw')
        self.client.post(reverse('llm:base_url_set'), {
            'provider': c.PROVIDER_OPENAI, 'base_url': 'http://x',
        })
        self.assertFalse(ProviderConfig.objects.filter(provider=c.PROVIDER_OPENAI).exists())

    def test_user_only_sees_own_keys(self):
        other_cred = ProviderCredential(user=self.other, provider=c.PROVIDER_GEMINI)
        other_cred.set_key('sk-other-9999')
        other_cred.save()
        self.client.login(username='owner', password='pw')
        resp = self.client.get(self.url)
        self.assertNotContains(resp, '9999')

    def test_delete_is_owner_scoped(self):
        other_cred = ProviderCredential(user=self.other, provider=c.PROVIDER_GEMINI)
        other_cred.set_key('sk-other-9999')
        other_cred.save()
        self.client.login(username='owner', password='pw')
        self.client.post(reverse('llm:credential_delete', kwargs={'provider': c.PROVIDER_GEMINI}))
        self.assertTrue(ProviderCredential.objects.filter(id=other_cred.id).exists())


class RefreshModelsViewTests(FernetTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user('owner', password='pw')
        ProviderConfig.objects.create(user=self.owner, provider=c.PROVIDER_OLLAMA, base_url='http://localhost:11434')

    def tearDown(self):
        providers.set_model_lister(None)
        super().tearDown()

    def test_refresh_saves_models_and_reports_count(self):
        providers.set_model_lister(lambda p, *, api_key, base_url: ['m1', 'm2', 'm3'])
        self.client.login(username='owner', password='pw')
        resp = self.client.post(reverse('llm:refresh_models', kwargs={'provider': c.PROVIDER_OLLAMA}))
        self.assertEqual(resp.status_code, 200)
        config = ProviderConfig.objects.get(user=self.owner, provider=c.PROVIDER_OLLAMA)
        self.assertEqual([m['id'] for m in config.model_list], ['ollama/m1', 'ollama/m2', 'ollama/m3'])
        self.assertContains(resp, 'c-notice--success')
        self.assertContains(resp, 'hx-swap-oob')
        self.assertIsNotNone(config.models_updated_at)

    def test_refresh_error_is_reported(self):
        def boom(p, *, api_key, base_url):
            raise providers.ProviderError('sem conexão')

        providers.set_model_lister(boom)
        self.client.login(username='owner', password='pw')
        resp = self.client.post(reverse('llm:refresh_models', kwargs={'provider': c.PROVIDER_OLLAMA}))
        self.assertContains(resp, 'sem conexão')


class TestProviderViewTests(FernetTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user('owner', password='pw')

    def tearDown(self):
        client.set_provider_override(None)
        providers.set_model_lister(None)
        super().tearDown()

    def test_cloud_without_key_reports_error(self):
        self.client.login(username='owner', password='pw')
        resp = self.client.post(reverse('llm:test_provider', kwargs={'provider': c.PROVIDER_OPENAI}))
        self.assertContains(resp, 'Nenhuma chave de API salva')

    def test_cloud_with_key_reports_ok(self):
        cred = ProviderCredential(user=self.owner, provider=c.PROVIDER_OPENAI)
        cred.set_key('sk-1234')
        cred.save()
        client.set_provider_override(FakeProvider(reply='pong'))
        self.client.login(username='owner', password='pw')
        resp = self.client.post(reverse('llm:test_provider', kwargs={'provider': c.PROVIDER_OPENAI}))
        self.assertContains(resp, 'respondeu')

    def test_local_reports_reachable(self):
        ProviderConfig.objects.create(user=self.owner, provider=c.PROVIDER_OLLAMA, base_url='http://localhost:11434')
        providers.set_model_lister(lambda p, *, api_key, base_url: ['a', 'b'])
        self.client.login(username='owner', password='pw')
        resp = self.client.post(reverse('llm:test_provider', kwargs={'provider': c.PROVIDER_OLLAMA}))
        self.assertContains(resp, 'acessível')


class ModelOptionsViewTests(FernetTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user('owner', password='pw')
        self.url = reverse('llm:model_options')

    def test_curated_models_for_provider(self):
        self.client.login(username='owner', password='pw')
        resp = self.client.get(self.url, {'kind': 'chat', 'chat_provider': c.PROVIDER_MISTRAL})
        self.assertContains(resp, 'mistral/mistral-large-latest')

    def test_free_text_providers_render_input(self):
        self.client.login(username='owner', password='pw')
        for provider in (c.PROVIDER_OLLAMA, c.PROVIDER_OPENROUTER):
            resp = self.client.get(self.url, {'kind': 'chat', 'chat_provider': provider})
            self.assertContains(resp, 'type="text"')

    def test_refreshed_models_render_as_select(self):
        ProviderConfig.objects.create(user=self.owner, provider=c.PROVIDER_OLLAMA, model_list=['llama3.1'])
        self.client.login(username='owner', password='pw')
        resp = self.client.get(self.url, {'kind': 'chat', 'chat_provider': c.PROVIDER_OLLAMA})
        self.assertContains(resp, 'llama3.1')
        self.assertNotContains(resp, 'type="text"')


class NotebookSettingsViewTests(FernetTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user('owner', password='pw')
        self.other = User.objects.create_user('other', password='pw')
        self.notebook = Notebook.objects.create(user=self.owner, title='NB')
        self.url = reverse('llm:notebook_settings', kwargs={'notebook_id': self.notebook.id})

    def test_requires_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_owner_opens_and_settings_autocreated(self):
        self.client.login(username='owner', password='pw')
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(NotebookSettings.objects.filter(notebook=self.notebook).exists())
        self.assertContains(resp, 'id_chat_provider')
        self.assertContains(resp, 'Regras invioláveis')

    def test_compiled_instruction_follows_browser_language(self):
        self.client.login(username='owner', password='pw')
        en = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE='en')
        pt = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE='pt-BR')
        self.assertContains(en, 'Inviolable rules')
        self.assertContains(pt, 'Regras invioláveis')

    def test_other_user_gets_404(self):
        self.client.login(username='other', password='pw')
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_save_provider_model_and_style(self):
        self.client.login(username='owner', password='pw')
        resp = self.client.post(self.url, {
            'chat_provider': c.PROVIDER_GROQ, 'chat_model': 'groq/llama-3.3-70b-versatile',
            'embedding_provider': c.PROVIDER_OPENAI, 'embedding_model': 'text-embedding-3-large',
            'preset': c.PRESET_CONCISE, 'tone': c.TONE_FORMAL, 'length': c.LENGTH_SHORT,
            'language': c.LANGUAGE_EN, 'answer_format': c.FORMAT_BULLETS,
            'detail_level': c.DETAIL_ADVANCED, 'extra_instructions': 'seja breve',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        settings = NotebookSettings.objects.get(notebook=self.notebook)
        self.assertEqual(settings.chat_provider, c.PROVIDER_GROQ)
        self.assertEqual(settings.language, c.LANGUAGE_EN)
        self.assertContains(resp, 'inglês')

    def test_invalid_model_rejected(self):
        self.client.login(username='owner', password='pw')
        self.client.post(self.url, {
            'chat_provider': c.PROVIDER_OPENAI, 'chat_model': 'gpt-nope',
            'embedding_provider': c.PROVIDER_OPENAI, 'embedding_model': 'text-embedding-3-small',
            'preset': c.PRESET_DIDACTIC, 'tone': c.TONE_NEUTRAL, 'length': c.LENGTH_MEDIUM,
            'language': c.LANGUAGE_PT_BR, 'answer_format': c.FORMAT_PROSE,
            'detail_level': c.DETAIL_INTERMEDIATE, 'extra_instructions': '',
        })
        self.assertEqual(NotebookSettings.objects.get(notebook=self.notebook).chat_model, 'gpt-4o-mini')

    def _payload(self, **overrides):
        data = {
            'chat_provider': c.PROVIDER_OPENAI, 'chat_model': 'gpt-4o-mini',
            'embedding_provider': c.PROVIDER_OPENAI, 'embedding_model': 'text-embedding-3-small',
            'preset': c.PRESET_DIDACTIC, 'tone': c.TONE_NEUTRAL, 'length': c.LENGTH_MEDIUM,
            'language': c.LANGUAGE_PT_BR, 'answer_format': c.FORMAT_PROSE,
            'detail_level': c.DETAIL_INTERMEDIATE, 'extra_instructions': '',
        }
        data.update(overrides)
        return data

    def test_changing_embedding_model_warns_about_reindexing(self):
        self.client.login(username='owner', password='pw')
        resp = self.client.post(self.url, self._payload(embedding_model='text-embedding-3-large'), follow=True)
        self.assertContains(resp, 'reindexadas')

    def test_keeping_embedding_model_does_not_warn(self):
        self.client.login(username='owner', password='pw')
        resp = self.client.post(self.url, self._payload(chat_model='gpt-4o'), follow=True)
        self.assertNotContains(resp, 'reindexadas')

    def test_refreshed_local_model_accepted(self):
        ProviderConfig.objects.create(user=self.owner, provider=c.PROVIDER_OLLAMA, model_list=['llama3.1'])
        self.client.login(username='owner', password='pw')
        self.client.post(self.url, {
            'chat_provider': c.PROVIDER_OLLAMA, 'chat_model': 'llama3.1',
            'embedding_provider': c.PROVIDER_OPENAI, 'embedding_model': 'text-embedding-3-small',
            'preset': c.PRESET_DIDACTIC, 'tone': c.TONE_NEUTRAL, 'length': c.LENGTH_MEDIUM,
            'language': c.LANGUAGE_PT_BR, 'answer_format': c.FORMAT_PROSE,
            'detail_level': c.DETAIL_INTERMEDIATE, 'extra_instructions': '',
        })
        settings = NotebookSettings.objects.get(notebook=self.notebook)
        self.assertEqual(settings.chat_model, 'llama3.1')
