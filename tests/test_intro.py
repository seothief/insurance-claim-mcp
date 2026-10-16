"""Public intro pages: reachable without a key, no secrets, consistent with the real tools."""

import asyncio
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from claim_service.config import get_settings
from claim_service.intro import TOOLS, build_html, build_markdown
from claim_service.main import create_app
from claim_service.mcp.server import mcp
from tests.dbutil import database_url_for

SECRET_KEY = "secret-test-key-1234567890"
FORBIDDEN_PATTERNS = (
    SECRET_KEY,
    "project-93d02748",
    "878600435547",
    "run.app",
    "api_key.txt",
    "secrets",
    "DATABASE_URL",
    "neon",
    "postgresql",
    "X-API-Key",
    "pin_hash",
)


@pytest.fixture
def keyed_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fresh_external_schema: None
) -> Iterator[TestClient]:
    monkeypatch.setenv("API_KEY", SECRET_KEY)
    get_settings.cache_clear()
    with TestClient(create_app(database_url_for(tmp_path, "intro.db"))) as client:
        yield client
    monkeypatch.delenv("API_KEY")
    get_settings.cache_clear()


def test_intro_routes_are_public_even_when_a_key_is_required(keyed_client: TestClient) -> None:
    assert keyed_client.get("/").status_code == 200
    assert keyed_client.get("/llms.txt").status_code == 200
    assert keyed_client.get("/about.md").status_code == 200


def test_data_routes_still_require_the_key(keyed_client: TestClient) -> None:
    assert keyed_client.get("/api/catalog/rules").status_code == 401
    assert keyed_client.get("/api/users/user_123/policies").status_code == 401
    assert keyed_client.post("/mcp", json={}).status_code == 401


def test_content_types(keyed_client: TestClient) -> None:
    assert keyed_client.get("/").headers["content-type"].startswith("text/html")
    assert "text/markdown" in keyed_client.get("/about.md").headers["content-type"]
    assert keyed_client.get("/llms.txt").headers["content-type"].startswith("text/plain")


def test_all_three_routes_carry_the_same_text(keyed_client: TestClient) -> None:
    markdown = keyed_client.get("/about.md").text
    assert keyed_client.get("/llms.txt").text == markdown
    assert "예상치" in keyed_client.get("/").text


def test_pages_contain_no_secrets_or_infrastructure_details() -> None:
    for text in (build_markdown(), build_html()):
        for pattern in FORBIDDEN_PATTERNS:
            assert pattern.lower() not in text.lower(), pattern


def test_limits_and_disclaimers_are_present() -> None:
    markdown = build_markdown()
    for phrase in ("미검증", "예상치", "지급 확정이 아닙니다", "가입금액", "한계"):
        assert phrase in markdown, phrase
    assert "읽는 AI에게" in markdown


def test_listed_tools_match_the_real_mcp_tools() -> None:
    async def names() -> set[str]:
        async with Client(mcp) as client:
            return {tool.name for tool in await client.list_tools()}

    assert {name for name, _ in TOOLS} == asyncio.run(names())


def test_example_is_computed_by_the_engine_and_shows_the_cast_difference() -> None:
    markdown = build_markdown()
    assert "통깁스(석고붕대) 처치" in markdown
    assert "부목(반깁스) 처치" in markdown
    amounts = re.findall(r"합계 예상: ([\d,]+)원", markdown)
    assert amounts == ["800,000", "300,000"]


def test_html_has_preview_tags_and_escapes_markup() -> None:
    page = build_html()
    assert 'property="og:title"' in page
    assert 'property="og:description"' in page
    assert "<script" not in page.lower()
