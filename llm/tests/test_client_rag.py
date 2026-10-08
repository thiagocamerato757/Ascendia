"""Client features used by RAG: streaming, batched embeddings, local endpoints."""
import math

from django.contrib.auth.models import User
from django.test import override_settings

from llm import client
from llm import constants as c
from llm.models import NotebookSettings, ProviderConfig, ProviderCredential
from llm.providers import FakeProvider, ProviderError, hashing_embedding
from workspace.models import Notebook

from . import FernetTestCase


class ClientRagTests(FernetTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('rag', password='pw')
        self.notebook = Notebook.objects.create(user=self.user, title='NB')
        self.nb_settings = NotebookSettings.objects.create(notebook=self.notebook)
        for provider in (c.PROVIDER_OPENAI, c.PROVIDER_NVIDIA):
            cred = ProviderCredential(user=self.user, provider=provider)
            cred.set_key(f'key-{provider}')
            cred.save()

    def tearDown(self):
        client.set_provider_override(None)
        super().tearDown()

    def test_stream_yields_deltas_then_result(self):
        client.set_provider_override(FakeProvider(reply='uma resposta curta [1]'))
        stream = client.stream_chat(self.nb_settings, [{'role': 'user', 'content': 'oi'}])
        deltas = list(stream)
        self.assertEqual(''.join(deltas), 'uma resposta curta [1]')
        self.assertGreater(len(deltas), 1)
        self.assertEqual(stream.result.text, 'uma resposta curta [1]')
        self.assertEqual(stream.result.model, self.nb_settings.chat_model)

    def test_failure_mid_stream_reaches_caller_without_retry(self):
        fake = FakeProvider(reply='a b c d', fail_with='caiu', fail_after_tokens=2)
        client.set_provider_override(fake)
        stream = client.stream_chat(self.nb_settings, [{'role': 'user', 'content': 'oi'}])
        received = []
        with self.assertRaises(ProviderError):
            for delta in stream:
                received.append(delta)
        self.assertEqual(len(received), 2)
        self.assertIsNone(stream.result)

    @override_settings(ASCENDIA_EMBED_BATCH_SIZE=2)
    def test_embed_sends_batches_and_merges_results(self):
        fake = FakeProvider()
        client.set_provider_override(fake)
        result = client.embed(self.nb_settings, ['a', 'b', 'c', 'd', 'e'])
        self.assertEqual([len(call['texts']) for call in fake.embed_calls], [2, 2, 1])
        self.assertEqual(len(result.vectors), 5)

    def test_input_type_only_for_providers_that_need_it(self):
        fake = FakeProvider()
        client.set_provider_override(fake)
        client.embed(self.nb_settings, ['x'], purpose='query')
        self.assertIsNone(fake.last_embed_call['input_type'])  # OpenAI
        self.nb_settings.embedding_provider = c.PROVIDER_NVIDIA
        client.embed(self.nb_settings, ['x'], purpose='query')
        self.assertEqual(fake.last_embed_call['input_type'], 'query')
        client.embed(self.nb_settings, ['x'])
        self.assertEqual(fake.last_embed_call['input_type'], 'passage')

    def test_unknown_purpose_is_rejected(self):
        with self.assertRaises(ValueError):
            client.embed(self.nb_settings, ['x'], purpose='document')

    def test_local_server_url_reaches_chat_and_embed(self):
        ProviderConfig.objects.create(user=self.user, provider=c.PROVIDER_OLLAMA, base_url='http://localhost:11434')
        self.nb_settings.chat_provider = c.PROVIDER_OLLAMA
        self.nb_settings.chat_model = 'ollama/llama3.1'
        self.nb_settings.embedding_provider = c.PROVIDER_OLLAMA
        self.nb_settings.embedding_model = 'ollama/nomic-embed-text'
        fake = FakeProvider()
        client.set_provider_override(fake)
        client.chat(self.nb_settings, [{'role': 'user', 'content': 'oi'}])
        self.assertEqual(fake.last_chat_call['api_base'], 'http://localhost:11434')
        self.assertIsNone(fake.last_chat_call['api_key'])
        client.embed(self.nb_settings, ['x'])
        self.assertEqual(fake.last_embed_call['api_base'], 'http://localhost:11434')

    def test_cloud_providers_use_default_endpoint(self):
        fake = FakeProvider()
        client.set_provider_override(fake)
        client.chat(self.nb_settings, [{'role': 'user', 'content': 'oi'}])
        self.assertIsNone(fake.last_chat_call['api_base'])
        self.assertEqual(fake.last_chat_call['api_key'], 'key-openai')


class HashingEmbeddingTests(FernetTestCase):
    def test_similar_texts_are_closer(self):
        def cos(a, b):
            return sum(x * y for x, y in zip(a, b))

        q = hashing_embedding('fotossíntese em plantas')
        near = hashing_embedding('A fotossíntese acontece nas plantas verdes.')
        far = hashing_embedding('Revolução Francesa e a queda da Bastilha.')
        self.assertGreater(cos(q, near), cos(q, far))
        self.assertAlmostEqual(math.sqrt(sum(v * v for v in near)), 1.0)


class StartupTests(FernetTestCase):
    def test_litellm_is_loaded_at_startup_not_inside_answer_threads(self):
        # Loaded lazily, its first import happened inside an answer-generation thread
        # and deadlocked on Python's import lock (see llm/apps.py).
        import sys

        self.assertIn('litellm', sys.modules)
