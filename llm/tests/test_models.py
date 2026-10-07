from django.contrib.auth.models import User

from llm import constants as c
from llm.models import NotebookSettings, ProviderCredential
from workspace.models import Notebook

from . import FernetTestCase


class ProviderCredentialTests(FernetTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('alice', password='x')

    def test_set_key_stores_only_ciphertext(self):
        cred = ProviderCredential(user=self.user, provider=c.PROVIDER_OPENAI)
        cred.set_key('sk-openai-abcd9876')
        cred.save()
        self.assertNotIn('sk-openai', cred.ciphertext)
        self.assertNotIn('9876', cred.ciphertext)
        self.assertFalse(hasattr(cred, 'last_four'))
        self.assertEqual(cred.get_key(), 'sk-openai-abcd9876')

    def test_str_does_not_leak_key(self):
        cred = ProviderCredential(user=self.user, provider=c.PROVIDER_OPENAI)
        cred.set_key('sk-secret-value-0000')
        self.assertNotIn('secret', str(cred))
        self.assertNotIn('0000', str(cred))


class NotebookSettingsTests(FernetTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('bob', password='x')
        self.notebook = Notebook.objects.create(user=self.user, title='NB')

    def test_defaults(self):
        settings = NotebookSettings.objects.create(notebook=self.notebook)
        self.assertEqual(settings.chat_provider, c.PROVIDER_OPENAI)
        self.assertEqual(settings.language, c.LANGUAGE_PT_BR)
        self.assertEqual(settings.preset, c.PRESET_DIDACTIC)

    def test_style_spec_mirrors_fields(self):
        settings = NotebookSettings.objects.create(
            notebook=self.notebook, tone=c.TONE_FORMAL, extra_instructions='oi',
        )
        spec = settings.style_spec
        self.assertEqual(spec.tone, c.TONE_FORMAL)
        self.assertEqual(spec.extra_instructions, 'oi')

    def test_credential_for_chat(self):
        settings = NotebookSettings.objects.create(notebook=self.notebook, chat_provider=c.PROVIDER_OPENAI)
        self.assertIsNone(settings.credential_for(settings.chat_provider))
        cred = ProviderCredential(user=self.user, provider=c.PROVIDER_OPENAI)
        cred.set_key('sk-1234')
        cred.save()
        self.assertEqual(settings.credential_for(settings.chat_provider), cred)
