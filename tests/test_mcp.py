"""MCP tools, prompts and resources remain the sole insurance interface."""

import asyncio
import json

from fastapi.testclient import TestClient
from fastmcp import Client

from claim_service.mcp.server import mcp


def test_mcp_tools_prompt_and_resources_are_available(client: TestClient) -> None:
    async def inspect() -> tuple[set[str], set[str], set[str]]:
        async with Client(mcp) as mcp_client:
            tools = {tool.name for tool in await mcp_client.list_tools()}
            prompts = {prompt.name for prompt in await mcp_client.list_prompts()}
            resources = {str(resource.uri) for resource in await mcp_client.list_resources()}
            templates = {
                str(template.uri_template)
                for template in await mcp_client.list_resource_templates()
            }
            return tools, prompts, resources | templates

    tools, prompts, resources = asyncio.run(inspect())
    assert {
        "get_onboarding_guide",
        "get_document_request_guide",
        "register_user",
        "get_user_profile",
        "list_standard_rules",
        "list_user_policies",
        "register_user_policy",
        "resolve_user_rider",
        "delete_user_policy",
        "update_user_rider",
        "evaluate_claim",
    } <= tools
    assert "insurance_assistant_prompt" in prompts
    assert {
        "insurance://guide/onboarding",
        "insurance://rules/standard",
        "insurance://guide/document-request/{policy_type}/{product_name}",
    } <= resources


def test_mcp_user_registration_and_profile_flow(client: TestClient) -> None:
    async def register_and_read() -> dict[str, object]:
        async with Client(mcp) as mcp_client:
            created = await mcp_client.call_tool(
                "register_user",
                {"user_id": "mcp_test_user", "display_alias": "테스트", "pin": "4829"},
            )
            assert created.is_error is False
            profile = await mcp_client.call_tool(
                "get_user_profile", {"user_id": "mcp_test_user", "pin": "4829"}
            )
            assert profile.is_error is False
            return dict(profile.data)  # type: ignore[arg-type]

    profile = asyncio.run(register_and_read())
    assert profile["user_id"] == "mcp_test_user"
    assert profile["onboarding_status"] == "CREATED"


def test_mcp_policy_registration_and_rider_confirmation(client: TestClient) -> None:
    async def register_and_resolve() -> dict[str, object]:
        async with Client(mcp) as mcp_client:
            await mcp_client.call_tool(
                "register_user",
                {"user_id": "policy_test_user", "display_alias": "테스트", "pin": "4829"},
            )
            registered = await mcp_client.call_tool(
                "register_user_policy",
                {
                    "user_id": "policy_test_user",
                    "company": "테스트 보험사",
                    "product_name": "테스트 종합보험",
                    "policy_type": "COMPREHENSIVE",
                    "riders": [{"rider_name": "무배당 뉴플랜수술담보", "coverage_amount": 100000}],
                    "pin": "4829",
                },
            )
            result = dict(registered.data)  # type: ignore[arg-type]
            unresolved = result["unresolved_riders"]
            assert isinstance(unresolved, list) and len(unresolved) == 1
            rider_id = unresolved[0]["rider_id"]
            await mcp_client.call_tool(
                "resolve_user_rider",
                {
                    "user_id": "policy_test_user",
                    "rider_id": rider_id,
                    "mapping_status": "IGNORED",
                    "pin": "4829",
                },
            )
            profile = await mcp_client.call_tool(
                "get_user_profile", {"user_id": "policy_test_user", "pin": "4829"}
            )
            return dict(profile.data)  # type: ignore[arg-type]

    profile = asyncio.run(register_and_resolve())
    assert profile["onboarding_status"] == "READY"


def test_mcp_onboarding_resource_includes_bound_user_context(client: TestClient) -> None:
    async def read_guide() -> dict[str, object]:
        async with Client(mcp) as mcp_client:
            resource = await mcp_client.read_resource("insurance://guide/onboarding")
            return json.loads(resource[0].text)  # type: ignore[union-attr]

    guide = asyncio.run(read_guide())
    assert guide["trigger_phrase"] == "보험비서 시작"
    assert "steps" in guide