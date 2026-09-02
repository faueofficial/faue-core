"""Ed25519 keys for signing user access tokens.

The encoding lives here because two repositories have to agree on it:
`faue-infra`'s generator writes it and `api-gateway` reads it. Two
implementations of one format drift, and the symptom is every access token
failing to verify at once.

**Format:** base64url of the 32 raw key bytes, on a single line.

PEM would be the conventional choice and is rejected on purpose: it is
multi-line, and both `.env` files and Railway environment variables handle
embedded newlines badly enough that the value arrives mangled and the error
appears somewhere unrelated. 44 characters on one line cannot be mangled.
"""

from __future__ import annotations

import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

__all__ = [
    "InvalidKey",
    "InvalidSignature",
    "generate_keypair",
    "load_private_key",
    "load_public_key",
    "public_key_for",
]

KEY_BYTES = 32


class InvalidKey(ValueError):
    """A configured key could not be decoded. Almost always a truncated paste."""


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(value: str, *, name: str) -> bytes:
    if not value:
        raise InvalidKey(f"{name} is empty")

    # Operators paste from places that add or strip '='. Accept either on the
    # way in; what this module writes stays canonical.
    padded = value + "=" * (-len(value) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded)
    except Exception as exc:
        raise InvalidKey(f"{name} is not valid base64url: {exc}") from exc

    if len(raw) != KEY_BYTES:
        raise InvalidKey(
            f"{name} decoded to {len(raw)} bytes; Ed25519 keys are {KEY_BYTES} bytes. "
            "The usual cause is a truncated copy."
        )
    return raw


def generate_keypair() -> tuple[str, str]:
    """A fresh (private, public) pair, both base64url on one line.

    The public key is *derived* from the private one rather than generated
    beside it — a pair of unrelated keys would produce tokens that never verify,
    and that reads as a configuration error rather than a generation bug.
    """
    private = Ed25519PrivateKey.generate()
    return _encode(_private_bytes(private)), _encode(_public_bytes(private))


def public_key_for(private_b64: str) -> str:
    """The public half of a configured private key.

    Lets a deployment carry only the signing key and derive the rest, and lets
    an operator check that a pair actually belongs together.
    """
    return _encode(_public_bytes(load_private_key(private_b64)))


def load_private_key(value: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(_decode(value, name="private key"))


def load_public_key(value: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(_decode(value, name="public key"))


def _private_bytes(key: Ed25519PrivateKey) -> bytes:
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat,
    )

    return key.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )


def _public_bytes(key: Ed25519PrivateKey) -> bytes:
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    return key.public_key().public_bytes(
        encoding=Encoding.Raw, format=PublicFormat.Raw
    )
