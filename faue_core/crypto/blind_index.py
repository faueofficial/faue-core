"""Blind indexes.

Encrypted values cannot be searched, but login must find a user by email. An
HMAC of the normalised value is stored alongside the ciphertext, so equality
lookups stay index scans without storing plaintext.

The pepper lives in the secret store, separate from the database: a dump alone
yields neither the value nor the ability to test guesses at scale.
"""

from __future__ import annotations

import hashlib
import hmac
import unicodedata


def normalise(value: str) -> str:
    """Lower-case, strip, and NFKC-normalise before hashing.

    Getting this wrong makes login silently fail for a subset of users — the one
    who typed a trailing space, or whose keyboard produced a composed character.
    """
    return unicodedata.normalize("NFKC", value).strip().casefold()


def blind_index(value: str, pepper: bytes) -> str:
    if not pepper:
        raise ValueError("blind index pepper must not be empty")
    return hmac.new(pepper, normalise(value).encode(), hashlib.sha256).hexdigest()


def verify(value: str, index: str, pepper: bytes) -> bool:
    return hmac.compare_digest(blind_index(value, pepper), index)
