"""FastAPI application with the MCP server mounted at /mcp.

The MCP sub-app's lifespan must be combined into the FastAPI lifespan,
otherwise its streamable-HTTP session manager is never initialised.
"""

import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastmcp.utilities.lifespan import combine_lifespans

from claim_service.api.ai_bridge import build_user_context_json
from claim_service.api.ai_bridge import router as ai_router
from claim_service.api.auth import ApiKeyMiddleware
from claim_service.api.routes import router as api_router
from claim_service.config import get_settings
from claim_service.intro import build_html, build_markdown
from claim_service.mcp.server import mcp
from claim_service.runtime import init_runtime
from claim_service.start_guide import build_start_html, build_start_markdown

APP_VERSION = os.environ.get("APP_VERSION", "local")
MCP_PATH = "/mcp"

mcp_app = mcp.http_app(path="/", stateless_http=True)


def _db_lifespan(database_url: str | None) -> Callable[[FastAPI], Any]:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        init_runtime(database_url)
        yield

    return lifespan


_AI_HTML_BOTS = ("chatgpt-user", "oai-searchbot", "claude-web", "claudebot", "perplexity")


def _is_ai_html_reader(request: Request) -> bool:
    ua = (request.headers.get("user-agent") or "").lower()
    return any(bot in ua for bot in _AI_HTML_BOTS)


def _resolve_base_url(request: Request, configured_base_url: str) -> str:
    host = (request.headers.get("host") or "").strip()
    if (
        host
        and host not in ("testserver", "localhost")
        and not host.startswith(("127.0.0.1", "localhost:"))
    ):
        proto = (request.headers.get("x-forwarded-proto") or "https").split(",")[0].strip()
        return f"{proto}://{host}"
    return configured_base_url


def create_app(database_url: str | None = None) -> FastAPI:
    base_url = get_settings().public_base_url.strip().rstrip("/")
    app = FastAPI(
        title="Insurance Claim MCP Service",
        version=APP_VERSION,
        lifespan=combine_lifespans(_db_lifespan(database_url), mcp_app.lifespan),
        servers=[{"url": base_url}] if base_url else None,
    )

    @app.get("/robots.txt", include_in_schema=False, response_class=PlainTextResponse)
    def robots_txt() -> PlainTextResponse:
        return PlainTextResponse(
            "User-agent: *\nAllow: /\n", media_type="text/plain; charset=utf-8"
        )

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/api/health", include_in_schema=False)
    def health() -> dict[str, Any]:
        return {"status": "ok"}

    @app.get("/api/version", include_in_schema=False)
    def version() -> JSONResponse:
        return JSONResponse({"service": "insurance-claim-mcp", "version": APP_VERSION})

    @app.get("/", include_in_schema=False, response_class=HTMLResponse)
    def intro_page(request: Request) -> HTMLResponse:
        return HTMLResponse(build_html(_resolve_base_url(request, base_url)))

    @app.get("/about.md", include_in_schema=False)
    def intro_markdown(request: Request) -> Response:
        effective = _resolve_base_url(request, base_url)
        if _is_ai_html_reader(request):
            return HTMLResponse(build_html(effective))
        return PlainTextResponse(
            build_markdown(effective), media_type="text/markdown; charset=utf-8"
        )

    @app.get("/llms.txt", include_in_schema=False, response_class=PlainTextResponse)
    def intro_llms(request: Request) -> PlainTextResponse:
        return PlainTextResponse(
            build_markdown(_resolve_base_url(request, base_url)),
            media_type="text/plain; charset=utf-8",
        )

    @app.get("/start", include_in_schema=False, response_class=HTMLResponse)
    def start_page(
        request: Request, user_id: str | None = None, pin: str | None = None
    ) -> HTMLResponse:
        ctx = build_user_context_json(user_id, pin) if (user_id and pin) else None
        return HTMLResponse(build_start_html(_resolve_base_url(request, base_url), ctx))

    @app.get("/start.md", include_in_schema=False)
    def start_markdown(
        request: Request, user_id: str | None = None, pin: str | None = None
    ) -> Response:
        effective = _resolve_base_url(request, base_url)
        ctx = build_user_context_json(user_id, pin) if (user_id and pin) else None
        if _is_ai_html_reader(request):
            return HTMLResponse(build_start_html(effective, ctx))
        return PlainTextResponse(
            build_start_markdown(effective, ctx), media_type="text/markdown; charset=utf-8"
        )

    @app.get("/u/{user_id}/{pin}", include_in_schema=False, response_class=HTMLResponse)
    def user_start_page(request: Request, user_id: str, pin: str) -> HTMLResponse:
        effective = _resolve_base_url(request, base_url)
        ctx = build_user_context_json(user_id, pin)
        return HTMLResponse(build_start_html(effective, ctx))

    app.include_router(api_router)
    app.include_router(ai_router)
    app.mount(MCP_PATH, mcp_app)
    api_key = get_settings().api_key
    app.add_middleware(ApiKeyMiddleware, api_key=api_key)
    return app


app = create_app()
