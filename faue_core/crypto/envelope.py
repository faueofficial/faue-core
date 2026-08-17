"""Envelope encryption.

Each sensitive column is encrypted with a data key, which is itself encrypted by
a rotatable master key. Rotation re-encrypts data keys, not rows — minutes
rather than hours.
"""

from __future__ import annotations


class EnvelopeEncryptor:
    def __init__(self, master_key: bytes) -> None:
        self._master_key = master_key

    def encrypt(self, plaintext: str) -> bytes:
        raise NotImplementedError

    def decrypt(self, ciphertext: bytes) -> str:
        raise NotImplementedError

    def rotate(self, ciphertext: bytes, new_master_key: bytes) -> bytes:
        """Re-wraps the data key only. The row's ciphertext is unchanged."""
        raise NotImplementedError
