"""Tests for the mobile AI GET bridge (`/ai/*`): onboarding, policy upload, and security."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from claim_service.api.ai_bridge import reset_rate_limits
from claim_service.config import get_settings
from claim_service.main import create_app
from tests.dbutil import database_url_for


@pytest.fixture
def keyed_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fresh_external_schema: None
) -> Iterator[TestClient]:
    reset_rate_limits()
    monkeypatch.setenv("API_KEY", "server-secret-key")
    monkeypatch.setenv("SEED_SAMPLE_DATA", "true")
    get_settings.cache_clear()
    with TestClient(create_app(database_url_for(tmp_path, "ai-bridge.db"))) as client:
        yield client
    reset_rate_limits()
    monkeypatch.delenv("API_KEY")
    get_settings.cache_clear()


def test_ai_guide_is_public_without_api_key(keyed_client: TestClient) -> None:
    res = keyed_client.get("/ai/guide")
    assert res.status_code == 200
    data = res.json()
    assert "mobile_ai_endpoints" in data
    assert "register_policy" in data["mobile_ai_endpoints"]


def test_ai_bridge_full_personalized_flow_and_cross_interface_sync(
    keyed_client: TestClient,
) -> None:
    # 1. Onboard new user via mobile GET bridge (no X-API-Key header needed)
    onboard = keyed_client.get(
        "/ai/onboard",
        params={"user_id": "minsu", "pin": "2580", "display_alias": "민수"},
    )
    assert onboard.status_code == 200
    assert onboard.json()["onboarding_status"] == "CREATED"
    assert onboard.json()["pin_protected"] is True

    # 2. Upload personal policy certificate with one standard rider and one ambiguous rider
    reg = keyed_client.get(
        "/ai/register-policy",
        params={
            "user_id": "minsu",
            "pin": "2580",
            "company": "삼성화재",
            "product_name": "무배당 건강보험",
            "policy_type": "COMPREHENSIVE",
            "source_type": "POLICY_CERTIFICATE",
            "issuer": "삼성화재",
            "issued_on": "2023-05-10",
            "riders": "골절진단비:300,000원|무배당 뉴플랜수술특약:1000000",
        },
    )
    assert reg.status_code == 200
    reg_data = reg.json()
    assert reg_data["action"] == "CREATED"
    assert len(reg_data["unresolved_riders"]) == 1
    unresolved_id = reg_data["unresolved_riders"][0]["rider_id"]

    # 3. Resolve ambiguous rider via mobile GET bridge
    resolved = keyed_client.get(
        "/ai/resolve-rider",
        params={
            "user_id": "minsu",
            "pin": "2580",
            "rider_id": unresolved_id,
            "mapping_status": "MAPPED",
            "mapped_rule_id": "DISEASE_SURGERY",
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["mapped_rule_id"] == "DISEASE_SURGERY"

    # 4. Verify status is READY and policies are shared with standard REST/MCP backend
    profile = keyed_client.get("/ai/onboard", params={"user_id": "minsu", "pin": "2580"})
    assert profile.status_code == 200
    assert profile.json()["onboarding_status"] == "READY"

    rest_policies = keyed_client.get(
        "/api/users/minsu/policies",
        headers={"X-API-Key": "server-secret-key", "X-User-Pin": "2580"},
    )
    assert rest_policies.status_code == 200
    assert len(rest_policies.json()) == 1

    # 5. Evaluate hospital receipt via mobile GET bridge
    evaluated = keyed_client.get(
        "/ai/evaluate",
        params={
            "user_id": "minsu",
            "pin": "2580",
            "kcd_code": "S82.1",
            "treatment_name": "석고붕대(통깁스)",
            "cost_covered": 25000,
            "cost_uncovered": 60000,
            "hospital_type": "clinic",
        },
    )
    assert evaluated.status_code == 200
    eval_data = evaluated.json()
    assert eval_data["user_id"] == "minsu"
    assert eval_data["unverified_source_riders"] == []
    assert any(b["rider_name"] == "골절진단비" for b in eval_data["matched_benefits"])

    # 6. Delete policy via mobile GET bridge
    policy_id = reg_data["policy"]["policy_id"]
    deleted = keyed_client.get(
        "/ai/delete-policy",
        params={"user_id": "minsu", "pin": "2580", "policy_id": policy_id},
    )
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    assert keyed_client.get(
        "/ai/policies", params={"user_id": "minsu", "pin": "2580"}
    ).json() == []


def test_ai_bridge_blocks_unpinned_accounts_and_brute_force(
    keyed_client: TestClient,
) -> None:
    # Seeded sample user `user_123` has no PIN set -> must be blocked on public /ai/*
    unpinned = keyed_client.get(
        "/ai/policies", params={"user_id": "user_123", "pin": "1234"}
    )
    assert unpinned.status_code == 403

    # Create a pinned user and test brute-force lockout after 5 wrong PIN attempts
    keyed_client.get("/ai/onboard", params={"user_id": "locked_user", "pin": "9999"})
    for _ in range(5):
        wrong = keyed_client.get(
            "/ai/policies", params={"user_id": "locked_user", "pin": "0000"}
        )
        assert wrong.status_code == 403

    # 6th attempt is locked out with 429 even with the correct PIN
    locked = keyed_client.get(
        "/ai/policies", params={"user_id": "locked_user", "pin": "9999"}
    )
    assert locked.status_code == 429


def test_chatgpt_user_agent_receives_html_and_robots_txt(
    keyed_client: TestClient,
) -> None:
    chatgpt_headers = {
        "User-Agent": (
            "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); "
            "compatible; ChatGPT-User/1.0; +https://openai.com/bot"
        ),
        "Host": "insurance-claim.example.org",
    }
    robots = keyed_client.get("/robots.txt", headers=chatgpt_headers)
    assert robots.status_code == 200
    assert "Allow: /" in robots.text

    start_md = keyed_client.get("/start.md", headers=chatgpt_headers)
    assert start_md.status_code == 200
    assert start_md.headers["content-type"].startswith("text/html")
    assert "https://insurance-claim.example.org/ai/onboard" in start_md.text

    onboard_html = keyed_client.get(
        "/ai/onboard",
        params={"user_id": "gpt_user", "pin": "4321"},
        headers=chatgpt_headers,
    )
    assert onboard_html.status_code == 200
    assert onboard_html.headers["content-type"].startswith("text/html")
    assert "&quot;user_id&quot;: &quot;gpt_user&quot;" in onboard_html.text

    wrong_pin_html = keyed_client.get(
        "/ai/policies",
        params={"user_id": "gpt_user", "pin": "0000"},
        headers=chatgpt_headers,
    )
    assert wrong_pin_html.status_code == 200
    assert wrong_pin_html.headers["content-type"].startswith("text/html")
    assert "&quot;status_code&quot;: 403" in wrong_pin_html.text

    single_fetch = keyed_client.get("/u/gpt_user/4321", headers=chatgpt_headers)
    assert single_fetch.status_code == 200
    assert single_fetch.headers["content-type"].startswith("text/html")
    assert "현재 로그인된 사용자의 실시간 DB 데이터" in single_fetch.text
    assert "&quot;user_id&quot;: &quot;gpt_user&quot;" in single_fetch.text
    assert "&quot;standard_rules&quot;" in single_fetch.text
