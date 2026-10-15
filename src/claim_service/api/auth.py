"""Optional API-key guard for the REST and MCP endpoints.

Enabled only when the API_KEY environment variable is set. Health and version endpoints stay open
so that container and cloud health checks work without credentials.
"""

import hmac
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

# /openapi.json describes the API shape only (no user data). ChatGPT Actions must fetch it
# without credentials when a GPT is configured.
PUBLIC_PATHS = frozenset({"/api/health", "/api/version", "/openapi.json"})
Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


def _extract_key(headers: list[tuple[bytes, bytes]]) -> str:
    for name, value in headers:
        lowered = name.lower()
        if lowered == b"x-api-key":
            return value.decode("latin-1")
        if lowered == b"authorization":
            text = value.decode("latin-1")
            if text.lower().startswith("bearer "):
                return text[7:].strip()
    return ""


class ApiKeyMiddleware:
    """Reject HTTP requests without the configured key. Other scope types pass through."""

    def __init__(self, app: ASGIApp, api_key: str) -> None:
        self._app = app
        self._api_key = api_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in PUBLIC_PATHS:
            await self._app(scope, receive, send)
            return
        provided = _extract_key(scope.get("headers", []))
        if not hmac.compare_digest(provided.encode(), self._api_key.encode()):
            body = b'{"detail":"invalid or missing API key"}'
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode())],
            })
            await send({"type": "http.response.body", "body": body})
            return
        await self._app(scope, receive, send)
