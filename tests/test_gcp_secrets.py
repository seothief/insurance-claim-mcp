"""Tests for shared Secret Manager helpers without contacting Google Cloud."""

from typing import Any

import pytest

from scripts import gcp_secrets


def test_get_secret_text_decodes_secret_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class Response:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, Any]:
            return {"payload": {"data": "cG9zdGdyZXNxbDovL2V4YW1wbGU="}}

    def fake_get(url: str, **kwargs: Any) -> Response:
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(gcp_secrets.httpx, "get", fake_get)

    assert gcp_secrets.get_secret_text("test-token", "DATABASE_URL", "test-project") == (
        "postgresql://example"
    )
    assert captured["url"].endswith(
        "/projects/test-project/secrets/DATABASE_URL/versions/latest:access"
    )
    assert captured["headers"] == {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgres://user:pass@db/test", "postgresql+psycopg://user:pass@db/test"),
        ("postgresql://user:pass@db/test", "postgresql+psycopg://user:pass@db/test"),
        ("sqlite:///local.db", "sqlite:///local.db"),
    ],
)
def test_get_database_url_normalizes_postgres_driver(
    monkeypatch: pytest.MonkeyPatch, url: str, expected: str
) -> None:
    monkeypatch.setattr(gcp_secrets, "get_secret_text", lambda *_args: url)

    assert gcp_secrets.get_database_url("test-token") == expected