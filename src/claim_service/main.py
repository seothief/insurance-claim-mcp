"""FastAPI application with the MCP server mounted at /mcp.

The MCP sub-app's lifespan must be combined into the FastAPI lifespan,
otherwise its streamable-HTTP session manager is never initialised.
"""

import os
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastmcp.utilities.lifespan import combine_lifespans

from claim_service.mcp.server import mcp

APP_VERSION = os.environ.get("APP_VERSION", "local")
MCP_PATH = "/mcp"

mcp_app = mcp.http_app(path="/")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Insurance Claim MCP Service",
        version=APP_VERSION,
        lifespan=combine_lifespans(mcp_app.lifespan),
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok"}

    @app.get("/api/version")
    def version() -> JSONResponse:
        return JSONResponse({"service": "insurance-claim-mcp", "version": APP_VERSION})

    app.mount(MCP_PATH, mcp_app)
    return app


app = create_app()
