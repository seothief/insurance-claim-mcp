"""Safe release probe; optional protected key file enables authenticated MCP checks."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SERVICE = "insurance-claim-mcp-v2"


def probe(
    url: str, version: str | None, key: str | None = None, expected_workspace: str | None = None,
) -> None:
    if not url.startswith(("https://", "http://127.0.0.1:", "http://localhost:")):
        raise ValueError("HTTPS is required for remote probes")
    base = url.rstrip("/")
    for path, status in [("/api/health", "ok"), ("/api/ready", "ready")]:
        with urllib.request.urlopen(base + path, timeout=20) as response:
            data = json.load(response)
            assert data["service"] == SERVICE and data["status"] == status
    with urllib.request.urlopen(base + "/api/version", timeout=20) as response:
        data = json.load(response)
        assert data["service"] == SERVICE
        if version:
            assert data["version"] == version
    try:
        urllib.request.urlopen(urllib.request.Request(base + "/mcp", data=b"{}", headers={
            "Content-Type": "application/json",
        }), timeout=20)
    except urllib.error.HTTPError as exc:
        assert exc.code == 401
    else:
        raise AssertionError("Unauthenticated MCP access was not rejected")
    if key is None:
        return
    headers = {
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream",
    }
    for index, (method, params) in enumerate([
        ("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "v2-smoke", "version": "1"}}),
        ("tools/list", {}),
        ("tools/call", {"name": "get_workspace_context", "arguments": {}}),
    ], 1):
        body = json.dumps({"jsonrpc": "2.0", "id": index, "method": method, "params": params})
        with urllib.request.urlopen(urllib.request.Request(
            base + "/mcp", data=body.encode(), headers=headers,
        ), timeout=30) as response:
            raw = response.read().decode()
            if raw.startswith("event:") or raw.startswith("data:"):
                raw = next(line[6:] for line in raw.splitlines() if line.startswith("data: "))
            result = json.loads(raw)
            assert "error" not in result and not result.get("result", {}).get("isError", False)
            if method == "tools/list":
                assert [tool["name"] for tool in result["result"]["tools"]] == [
                    "get_workspace_context",
                ]
            if method == "tools/call" and expected_workspace is not None:
                context = result["result"]["structuredContent"]
                assert context["service"] == SERVICE
                assert context["workspace_id"] == expected_workspace
                assert context["business_tools_available"] is False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--version")
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--key-env", choices=["V2_SMOKE_KEY"])
    parser.add_argument("--expected-workspace")
    args = parser.parse_args()
    try:
        key = None
        if args.key_file:
            if args.key_file.stat().st_mode & 0o077:
                raise ValueError("Credential file must not be group/world readable")
            key = json.loads(args.key_file.read_text())["api_key"]
        if args.key_env:
            key = os.environ[args.key_env]
        if args.expected_workspace and not key:
            raise ValueError("Workspace verification requires authenticated MCP")
        probe(args.url, args.version, key, args.expected_workspace)
        print("V2 smoke checks passed" + (" (authenticated MCP)" if key else " (public boundary)"))
        return 0
    except Exception:
        print("V2 smoke checks failed; response bodies and credentials suppressed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
