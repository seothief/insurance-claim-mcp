"""MCP tools: onboarding, policy registration with AI feedback, and claim evaluation."""

from collections.abc import Callable

from fastmcp import FastMCP

from claim_service.domain.errors import DomainError
from claim_service.domain.models import (
    ClaimInput,
    PolicyIn,
    PolicyType,
    ResolvableStatus,
    RiderIn,
    RiderResolve,
    UserIn,
)
from claim_service.runtime import get_service

mcp = FastMCP("Personal-Insurance-Claim-Agent")


def _guard[T](call: Callable[[], T]) -> T:
    """Turn domain errors into readable tool errors instead of server crashes."""
    try:
        return call()
    except DomainError as exc:
        raise ValueError(str(exc)) from exc


@mcp.tool()
def get_onboarding_guide() -> dict[str, object]:
    """Explain how to register a user and their policies, and which standard rules exist."""
    return get_service().onboarding_guide()


@mcp.tool()
def register_user(
    user_id: str,
    display_alias: str | None = None,
    birth_year: int | None = None,
) -> dict[str, object]:
    """Create a new user (step 1 of onboarding). user_id may only use letters, digits, _ and -."""
    user = UserIn(user_id=user_id, display_alias=display_alias, birth_year=birth_year)
    return _guard(lambda: get_service().register_user(user).model_dump())


@mcp.tool()
def get_user_profile(user_id: str) -> dict[str, object]:
    """Show onboarding status, policy count and riders that still need confirmation."""
    return _guard(lambda: get_service().user_profile(user_id).model_dump())


@mcp.tool()
def list_standard_rules() -> list[dict[str, object]]:
    """Return the standard coverage rules. `verified` is False until checked against policy text."""
    return [rule.model_dump() for rule in get_service().rules().values()]


@mcp.tool()
def list_user_policies(user_id: str) -> list[dict[str, object]]:
    """List the user's active policies and their riders (with rider_id for updates)."""
    return [p.model_dump() for p in get_service().list_policies(user_id)]


@mcp.tool()
def register_user_policy(
    user_id: str,
    company: str,
    product_name: str,
    policy_type: PolicyType,
    riders: list[RiderIn],
    silson_generation: int | None = None,
    enrolled_year: int | None = None,
    replace_riders: bool = False,
) -> dict[str, object]:
    """Register or update a policy. Riders that could not be mapped are returned with an
    ai_follow_up_prompt; re-check the policy and call resolve_user_rider for each one."""
    policy = PolicyIn(
        company=company,
        product_name=product_name,
        policy_type=policy_type,
        silson_generation=silson_generation,
        enrolled_year=enrolled_year,
        riders=riders,
        replace_riders=replace_riders,
    )
    return _guard(lambda: get_service().register_policy(user_id, policy).model_dump())


@mcp.tool()
def resolve_user_rider(
    user_id: str,
    rider_id: str,
    mapping_status: ResolvableStatus,
    mapped_rule_id: str | None = None,
    custom_rule_config: dict[str, object] | None = None,
    coverage_amount: int | None = None,
) -> dict[str, object]:
    """Confirm a rider's mapping. mapping_status: MAPPED (with mapped_rule_id), CUSTOM (with
    custom_rule_config such as target_kcd_prefixes or target_keywords), or IGNORED."""
    body = RiderResolve(
        mapping_status=mapping_status,
        mapped_rule_id=mapped_rule_id,
        custom_rule_config=custom_rule_config,
        coverage_amount=coverage_amount,
    )
    return _guard(lambda: get_service().resolve_rider(user_id, rider_id, body).model_dump())


@mcp.tool()
def delete_user_policy(user_id: str, policy_id: str) -> dict[str, bool]:
    """Delete a policy the user no longer holds (for example, a cancelled policy)."""
    return {"deleted": get_service().delete_policy(user_id, policy_id)}


@mcp.tool()
def update_user_rider(user_id: str, rider_id: str, coverage_amount: int) -> dict[str, bool]:
    """Change the coverage amount of one rider."""
    return {"updated": get_service().update_rider_amount(user_id, rider_id, coverage_amount)}


@mcp.tool()
def evaluate_claim(user_id: str, claim: ClaimInput) -> dict[str, object]:
    """Estimate payouts for a receipt or prescription. The claim data is not stored."""
    return get_service().evaluate(user_id, claim).model_dump()
