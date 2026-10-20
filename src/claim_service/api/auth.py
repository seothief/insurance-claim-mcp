"""Optional API-key guard for the REST and MCP endpoints.

Enabled only when the API_KEY environment variable is set. Health and version endpoints stay open
so that container and cloud health checks work without credentials.
"""

import hmac
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from claim_service.domain.security import set_request_identity

# /openapi.json describes the API shape only (no user data). ChatGPT Actions must fetch it
# without credentials when a GPT is configured. The intro pages are static, secret-free text.
PUBLIC_PATHS = frozenset(
    {
        "/api/health",
        "/api/version",
        "/openapi.json",
        "/",
        "/llms.txt",
        "/about.md",
        "/start",
        "/start.md",
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
    api_key = ""
    bound_user: str | None = None
    header_pin: str | None = None
    for name, value in headers:
        lowered = name.lower()
        if lowered == b"x-api-key":
            api_key = value.decode("latin-1")
        elif lowered == b"authorization":
            text = value.decode("latin-1")
            if text.lower().startswith("bearer "):
                api_key = text[7:].strip()
        elif lowered == b"x-user-id":
            bound_user = value.decode("latin-1").strip() or None
        elif lowered == b"x-user-pin":
            header_pin = value.decode("latin-1").strip() or None
    return api_key, bound_user, header_pin


class ApiKeyMiddleware:
    """Reject HTTP requests without the configured key. Other scope types pass through."""

    def __init__(self, app: ASGIApp, api_key: str) -> None:
        self._app = app
        self._api_key = api_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        # Avoid Starlette's 307 /mcp -> /mcp/ redirect, which downgrades https to http behind
        # Cloud Run's proxy and is rejected by strict MCP clients.
        if scope.get("path") == "/mcp":
            scope["path"] = "/mcp/"
        path = str(scope.get("path") or "")
        if path in PUBLIC_PATHS or path.startswith("/ai/"):
            await self._app(scope, receive, send)
            return
        provided, requested_user, header_pin = _extract_headers(scope.get("headers", []))
        server_key_valid = bool(self._api_key) and hmac.compare_digest(
            provided.encode(), self._api_key.encode()
        )
        if self._api_key and not server_key_valid:
            body = b'{"detail":"invalid or missing API key"}'
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode())],
            })
            await send({"type": "http.response.body", "body": body})
            return
        set_request_identity(requested_user, header_pin)
        try:
            await self._app(scope, receive, send)
        finally:
            set_request_identity(None, None)
