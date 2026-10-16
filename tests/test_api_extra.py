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


def test_sample_user_is_never_calculated(client: TestClient) -> None:
    """The synthetic sample is not a real policy: it has no certificate source, so no payout."""
    body = {
        "kcd_code": "S82.1",
        "treatment_name": "석고붕대(통깁스)",
        "cost_covered": 25000,
        "cost_uncovered": 60000,
        "hospital_type": "clinic",
    }
    result = client.post(f"/api/users/{SAMPLE}/evaluate", json=body).json()
    assert result["total_estimated_payout"] == 0
    assert result["matched_benefits"] == []
    assert result["disclaimer"]
    assert result["unverified_source_riders"]
    assert any("샘플보험사A" in item for item in result["unverified_source_riders"])
    assert any("골절진단비(샘플)" in item for item in result["unverified_source_riders"])


def test_certified_policy_is_calculated(client: TestClient) -> None:
    _new_user(client)
    body = {
        "company": "테스트보험사",
        "product_name": "증권 확인 종합보험",
        "policy_type": "COMPREHENSIVE",
        "source_type": "POLICY_CERTIFICATE",
        "issuer": "테스트보험사",
        "issued_on": "2021-03-02",
        "riders": [
            {
                "rider_name": "골절진단비",
                "coverage_amount": 300000,
                "source_type": "POLICY_CERTIFICATE",
                "issuer": "테스트보험사",
                "issued_on": "2021-03-02",
            }
        ],
    }
    assert client.post("/api/users/me/policies", json=body).status_code == 200
    result = client.post(
        "/api/users/me/evaluate",
        json={"kcd_code": "S82.1", "treatment_name": "골절", "cost_covered": 1000},
    ).json()
    assert result["total_estimated_payout"] == 0
    assert result["matched_benefits"][0]["status"] == "NOT_EVALUATED"
    assert result["unverified_source_riders"] == []


def test_user_stated_rider_is_not_calculated_even_if_it_matches(client: TestClient) -> None:
    _new_user(client)
    body = {
        "company": "테스트보험사",
        "product_name": "말로만 한 종합보험",
        "policy_type": "COMPREHENSIVE",
        "riders": [{"rider_name": "골절진단비", "coverage_amount": 300000}],
    }
    assert client.post("/api/users/me/policies", json=body).status_code == 200
    result = client.post(
        "/api/users/me/evaluate",
        json={"kcd_code": "S82.1", "treatment_name": "골절", "cost_covered": 1000},
    ).json()
    assert result["total_estimated_payout"] == 0
    assert any("골절진단비" in item for item in result["unverified_source_riders"])


def test_mcp_lists_onboarding_and_policy_tools(client: TestClient) -> None:
    async def run() -> list[str]:
        async with Client(mcp) as mcp_client:
            tools = await mcp_client.list_tools()
            return [tool.name for tool in tools]

    names = set(asyncio.run(run()))
    expected = {
        "get_onboarding_guide",
        "get_document_request_guide",
        "register_user",
        "get_user_profile",
        "register_user_policy",
        "resolve_user_rider",
        "evaluate_claim",
    }
    assert expected <= names


def test_mcp_tool_call_works_over_in_memory_client(client: TestClient) -> None:
    async def run() -> dict[str, object]:
        async with Client(mcp) as mcp_client:
            result = await mcp_client.call_tool("get_onboarding_guide", {})
            return dict(result.data)  # type: ignore[arg-type]

    guide = asyncio.run(run())
    assert guide["trigger_phrase"] == "보험비서 시작"


def test_mcp_document_request_guide_uses_official_channels_only() -> None:
    async def run() -> dict[str, object]:
        async with Client(mcp) as mcp_client:
            result = await mcp_client.call_tool(
                "get_document_request_guide",
                {"policy_type": "COMPREHENSIVE", "product_name": "테스트 종합보험"},
            )
            return dict(result.data)  # type: ignore[arg-type]

    guide = asyncio.run(run())
    assert guide["product_name"] == "테스트 종합보험"
    channels = guide["where_to_request"]
    assert channels == [
        "보험사 공식 앱",
        "보험사 공식 홈페이지의 본인 로그인 메뉴",
        "보험사 고객센터(전화, 채팅)",
        "보험사가 제공하는 우편, 이메일, 팩스, 지점 발급",
    ]
    response_text = " ".join(str(item) for item in [*channels, *guide["not_accepted"]])
    prohibited_terms = ("토스", "뱅크샐러드", "화면 캡처", "스크래핑")
    assert not any(term in response_text for term in prohibited_terms)

