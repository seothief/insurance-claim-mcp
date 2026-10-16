"""Safety tests for shared API-key rotation without contacting Google Cloud."""

import base64
from typing import Any

import pytest

from scripts import rotate_api_key


def test_dry_run_lists_versions_without_writing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(rotate_api_key, "get_adc_access_token", lambda: "test-token")

    def request(method: str, url: str, token: str, **kwargs: Any) -> Any:
        calls.append(method)
        return type("Response", (), {"json": lambda self: {"versions": [
            {"name": "projects/test/secrets/API_KEY/versions/1", "state": "ENABLED"},
            {"name": "projects/test/secrets/API_KEY/versions/2", "state": "DISABLED"},
        ]}})()

    monkeypatch.setattr(rotate_api_key, "_request", request)
    assert rotate_api_key.rotate("test", "API_KEY", apply=False) == 0
    output = capsys.readouterr().out
    assert calls == ["GET"]
    assert "활성 버전 수: 1" in output
    assert "DRY RUN" in output


def test_apply_requires_explicit_confirmation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(rotate_api_key, "get_adc_access_token", lambda: "test-token")
    monkeypatch.setattr(
        rotate_api_key,
        "_request",
        lambda method, url, token, **kwargs: (
            calls.append(method) or type("Response", (), {"json": lambda self: {}})()
        ),
    )
    monkeypatch.setattr("builtins.input", lambda _: "no")

    assert rotate_api_key.rotate("test", "API_KEY", apply=True) == 1
    assert calls == ["GET"]
    assert "취소됨" in capsys.readouterr().out


def test_apply_adds_random_key_only_after_confirmation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[str, str, dict[str, Any] | None]] = []
    monkeypatch.setattr(rotate_api_key, "get_adc_access_token", lambda: "test-token")
    monkeypatch.setattr(rotate_api_key.secrets, "token_urlsafe", lambda _: "fresh-random-key")
    monkeypatch.setattr("builtins.input", lambda _: "ROTATE")

    def request(method: str, url: str, token: str, *, json: dict[str, Any] | None = None) -> Any:
        calls.append((method, url, json))
        payload = {"versions": []} if method == "GET" else {
            "name": "projects/test/secrets/API_KEY/versions/3"
        }
        return type("Response", (), {"json": lambda self: payload})()

    monkeypatch.setattr(rotate_api_key, "_request", request)
    assert rotate_api_key.rotate("test", "API_KEY", apply=True) == 0

    assert [call[0] for call in calls] == ["GET", "POST"]
    encoded = calls[1][2]
    assert encoded is not None
    assert base64.b64decode(encoded["payload"]["data"]).decode() == "fresh-random-key"
    assert "fresh-random-key" in capsys.readouterr().out