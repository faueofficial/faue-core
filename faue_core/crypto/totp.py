"""Time-based one-time passwords (RFC 6238).

The second factor on admin accounts. The first is a magic link, which arrives by
email — so without this, a compromised inbox alone is admin access to everyone's
PII. TOTP requires the physical device holding the secret, which is a genuinely
different place from the inbox.

Chosen over SMS deliberately: SIM swaps are common in the launch market, and SMS
costs money per message. TOTP is offline, free, and works on any authenticator.

Replay protection is **not** here. A code stays valid for its whole window, so
"has this code already been used?" needs storage the caller owns — see
`api-gateway`'s admin auth, which holds it in Redis.
"""

from __future__ import annotations

import time

import pyotp

#: Two things the authenticator shows the user. Without an issuer, every FAUE
#: account appears in their app as an unlabelled six-digit code beside every
#: other unlabelled six-digit code.
ISSUER = "FAUE"

DIGITS = 6
PERIOD_SECONDS = 30

#: How many 30-second steps either side of now to accept.
#:
#: 1 means a code stays usable for roughly 90 seconds. Phone clocks drift, and a
#: strictly-current check locks people out for a reason they cannot diagnose or
#: fix. Wider than 1 materially weakens the factor, so this is the standard
#: allowance and not a dial to turn up when someone complains.
DRIFT_WINDOWS = 1


def generate_secret() -> str:
    """A fresh base32 secret. 160 bits, per RFC 4226."""
    return pyotp.random_base32()


def _totp(secret: str) -> pyotp.TOTP:
    return pyotp.TOTP(secret, digits=DIGITS, interval=PERIOD_SECONDS)


def now(secret: str) -> str:
    """The code for the current window. Tests and enrolment confirmation."""
    return _totp(secret).now()


def at(secret: str, moment: float) -> str:
    """The code for an arbitrary moment — used to exercise drift."""
    return _totp(secret).at(moment)


def verify(secret: str, code: str | None) -> bool:
    """Whether the code is valid now or one window either side.

    Never raises. The code arrives from a form, so letters, empty strings and
    over-long input are all things a person will actually send, and none of them
    is a server error.
    """
    if not code or not isinstance(code, str):
        return False

    candidate = code.strip().replace(" ", "")
    if len(candidate) != DIGITS or not candidate.isdigit():
        return False

    # pyotp compares with hmac.compare_digest, so this is not a timing oracle.
    return _totp(secret).verify(candidate, valid_window=DRIFT_WINDOWS)


def window_for(moment: float | None = None) -> int:
    """The counter this moment falls in.

    The caller stores `(admin_id, window, code)` to make a used code
    unreplayable for the rest of its life — which is the piece RFC 6238 leaves
    to the implementer.
    """
    return int((moment if moment is not None else time.time()) // PERIOD_SECONDS)


def provisioning_uri(secret: str, *, account: str) -> str:
    """The `otpauth://` URI a QR code encodes.

    Shown once at enrolment. It contains the secret, so it must never be logged,
    stored, or re-displayed after the account is enrolled.
    """
    return _totp(secret).provisioning_uri(name=account, issuer_name=ISSUER)
