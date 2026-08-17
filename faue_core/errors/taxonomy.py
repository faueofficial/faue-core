"""Domain exception taxonomy.

Modules raise these; the boundary translates them once into RFC 7807 problem
documents. No module imports HTTPException, which is what keeps business logic
callable from a worker as well as from a request.

`problem_type` values are the same strings documented in
docs/40-frontend/error-model.md, so the contract cannot drift from the code.
"""

from __future__ import annotations


class FaueError(Exception):
    problem_type: str = "internal_error"
    status: int = 500
    title: str = "Internal error"

    def __init__(self, detail: str | None = None, *, field: str | None = None) -> None:
        super().__init__(detail or self.title)
        self.detail = detail
        self.field = field


# --- auth -------------------------------------------------------------------
class Unauthenticated(FaueError):
    problem_type, status, title = "unauthenticated", 401, "Not signed in"


class TokenExpired(FaueError):
    problem_type, status, title = "token_expired", 401, "Session expired"


class RefreshReuseDetected(FaueError):
    """Terminal. The client must sign out, never retry."""
    problem_type, status, title = "refresh_reuse_detected", 401, "Session revoked"


class Forbidden(FaueError):
    problem_type, status, title = "forbidden", 403, "Not permitted"


class ConsentMissing(FaueError):
    """Not an error in product terms — the client shows the consent surface."""
    problem_type, status, title = "consent_required", 403, "Consent required"


class AgeRestricted(FaueError):
    problem_type, status, title = "age_restricted", 403, "Age restricted"


# --- magic link -------------------------------------------------------------
class LinkExpired(FaueError):
    problem_type, status, title = "link_expired", 410, "Link expired"


class LinkAlreadyUsed(FaueError):
    problem_type, status, title = "link_already_used", 410, "Link already used"


class DeviceCodeRequired(FaueError):
    problem_type, status, title = "device_code_required", 409, "Confirm on your device"


class DeviceCodeInvalid(FaueError):
    problem_type, status, title = "device_code_invalid", 400, "Incorrect code"


# --- validation -------------------------------------------------------------
class ValidationFailed(FaueError):
    problem_type, status, title = "validation_failed", 422, "Invalid request"


class UsernameTaken(FaueError):
    problem_type, status, title = "username_taken", 409, "Username taken"


class UnsupportedMediaType(FaueError):
    problem_type, status, title = "unsupported_media_type", 415, "Unsupported file type"


class PayloadTooLarge(FaueError):
    problem_type, status, title = "payload_too_large", 413, "File too large"


# --- resources --------------------------------------------------------------
class NotFound(FaueError):
    problem_type, status, title = "not_found", 404, "Not found"


class AssetNotReady(FaueError):
    problem_type, status, title = "asset_not_ready", 409, "Still processing"


class AssetRejected(FaueError):
    problem_type, status, title = "asset_rejected", 422, "Image rejected"


class Conflict(FaueError):
    problem_type, status, title = "conflict", 409, "Conflict"


# --- generation -------------------------------------------------------------
class EmptyPool(FaueError):
    """Expected outcome for a near-empty vault, not a fault. Does not page."""
    problem_type, status, title = "empty_pool", 422, "Not enough to work with"


class BudgetExceeded(FaueError):
    problem_type, status, title = "budget_exceeded", 429, "Daily limit reached"


class GuardrailBlocked(FaueError):
    """Expected outcome for bad input, not a fault. Does not page."""
    problem_type, status, title = "guardrail_blocked", 422, "Cannot process that"


class ModelUnavailable(FaueError):
    problem_type, status, title = "model_unavailable", 503, "Temporarily unavailable"


class RenderFailed(FaueError):
    problem_type, status, title = "render_failed", 500, "Could not create this look"


# --- infrastructure ---------------------------------------------------------
class RateLimited(FaueError):
    problem_type, status, title = "rate_limited", 429, "Too many requests"


class ServiceUnavailable(FaueError):
    problem_type, status, title = "service_unavailable", 503, "Temporarily unavailable"


class Maintenance(FaueError):
    problem_type, status, title = "maintenance", 503, "Under maintenance"
