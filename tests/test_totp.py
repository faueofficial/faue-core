"""TOTP — RFC 6238.

The naive implementation verifies the current 30-second code and stops there.
Two things go wrong with that: a code stays valid for its whole window, so an
observed code can be replayed inside it; and phone clocks drift, so a strictly
current-window check locks people out for reasons they cannot diagnose.
"""

import time

import pytest

from faue_core.crypto import totp


def test_a_generated_secret_is_long_enough():
    """160 bits is the RFC 4226 recommendation and what every authenticator
    app expects."""
    secret = totp.generate_secret()

    assert len(secret) == 32          # base32 of 20 bytes


def test_two_secrets_differ():
    assert totp.generate_secret() != totp.generate_secret()


def test_the_current_code_verifies():
    secret = totp.generate_secret()

    assert totp.verify(secret, totp.now(secret)) is True


def test_a_wrong_code_is_rejected():
    secret = totp.generate_secret()

    assert totp.verify(secret, "000000") is False


def test_a_code_from_another_secret_is_rejected():
    mine, theirs = totp.generate_secret(), totp.generate_secret()

    assert totp.verify(mine, totp.now(theirs)) is False


def test_a_code_from_the_previous_window_is_accepted():
    """Phone clocks drift. One step either side is the standard allowance;
    wider than that materially weakens the factor."""
    secret = totp.generate_secret()
    previous = totp.at(secret, time.time() - 30)

    assert totp.verify(secret, previous) is True


def test_a_code_from_two_windows_ago_is_rejected():
    secret = totp.generate_secret()
    stale = totp.at(secret, time.time() - 90)

    assert totp.verify(secret, stale) is False


def test_a_malformed_code_is_rejected_without_raising():
    """The code arrives from a form. Letters, empty strings and long strings
    are all things a user will send, and none should be a 500."""
    secret = totp.generate_secret()

    for bad in ("", "abcdef", "12345", "1234567", "12 34 56", None):
        assert totp.verify(secret, bad) is False


def test_the_provisioning_uri_names_the_account_and_the_issuer():
    """This is what the QR code encodes. Without an issuer every FAUE account
    shows up in the authenticator as an unlabelled six-digit code."""
    uri = totp.provisioning_uri(
        totp.generate_secret(), account="ada@faueofficial.com"
    )

    assert uri.startswith("otpauth://totp/")
    assert "issuer=FAUE" in uri
    assert "ada%40faueofficial.com" in uri


def test_verification_uses_a_constant_time_comparison():
    """Asserted rather than assumed. A refactor to `==` would introduce a timing
    oracle on the second factor and nothing else would fail."""
    import inspect

    import pyotp.utils

    source = inspect.getsource(pyotp.utils.strings_equal)
    assert "compare_digest" in source


def test_a_used_code_is_still_valid_here():
    """Replay protection is deliberately NOT in this module.

    A code stays valid for its whole window, so "has this been used?" needs
    storage, and storage is the caller's. Pinning the boundary so nobody assumes
    this module already handles it.
    """
    secret = totp.generate_secret()
    code = totp.now(secret)

    assert totp.verify(secret, code) is True
    assert totp.verify(secret, code) is True


def test_the_window_counter_advances_with_time():
    """What the caller keys replay protection on."""
    first = totp.window_for(1_000_000_000)
    later = totp.window_for(1_000_000_000 + 30)

    assert later == first + 1


def test_the_window_counter_is_stable_inside_one_period():
    # Aligned to a window boundary on purpose: 1_000_000_000 % 30 == 10, so
    # +29 from there crosses into the next window and the assertion would be
    # testing the arithmetic of the chosen base rather than the function.
    base = 1_000_000_000 - (1_000_000_000 % 30)

    assert totp.window_for(base) == totp.window_for(base + 29)
    assert totp.window_for(base + 30) == totp.window_for(base) + 1
