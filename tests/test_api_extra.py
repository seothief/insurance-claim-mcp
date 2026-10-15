"""More REST and MCP integration tests: validation, silson inference, CRUD, evaluate and tools."""

import asyncio

from fastapi.testclient import TestClient
from fastmcp import Client

from claim_service.mcp.server import mcp

SAMPLE = "user_123"


def _new_user(client: TestClient, user_id: str = "me") -> None:
    assert client.post("/api/users", json={"user_id": user_id}).status_code == 201


def test_invalid_user_id_is_rejected(client: TestClient) -> None:
    assert client.post("/api/users", json={"user_id": "bad id!"}).status_code == 422


def test_resolve_rejects_unknown_and_silson_rules(client: TestClient) -> None:
    rider_id = client.get(f"/api/users/{SAMPLE}/policies").json()[1]["riders"][0]["rider_id"]
    unknown = client.post(
        f"/api/users/{SAMPLE}/riders/{rider_id}/resolve",
        json={"mapping_status": "MAPPED", "mapped_rule_id": "NOPE"},
    )
    assert unknown.status_code == 422
    silson = client.post(
        f"/api/users/{SAMPLE}/riders/{rider_id}/resolve",
        json={"mapping_status": "MAPPED", "mapped_rule_id": "SILSON_GEN4"},
    )
    assert silson.status_code == 422


def test_custom_mapping_requires_config(client: TestClient) -> None:
    rider_id = client.get(f"/api/users/{SAMPLE}/policies").json()[1]["riders"][0]["rider_id"]
    response = client.post(
        f"/api/users/{SAMPLE}/riders/{rider_id}/resolve", json={"mapping_status": "CUSTOM"}
    )
    assert response.status_code == 422


def test_silson_without_generation_infers_from_year(client: TestClient) -> None:
    _new_user(client)
    body = {
        "company": "삼성화재",
        "product_name": "실손보험",
        "policy_type": "SILSON",
        "enrolled_year": 2015,
        "riders": [],
    }
    registered = client.post("/api/users/me/policies", json=body).json()
    assert registered["policy"]["silson_generation"] == 2
    assert "추정" in registered["ai_follow_up_prompt"]


def test_silson_without_any_generation_info_warns(client: TestClient) -> None:
    _new_user(client)
    body = {"company": "X", "product_name": "실손", "policy_type": "SILSON", "riders": []}
    registered = client.post("/api/users/me/policies", json=body).json()
    assert registered["policy"]["silson_generation"] is None
    assert "가입연도가 모두 없어" in registered["ai_follow_up_prompt"]


def test_onboarding_guide_endpoint(client: TestClient) -> None:
    guide = client.get("/api/onboarding/guide").json()
    assert len(guide["steps"]) >= 4
    assert any(rule["rule_id"] == "BURN_DIAGNOSIS" for rule in guide["supported_rules"])


def test_register_update_delete_flow(client: TestClient) -> None:
    body = {
        "company": "메리츠화재",
        "product_name": "테스트 운전자보험",
        "policy_type": "DRIVER",
        "riders": [{"rider_name": "골절진단비", "coverage_amount": 100000}],
    }
    policy = client.post(f"/api/users/{SAMPLE}/policies", json=body).json()["policy"]
    rider_id = policy["riders"][0]["rider_id"]

    patched = client.patch(
        f"/api/users/{SAMPLE}/riders/{rider_id}", json={"coverage_amount": 200000}
    )
    assert patched.status_code == 204
    listed = client.get(f"/api/users/{SAMPLE}/policies").json()
    amounts = [
        r["coverage_amount"]
        for p in listed
        if p["policy_id"] == policy["policy_id"]
        for r in p["riders"]
    ]
    assert amounts == [200000]

    deleted = client.delete(f"/api/users/{SAMPLE}/policies/{policy['policy_id']}")
    assert deleted.status_code == 204
    assert client.delete(f"/api/users/{SAMPLE}/policies/{policy['policy_id']}").status_code == 404


def test_duplicate_rider_names_are_rejected(client: TestClient) -> None:
    body = {
        "company": "X",
        "product_name": "중복 테스트",
        "policy_type": "OTHER",
        "riders": [
            {"rider_name": "골절진단비", "coverage_amount": 1},
            {"rider_name": "골절진단비", "coverage_amount": 2},
        ],
    }
    assert client.post(f"/api/users/{SAMPLE}/policies", json=body).status_code == 409


def test_other_users_cannot_modify_my_rider(client: TestClient) -> None:
    rider_id = client.get(f"/api/users/{SAMPLE}/policies").json()[1]["riders"][0]["rider_id"]
    response = client.patch(
        "/api/users/other_user/riders/" + rider_id, json={"coverage_amount": 1}
    )
    assert response.status_code == 404


def test_evaluate_endpoint_returns_estimates(client: TestClient) -> None:
    body = {
        "kcd_code": "S82.1",
        "treatment_name": "석고붕대(통깁스)",
        "cost_covered": 25000,
        "cost_uncovered": 60000,
        "hospital_type": "clinic",
    }
    result = client.post(f"/api/users/{SAMPLE}/evaluate", json=body).json()
    assert result["total_estimated_payout"] > 0
    assert result["disclaimer"]
    statuses = {b["rider_name"]: b["status"] for b in result["matched_benefits"]}
    assert statuses["골절진단비(치아파열제외)"] == "ELIGIBLE"
    assert statuses["깁스치료비"] == "ELIGIBLE"
    assert result["pending_riders"] == []


def test_mcp_lists_onboarding_and_policy_tools(client: TestClient) -> None:
    async def run() -> list[str]:
        async with Client(mcp) as mcp_client:
            tools = await mcp_client.list_tools()
            return [tool.name for tool in tools]

    names = set(asyncio.run(run()))
    expected = {
        "get_onboarding_guide",
        "register_user",
        "get_user_profile",
        "register_user_policy",
        "resolve_user_rider",
        "evaluate_claim",
    }
    assert expected <= names
