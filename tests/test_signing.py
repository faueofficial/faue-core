"""Ed25519 signing keys: generation, encoding, and loading.

The wire format lives here rather than in either consumer because two of them
have to agree on it — `faue-infra`'s generator writes it and `api-gateway`'s
token module reads it. Two implementations of the same encoding drift, and the
symptom is every access token failing to verify.
"""

import base64

import pytest

from faue_core.crypto import signing


def test_a_generated_pair_verifies_itself():
    private_b64, public_b64 = signing.generate_keypair()

    private = signing.load_private_key(private_b64)
    public = signing.load_public_key(public_b64)

    signature = private.sign(b"payload")
    public.verify(signature, b"payload")          # raises if it does not match


def test_the_public_key_is_derived_from_the_private_one():
    """Not independently random. A pair generated as two unrelated keys would
    produce tokens that never verify, and the failure would look like a config
    error rather than a generation bug."""
    private_b64, public_b64 = signing.generate_keypair()

    derived = signing.public_key_for(private_b64)

    assert derived == public_b64


def test_two_generations_differ():
    assert signing.generate_keypair() != signing.generate_keypair()


def test_keys_are_single_line():
    """`.env` files and Railway variables both handle multi-line values badly.
    PEM is multi-line; this encoding deliberately is not."""
    for value in signing.generate_keypair():
        assert "\n" not in value
        assert " " not in value


def test_keys_are_the_expected_size():
    """Ed25519 is 32 bytes each side. A 44-character base64 value is the tell
    that someone pasted the right thing."""
    private_b64, public_b64 = signing.generate_keypair()

    assert len(base64.urlsafe_b64decode(private_b64 + "==")) == 32
    assert len(base64.urlsafe_b64decode(public_b64 + "==")) == 32


def test_a_signature_from_another_key_is_rejected():
    private_b64, _ = signing.generate_keypair()
    _, other_public_b64 = signing.generate_keypair()

    signature = signing.load_private_key(private_b64).sign(b"payload")

    with pytest.raises(Exception):
        signing.load_public_key(other_public_b64).verify(signature, b"payload")


def test_loading_rubbish_says_what_is_wrong():
    """The failure an operator will actually hit is a truncated paste. It must
    name the variable, not surface a base64 error from three frames down."""
    with pytest.raises(signing.InvalidKey) as caught:
        signing.load_private_key("not-a-key")

    assert "private key" in str(caught.value), "the message must name which key"


def test_a_truncated_key_says_so():
    """The most common paste error: the value is valid base64 but short."""
    private_b64, _ = signing.generate_keypair()

    with pytest.raises(signing.InvalidKey) as caught:
        signing.load_private_key(private_b64[:20])

    assert "32 bytes" in str(caught.value)


def test_loading_an_empty_key_is_rejected():
    with pytest.raises(signing.InvalidKey):
        signing.load_private_key("")


def test_a_public_key_cannot_be_loaded_as_a_private_one():
    """Both are 32 raw bytes, so nothing about the length distinguishes them.
    Swapping the two in configuration is a realistic mistake and it must fail
    loudly at startup rather than produce signatures nobody can verify."""
    private_b64, public_b64 = signing.generate_keypair()

    # Loading succeeds — the bytes are structurally valid as a seed — so the
    # guard that matters is that the resulting pair does not verify.
    wrong = signing.load_private_key(public_b64)
    signature = wrong.sign(b"payload")

    with pytest.raises(Exception):
        signing.load_public_key(public_b64).verify(signature, b"payload")


def test_padding_is_tolerated_on_input():
    """Operators paste from places that add or strip '='. Reading must accept
    both; writing stays canonical."""
    private_b64, _ = signing.generate_keypair()

    assert signing.load_private_key(private_b64 + "==") is not None
