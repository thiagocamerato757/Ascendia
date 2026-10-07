"""Symmetric encryption at rest for provider API keys (spec §5, decision D6).

Uses Fernet (AES-128-CBC + HMAC) with a master key read from the
``ASCENDIA_FERNET_KEY`` environment variable. The plaintext key is never logged
and never returned to templates; no part of it is displayed after saving.
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class DecryptionError(Exception):
    """Raised when a stored ciphertext cannot be decrypted (wrong/rotated key)."""


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = getattr(settings, 'ASCENDIA_FERNET_KEY', None)
    if not key:
        raise ImproperlyConfigured(
            'ASCENDIA_FERNET_KEY is not set. Generate one with '
            '`python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"` and add it to your .env.'
        )
    if isinstance(key, str):
        key = key.encode()
    try:
        return Fernet(key)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            'ASCENDIA_FERNET_KEY is not a valid Fernet key (expected a 32-byte '
            'url-safe base64 string).'
        ) from exc


def encrypt(plaintext: str) -> str:
    """Encrypt a secret, returning url-safe base64 ciphertext."""
    if not plaintext:
        raise ValueError('Cannot encrypt an empty value.')
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a stored ciphertext back to plaintext."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError('Stored secret could not be decrypted.') from exc


def generate_key() -> str:
    """Generate a fresh Fernet master key (for .env setup / tests)."""
    return Fernet.generate_key().decode()
