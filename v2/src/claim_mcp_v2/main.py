"""Separate V2 ASGI server. Infrastructure tools only; no V1 fallback."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from fastmcp.utilities.lifespan import combine_lifespans
from sqlalchemy import Engine
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Receive, Scope, Send

from claim_mcp_v2.config import SERVICE, Settings
from claim_mcp_v2.db import SCHEMA_VERSION, build_engine, check_ready
from claim_mcp_v2.security import authenticate, current_identity

PUBLIC_PATHS = {"/api/health", "/api/ready", "/api/version"}


class CredentialMiddleware:
    def __init__(self, app: ASGIApp, engine: Engine) -> None:
        self.app = app
        self.engine = engine

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope["path"] in PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return
        if scope["path"] == "/mcp":
            scope["path"] = "/mcp/"
        # Never accept actor, client or workspace impersonation headers.
        pairs = scope.get("headers", [])
        supplied = [v.decode("latin-1") for k, v in pairs if k.lower() == b"authorization"]
        forbidden = {b"x-user-id", b"x-user-pin", b"x-workspace-id", b"x-actor-id"}
        valid_header = len(supplied) == 1 and supplied[0].startswith("Bearer ")
        if any(k.lower() in forbidden for k, _v in pairs):
            valid_header = False
        identity = None
        if valid_header:
            try:
                identity = await run_in_threadpool(
                    authenticate, self.engine, supplied[0][7:].strip(),
                )
            except Exception:
                response = JSONResponse({"error": "temporarily_unavailable"}, status_code=503)
                await response(scope, receive, send)
                return
        if identity is None:
            response = JSONResponse(
                {"error": "unauthenticated"}, status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return
        token = current_identity.set(identity)
        try:
            await self.app(scope, receive, send)
        finally:
            current_identity.reset(token)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    engine = build_engine(config)
    mcp = FastMCP(
        "insurance-claim-mcp-v2",
        instructions="V2 infrastructure only. Customer and evaluation tools are not yet available.",
    )

    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
    def get_workspace_context() -> dict[str, Any]:
        """Return only the authenticated actor/workspace, never credentials or customer data."""
        who = current_identity.get()
        if who is None:
            raise ValueError("Authentication required")
        return {
            "schema_version": "2.0", "service": SERVICE,
            "actor_id": who.actor_id, "workspace_id": who.workspace_id,
            "capabilities": ["workspace_context"],
            "business_tools_available": False,
        }

    mcp_app = mcp.http_app(path="/", stateless_http=True)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            check_ready(engine, config.database_project_id)
        except Exception:
            engine.dispose()
            raise RuntimeError("V2 database not ready; run the explicit V2 migration") from None
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="Insurance Claim MCP V2", docs_url=None, redoc_url=None, openapi_url=None,
        lifespan=combine_lifespans(lifespan, mcp_app.lifespan),
    )
    app.state.engine = engine

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": SERVICE}

    @app.get("/api/ready")
    def ready() -> JSONResponse:
        try:
            check_ready(engine, config.database_project_id)
            return JSONResponse({"status": "ready", "service": SERVICE})
        except Exception:
            return JSONResponse({"status": "not_ready", "service": SERVICE}, status_code=503)

    @app.get("/api/version")
    def version() -> dict[str, Any]:
        return {
            "service": SERVICE, "version": config.app_version,
            "schema_version": SCHEMA_VERSION, "business_tools_available": False,
        }

    app.mount("/mcp", mcp_app)
    app.add_middleware(CredentialMiddleware, engine=engine)
    return app


app = create_app()
