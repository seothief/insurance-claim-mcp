"""Per-user API-key guard for the MCP HTTP endpoint.

Every protected request must present a per-user key in the `X-User-Key` header. The raw key is
never stored or logged; only its SHA-256 hash is looked up in the database. A valid key binds the
request to its owner (replacing PIN entry for that account) and rejects any other `X-User-Id`.
Health and version endpoints stay open so container and cloud health checks work without
credentials.
"""

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from starlette.concurrency import run_in_threadpool

from claim_service.domain.security import (
    set_key_authenticated_user,
    set_request_identity,
)
from claim_service.runtime import get_service

PUBLIC_PATHS = frozenset(
    {
        "/api/health",
        "/api/version",
    }
)
Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


def _extract_headers(
    headers: list[tuple[bytes, bytes]],
) -> tuple[str, str | None, str | None]:
    user_key = ""
    bound_user: str | None = None
    header_pin: str | None = None
    for name, value in headers:
        lowered = name.lower()
        if lowered == b"x-user-key":
            user_key = value.decode("latin-1")
        elif lowered == b"authorization":
            text = value.decode("latin-1")
            if text.lower().startswith("bearer "):
                user_key = text[7:].strip()
        elif lowered == b"x-user-id":
            bound_user = value.decode("latin-1").strip() or None
        elif lowered == b"x-user-pin":
            header_pin = value.decode("latin-1").strip() or None
    return user_key, bound_user, header_pin


class ApiKeyMiddleware:
    """Resolve the X-User-Key to its owner and bind the request to that user.

    A per-user key is a full credential: it authenticates its owner and replaces PIN input.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        # Avoid Starlette's 307 /mcp -> /mcp/ redirect, which downgrades https to http behind
        # Cloud Run's proxy and is rejected by strict MCP clients.
        if scope.get("path") == "/mcp":
            scope["path"] = "/mcp/"
        path = str(scope.get("path") or "")
        if path in PUBLIC_PATHS:
            await self._app(scope, receive, send)
            return
        provided_key, requested_user, header_pin = _extract_headers(scope.get("headers", []))
        owner = await run_in_threadpool(self._resolve_owner, provided_key)
        if owner is None:
            await self._reject(send)
            return
        if requested_user and requested_user != owner:
            await self._reject(send)
            return
        # A valid key is the account's credential: it replaces PIN entry for this request.
        set_key_authenticated_user(owner)
        set_request_identity(owner, header_pin)
        try:
            await self._app(scope, receive, send)
        finally:
            set_request_identity(None, None)
            set_key_authenticated_user(None)

    def _resolve_owner(self, provided_key: str) -> str | None:
        if not provided_key:
            return None
        try:
            return get_service().authenticate_api_key(provided_key)
        except Exception:
            # Fail closed: any DB/engine error must never be treated as an authenticated user.
            return None

    @staticmethod
    async def _reject(send: Send) -> None:
        body = b'{"error":"invalid or missing API key"}'
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": body})
