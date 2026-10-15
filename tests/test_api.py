"""REST integration tests: health, seeded data, onboarding, upsert and the AI feedback loop."""

from fastapi.testclient import TestClient

SAMPLE = "user_123"


def _new_user(client: TestClient, user_id: str = "me") -> None:
    response = client.post("/api/users", json={"user_id": user_id, "display_alias": "본인"})
    assert response.status_code == 201


def test_health_and_version(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/version").json()["service"] == "insurance-claim-mcp"


def test_seeded_sample_user_is_ready_when_mapped(client: TestClient) -> None:
    policies = client.get(f"/api/users/{SAMPLE}/policies").json()
    assert len(policies) == 2
    comprehensive = next(p for p in policies if p["policy_type"] == "COMPREHENSIVE")
    mapped = {r["rider_name"]: r["mapped_rule_id"] for r in comprehensive["riders"]}
    assert mapped["골절진단비(치아파열제외)"] == "FRACTURE_DIAGNOSIS"
    assert mapped["깁스치료비"] == "CAST_TREATMENT"
    assert client.get(f"/api/users/{SAMPLE}").json()["onboarding_status"] == "READY"


def test_standard_rules_are_unverified(client: TestClient) -> None:
    rules = client.get("/api/catalog/rules").json()
    assert rules
    assert all(rule["verified"] is False for rule in rules)


def test_onboarding_created_then_policy_then_ready(client: TestClient) -> None:
    _new_user(client)
    assert client.get("/api/users/me").json()["onboarding_status"] == "CREATED"
    assert client.post("/api/users", json={"user_id": "me"}).status_code == 409

    body = {
        "company": "메리츠화재",
        "product_name": "테스트 운전자보험",
        "policy_type": "DRIVER",
        "riders": [{"rider_name": "골절진단비", "coverage_amount": 100000}],
    }
    created = client.post("/api/users/me/policies", json=body).json()
    assert created["action"] == "CREATED"
    assert created["unresolved_riders"] == []
    assert client.get("/api/users/me").json()["onboarding_status"] == "READY"


def test_unmapped_rider_returns_ai_follow_up_and_can_be_resolved(client: TestClient) -> None:
    _new_user(client)
    body = {
        "company": "한화손해보험",
        "product_name": "무배당 든든보장보험",
        "policy_type": "COMPREHENSIVE",
        "riders": [
            {"rider_name": "무배당 뉴플랜수술담보", "coverage_amount": 1000000},
            {"rider_name": "골절진단비", "coverage_amount": 300000},
        ],
    }
    registered = client.post("/api/users/me/policies", json=body).json()
    unresolved = registered["unresolved_riders"]
    assert len(unresolved) == 1
    assert "뉴플랜수술담보" in registered["ai_follow_up_prompt"]
    rider_id = unresolved[0]["rider_id"]
    assert client.get("/api/users/me").json()["onboarding_status"] == "NEEDS_CLARIFICATION"

    resolved = client.post(
        f"/api/users/me/riders/{rider_id}/resolve",
        json={"mapping_status": "MAPPED", "mapped_rule_id": "DISEASE_SURGERY"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["mapped_rule_id"] == "DISEASE_SURGERY"
    assert client.get("/api/users/me").json()["onboarding_status"] == "READY"


def test_reregistering_same_policy_updates_instead_of_duplicating(client: TestClient) -> None:
    _new_user(client)
    body = {
        "company": "KB손해보험",
        "product_name": "KB 하나로 종합보험",
        "policy_type": "COMPREHENSIVE",
        "riders": [{"rider_name": "골절진단비", "coverage_amount": 100000}],
    }
    first = client.post("/api/users/me/policies", json=body).json()
    rider_id = first["policy"]["riders"][0]["rider_id"]
    ignored = client.post(
        f"/api/users/me/riders/{rider_id}/resolve", json={"mapping_status": "IGNORED"}
    )
    assert ignored.status_code == 200

    body["riders"] = [{"rider_name": "골절진단비", "coverage_amount": 200000}]
    second = client.post("/api/users/me/policies", json=body).json()
    assert second["action"] == "UPDATED"
    assert second["policy"]["policy_id"] == first["policy"]["policy_id"]
    kept = second["policy"]["riders"][0]
    assert kept["coverage_amount"] == 200000
    assert kept["mapping_status"] == "IGNORED"
    assert len(client.get("/api/users/me/policies").json()) == 1
