"""Phase 0 smoke tests: FastAPI routes and the mounted MCP endpoint."""

import asyncio

from fastapi.testclient import TestClient
from fastmcp import Client

from claim_service.main import create_app
from claim_service.mcp.server import mcp


def test_health_endpoint() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_endpoint() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/version")
    assert response.status_code == 200
    assert response.json()["service"] == "insurance-claim-mcp"


def test_mcp_lists_smoke_tool() -> None:
    async def run() -> list[str]:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            return [tool.name for tool in tools]

    assert "service_status" in asyncio.run(run())
