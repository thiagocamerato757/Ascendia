from cryptography.fernet import Fernet
from django.test import TestCase, override_settings

from llm import crypto

TEST_FERNET_KEY = Fernet.generate_key().decode()


@override_settings(ASCENDIA_FERNET_KEY=TEST_FERNET_KEY)
class FernetTestCase(TestCase):
    """Base case that installs a valid Fernet key and resets the cached cipher."""

    def setUp(self):
        super().setUp()
        crypto._fernet.cache_clear()
        self.addCleanup(crypto._fernet.cache_clear)
