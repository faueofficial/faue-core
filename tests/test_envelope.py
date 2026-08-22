"""Envelope encryption."""

import pytest

from faue_core.crypto.envelope import DecryptionError, EnvelopeEncryptor

KEY = "test-master-key-not-for-production"


def test_round_trips():
    enc = EnvelopeEncryptor(KEY)
    assert enc.decrypt(enc.encrypt("amara@example.com")) == "amara@example.com"


def test_ciphertext_does_not_contain_the_plaintext():
    enc = EnvelopeEncryptor(KEY)
    assert b"amara@example.com" not in enc.encrypt("amara@example.com")


def test_the_same_value_encrypts_differently_every_time():
    """A per-value data key and a random nonce. Deterministic ciphertext would
    let anyone with the database tell which users share an email domain."""
    enc = EnvelopeEncryptor(KEY)
    assert enc.encrypt("a@b.com") != enc.encrypt("a@b.com")


def test_another_master_key_cannot_decrypt():
    blob = EnvelopeEncryptor(KEY).encrypt("a@b.com")
    with pytest.raises(DecryptionError):
        EnvelopeEncryptor("a-different-master-key").decrypt(blob)


def test_tampering_is_detected():
    """AES-GCM is authenticated: a flipped byte fails rather than decrypting to
    something plausible."""
    enc = EnvelopeEncryptor(KEY)
    blob = bytearray(enc.encrypt("a@b.com"))
    blob[-1] ^= 0x01
    with pytest.raises(DecryptionError):
        enc.decrypt(bytes(blob))


@pytest.mark.parametrize("junk", [b"", b"nope", b"v9" + b"\x00" * 40])
def test_garbage_raises_rather_than_crashing(junk):
    with pytest.raises(DecryptionError):
        EnvelopeEncryptor(KEY).decrypt(junk)


def test_rotation_preserves_the_value():
    """Rotating re-wraps the data key. The value survives; the old master key
    no longer opens it."""
    old, new = EnvelopeEncryptor(KEY), "a-new-master-key"
    blob = old.encrypt("amara@example.com")
    rotated = old.rotate(blob, new)

    assert EnvelopeEncryptor(new).decrypt(rotated) == "amara@example.com"
    with pytest.raises(DecryptionError):
        old.decrypt(rotated)


def test_unicode_survives():
    enc = EnvelopeEncryptor(KEY)
    assert enc.decrypt(enc.encrypt("Adé Òjó — 어울림")) == "Adé Òjó — 어울림"


def test_an_empty_master_key_is_refused():
    with pytest.raises(ValueError):
        EnvelopeEncryptor("")


def test_a_short_master_key_still_works():
    """HKDF accepts any input, so a short key fails safely rather than deep
    inside the cipher with an unhelpful error."""
    enc = EnvelopeEncryptor("x")
    assert enc.decrypt(enc.encrypt("a@b.com")) == "a@b.com"
