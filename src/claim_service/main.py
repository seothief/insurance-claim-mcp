"""FastAPI application with the MCP server mounted at /mcp.

The MCP sub-app's lifespan must be combined into the FastAPI lifespan,
otherwise its streamable-HTTP session manager is never initialised.
"""

import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastmcp.utilities.lifespan import combine_lifespans

from claim_service.api.auth import ApiKeyMiddleware
from claim_service.api.routes import router as api_router
from claim_service.config import get_settings
from claim_service.mcp.server import mcp
from claim_service.runtime import init_runtime

APP_VERSION = os.environ.get("APP_VERSION", "local")
MCP_PATH = "/mcp"

mcp_app = mcp.http_app(path="/", stateless_http=True)


def _db_lifespan(database_url: str | None) -> Callable[[FastAPI], Any]:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        init_runtime(database_url)
        yield

    return lifespan


def create_app(database_url: str | None = None) -> FastAPI:
    base_url = get_settings().public_base_url.strip().rstrip("/")
    app = FastAPI(
        title="Insurance Claim MCP Service",
        version=APP_VERSION,
        lifespan=combine_lifespans(_db_lifespan(database_url), mcp_app.lifespan),
        servers=[{"url": base_url}] if base_url else None,
    )

    @app.get("/api/health", include_in_schema=False)
    def health() -> dict[str, Any]:
        return {"status": "ok"}

    @app.get("/api/version", include_in_schema=False)
    def version() -> JSONResponse:
        return JSONResponse({"service": "insurance-claim-mcp", "version": APP_VERSION})

    app.include_router(api_router)
    app.mount(MCP_PATH, mcp_app)
    api_key = get_settings().api_key
    app.add_middleware(ApiKeyMiddleware, api_key=api_key)
    return app


app = create_app()
