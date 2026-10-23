"""User identity protection: per-user API keys, PIN hashing and request-scoped credentials.

Per-user API/MCP keys are the primary credential over MCP HTTP: the raw key is shown once at issue
time and only its SHA-256 hash is stored. A valid `X-User-Key` binds the request to its owner and
replaces PIN entry for that account. Raw PINs are never stored or logged. Advanced single-user AI
clients can still pass `X-User-Id` and `X-User-Pin` headers so the user does not have to type them
in chat, while shared clients pass `user_id` and `pin` as tool/API parameters.
"""

import hashlib
import hmac
import secrets
from contextvars import ContextVar

PBKDF2_ITERATIONS = 120_000

_ctx_bound_user: ContextVar[str | None] = ContextVar("bound_user", default=None)
_ctx_header_pin: ContextVar[str | None] = ContextVar("header_pin", default=None)
_ctx_key_authenticated: ContextVar[str | None] = ContextVar(
    "key_authenticated_user", default=None
)


def set_request_identity(bound_user: str | None, header_pin: str | None) -> None:
    _ctx_bound_user.set(bound_user)
    _ctx_header_pin.set(header_pin)


def get_bound_user() -> str | None:
    return _ctx_bound_user.get()


def get_header_pin() -> str | None:
    return _ctx_header_pin.get()


def set_key_authenticated_user(user_id: str | None) -> None:
    """Record that a per-user API key proved this user's identity for the current request."""
    _ctx_key_authenticated.set(user_id)


def get_key_authenticated_user() -> str | None:
    """User id proven by a per-user API key in the current request, if any."""
    return _ctx_key_authenticated.get()


def generate_api_key() -> str:
    """Return a fresh unguessable per-user API key (shown once at issue time)."""
    return secrets.token_urlsafe(48)


def hash_api_key(key: str) -> str:
    """SHA-256 hex digest of an API key; the only form ever stored or logged."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def api_key_prefix(key: str) -> str:
    """Short display prefix so operators can identify a key without revealing it."""
    return key[:8]


def hash_pin(pin: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", pin.encode("utf-8"), salt.encode("ascii"), PBKDF2_ITERATIONS
    )
    return f"{salt}${digest.hex()}"


def verify_pin(pin: str, stored_hash: str) -> bool:
    if "$" not in stored_hash:
        return False
    salt, expected_hex = stored_hash.split("$", 1)
    digest = hashlib.pbkdf2_hmac(
        "sha256", pin.encode("utf-8"), salt.encode("ascii"), PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(digest.hex(), expected_hex)
