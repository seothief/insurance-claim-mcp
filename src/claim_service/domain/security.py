"""User identity protection: PIN hashing (PBKDF2-HMAC-SHA256) and request-scoped credentials.

Raw PINs are never stored or logged. Advanced single-user AI clients (Cline, Gemini CLI, Claude)
can pass `X-User-Id` and `X-User-Pin` headers so the user does not have to type them in chat,
while shared clients pass `user_id` and `pin` as tool/API parameters.
"""

import hashlib
import hmac
import secrets
from contextvars import ContextVar

PBKDF2_ITERATIONS = 120_000

_ctx_bound_user: ContextVar[str | None] = ContextVar("bound_user", default=None)
_ctx_header_pin: ContextVar[str | None] = ContextVar("header_pin", default=None)


def set_request_identity(bound_user: str | None, header_pin: str | None) -> None:
    _ctx_bound_user.set(bound_user)
    _ctx_header_pin.set(header_pin)


def get_bound_user() -> str | None:
    return _ctx_bound_user.get()


def get_header_pin() -> str | None:
    return _ctx_header_pin.get()


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
