"""MCP server definition. Real tools are added in Phase 4; Phase 0 exposes a smoke tool only."""

from fastmcp import FastMCP

mcp = FastMCP("Personal-Insurance-Claim-Agent")


@mcp.tool()
def service_status() -> dict[str, str]:
    """Return a static status string. Used to verify the MCP endpoint in Phase 0."""
    return {"status": "ok", "stage": "phase-0-skeleton"}
