"""Envelope encryption.

Each value gets its own random **data key**. The data key is encrypted with the
**master key** and stored alongside the ciphertext.

That indirection is the point: rotating the master key re-encrypts data keys,
not rows — minutes rather than hours, and no table rewrite on a live database.

Wire format, all one opaque blob:

    b"v1" || wrapped_key_len(1) || wrapped_data_key || nonce(12) || ciphertext

The version prefix is what makes a future algorithm change decryptable rather
than a migration.
"""

from __future__ import annotations

import os
from typing import Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

VERSION: Final = b"v1"
NONCE_BYTES: Final = 12
KEY_BYTES: Final = 32


class DecryptionError(Exception):
    """Ciphertext could not be decrypted — wrong key, or tampering."""


def _derive_master(master_key: str | bytes) -> bytes:
    """Derive a fixed-length key from whatever the operator configured.

    Without this, a short or non-random master key string fails deep inside the
    cipher with an unhelpful error. HKDF accepts any input and always yields 32
    bytes.
    """
    raw = master_key.encode() if isinstance(master_key, str) else master_key
    if not raw:
        raise ValueError("master key must not be empty")
    return HKDF(
        algorithm=hashes.SHA256(), length=KEY_BYTES,
        salt=None, info=b"faue-envelope-v1",
    ).derive(raw)


class EnvelopeEncryptor:
    def __init__(self, master_key: str | bytes) -> None:
        self._master = AESGCM(_derive_master(master_key))

    def encrypt(self, plaintext: str) -> bytes:
        data_key = os.urandom(KEY_BYTES)

        wrap_nonce = os.urandom(NONCE_BYTES)
        wrapped = wrap_nonce + self._master.encrypt(wrap_nonce, data_key, VERSION)

        nonce = os.urandom(NONCE_BYTES)
        ciphertext = AESGCM(data_key).encrypt(nonce, plaintext.encode(), VERSION)

        return VERSION + bytes([len(wrapped)]) + wrapped + nonce + ciphertext

    def decrypt(self, blob: bytes) -> str:
        try:
            if not blob.startswith(VERSION):
                raise DecryptionError("unknown envelope version")

            offset = len(VERSION)
            wrapped_len = blob[offset]
            offset += 1

            wrapped = blob[offset : offset + wrapped_len]
            offset += wrapped_len

            data_key = self._master.decrypt(
                wrapped[:NONCE_BYTES], wrapped[NONCE_BYTES:], VERSION
            )
            nonce = blob[offset : offset + NONCE_BYTES]
            ciphertext = blob[offset + NONCE_BYTES :]

            return AESGCM(data_key).decrypt(nonce, ciphertext, VERSION).decode()
        except (InvalidTag, IndexError, ValueError) as exc:
            raise DecryptionError("could not decrypt value") from exc

    def rotate(self, blob: bytes, new_master_key: str | bytes) -> bytes:
        """Re-wrap the data key under a new master key.

        The row's ciphertext is untouched — which is what makes rotation cheap
        enough to actually do on schedule.
        """
        plaintext = self.decrypt(blob)
        return EnvelopeEncryptor(new_master_key).encrypt(plaintext)


#: Process-wide encryptor, configured once at startup. The SQLAlchemy type
#: decorator has no access to application settings, so it reads this.
_configured: EnvelopeEncryptor | None = None


def configure(master_key: str | bytes) -> None:
    global _configured
    _configured = EnvelopeEncryptor(master_key)


def get_encryptor() -> EnvelopeEncryptor:
    if _configured is None:
        raise RuntimeError(
            "envelope encryption is not configured.\n"
            "Call faue_core.crypto.configure(ENCRYPTION_MASTER_KEY) at startup — "
            "app factory, worker entrypoint, or test fixture."
        )
    return _configured
