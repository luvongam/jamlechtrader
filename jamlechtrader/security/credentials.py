"""Credential encryption and secure storage using Fernet + OS keyring."""

from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet
from loguru import logger

_KEYRING_SERVICE = "jamlechtrader"
_KEYRING_KEY_NAME = "encryption_key"


class CredentialManager:
    """Manages encrypted credentials.

    The Fernet encryption key is stored in the OS keyring (via the ``keyring``
    library).  Credentials themselves are encrypted/decrypted in memory and
    can be persisted however the caller chooses.
    """

    def __init__(self) -> None:
        self._fernet: Fernet | None = None

    def _ensure_key(self) -> Fernet:
        if self._fernet is not None:
            return self._fernet

        import keyring

        key = keyring.get_password(_KEYRING_SERVICE, _KEYRING_KEY_NAME)
        if key is None:
            key = Fernet.generate_key().decode()
            keyring.set_password(_KEYRING_SERVICE, _KEYRING_KEY_NAME, key)
            logger.info("Generated and stored new encryption key in OS keyring")

        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return self._fernet

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string and return base64-encoded ciphertext."""
        f = self._ensure_key()
        token = f.encrypt(plaintext.encode("utf-8"))
        return base64.urlsafe_b64encode(token).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a base64-encoded ciphertext string."""
        f = self._ensure_key()
        token = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
        return f.decrypt(token).decode("utf-8")

    def store_credential(self, name: str, value: str) -> None:
        """Encrypt and store a named credential in the OS keyring."""
        import keyring

        encrypted = self.encrypt(value)
        keyring.set_password(_KEYRING_SERVICE, f"cred_{name}", encrypted)
        logger.debug(f"Credential '{name}' stored securely")

    def get_credential(self, name: str) -> str | None:
        """Retrieve and decrypt a named credential from the OS keyring."""
        import keyring

        encrypted = keyring.get_password(_KEYRING_SERVICE, f"cred_{name}")
        if encrypted is None:
            return None
        return self.decrypt(encrypted)
