from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from llm import crypto

from . import FernetTestCase


class CryptoTests(FernetTestCase):
    def test_roundtrip(self):
        token = crypto.encrypt('sk-super-secret-1234')
        self.assertNotIn('sk-super-secret', token)
        self.assertEqual(crypto.decrypt(token), 'sk-super-secret-1234')

    def test_ciphertext_is_not_deterministic(self):
        self.assertNotEqual(crypto.encrypt('same'), crypto.encrypt('same'))

    def test_encrypt_empty_raises(self):
        with self.assertRaises(ValueError):
            crypto.encrypt('')

    def test_decrypt_with_wrong_key_raises(self):
        token = crypto.encrypt('secret-value')
        crypto._fernet.cache_clear()
        with override_settings(ASCENDIA_FERNET_KEY=Fernet.generate_key().decode()):
            with self.assertRaises(crypto.DecryptionError):
                crypto.decrypt(token)

    def test_missing_key_raises(self):
        crypto._fernet.cache_clear()
        with override_settings(ASCENDIA_FERNET_KEY=''):
            with self.assertRaises(ImproperlyConfigured):
                crypto.encrypt('x')
