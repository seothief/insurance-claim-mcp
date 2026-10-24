"""MCP tools: onboarding, policy registration with AI feedback, and claim evaluation."""

from collections.abc import Callable

from fastmcp import FastMCP

from claim_service.domain.document_guide import PolicyKind, request_guide
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
from claim_service.domain.security import get_bound_user
from claim_service.runtime import get_service, init_runtime

ASSISTANT_INSTRUCTIONS = (
    "너는 사용자의 보험 등록과 병원 영수증 기준 예상 보험금 계산을 돕는 도우미다. "
    "사용자는 별도 UI 없이 너와만 대화한다. 모든 응답은 한국어로, 쉬운 말로 작성한다.\n"
    "[서비스 시작 및 사용자 특정 규칙]\n"
    "1. 사용자가 '보험비서 시작'(또는 '보험 시작')이라고 말하면 즉시 "
    "get_onboarding_guide를 호출한다.\n"
    "2. 응답에 bound_user_id가 있으면 사용자에게 별명을 묻지 않고 바로 그 ID로 "
    "get_user_profile을 호출한다. bound_user_id가 없으면 사용할 별명(user_id)과 "
    "본인 확인용 PIN(4자리 이상)을 물어본 뒤 get_user_profile 또는 "
    "register_user를 호출한다.\n"
    "3. 보험증권 이미지를 받으면 보험사, 상품명, 가입연도, 실손세대, 특약명, 가입금액(원 단위 "
    "정수)을 추출해 사용자에게 요약해 보여주고, 맞는지 확인받은 뒤 register_user_policy를 "
    "호출한다. 증권에서 읽은 특약은 source_type=POLICY_CERTIFICATE로, 발급처와 발급일을 issuer, "
    "issued_on으로 보낸다. 증권이 아닌 자료(리포트, 가공된 분석 결과, 말로만 한 내용)에서 읽은 "
    "특약은 source_type=USER_STATED로 보내며, 그 특약은 계산되지 않는다는 것을 알린다. "
    "불확실한 숫자는 추측하지 말고 되묻는다.\n"
    "3-1. 증권이 없어 등록할 수 없으면 한국신용정보원 본인신용정보 열람서비스(credit4u.or.kr)의 "
    "[보험신용정보 > 정액형보험 / 실손형보험] 상세 화면(보장구분·보장명·보장금액 표 및 "
    "'정액형보장 상세내역 발급' 버튼)에서 가져오도록 안내하거나(Aside 등 브라우저·파일 도구가 있는 "
    "에이전트 AI라면 사용자 로그인 후 모든 계약 상세 화면을 순회해 "
    "CSV(보험사,상품명,보장구분,보장명,보장상태,보장금액)로 먼저 정리·저장한 뒤 바로 등록하거나), "
    "get_document_request_guide로 "
    "받아야 할 서류 목록과 "
    "요청 문구를 가져와 사용자에게 안내한다. 보험사 공식 경로(공식 앱, 공식 홈페이지, 고객센터, "
    "우편·이메일·팩스·지점)만 안내한다. 제3자 앱이나 조회 사이트, 스크래핑, 보안 프로그램 우회 "
    "방법은 절대 안내하지 않는다. PC가 막히면 휴대폰 공식 앱이나 고객센터를 안내한다.\n"
    "4. register_user_policy 결과에 unresolved_riders가 있으면 ai_follow_up_prompt를 참고해 "
    "증권을 다시 확인하거나 사용자에게 쉬운 말로 질문한 뒤 resolve_user_rider로 확정한다.\n"
    "5. 병원 영수증·처방전·약봉투 사진을 받으면 급여/비급여 금액, 병원 종별, 질병코드(KCD), "
    "처치명, 처방약을 읽어 evaluate_claim을 호출한다.\n"
    "[주의사항]\n"
    "- 모든 약관 수치는 verified=false 상태이므로 '예상 금액'으로만 안내하고, "
    "'지급 확정'이나 '반드시 청구하세요' 같은 단정·권유 표현을 쓰지 않는다.\n"
    "- 주민등록번호, 실제 증권번호, 계좌번호는 요구하거나 저장하지 않는다."
)

mcp = FastMCP("Personal-Insurance-Claim-Agent", instructions=ASSISTANT_INSTRUCTIONS)


@mcp.prompt()
def insurance_assistant_prompt(user_id: str = "me") -> str:
    """보험 등록 및 병원 영수증 청구 예상액 계산을 수행하는 표준 AI 비서 지침입니다."""
    return f"{ASSISTANT_INSTRUCTIONS}\n현재 대화의 기본 user_id 후보: {user_id}"


@mcp.resource("insurance://guide/onboarding")
def onboarding_guide_resource() -> dict[str, object]:
    """온보딩 절차, 화면 캡처 안내, 지원 담보 목록을 제공하는 읽기 전용 MCP 리소스입니다."""
    guide = dict(get_service().onboarding_guide())
    guide["trigger_phrase"] = "보험비서 시작"
    guide["bound_user_id"] = get_bound_user()
    return guide


@mcp.resource("insurance://rules/standard")
def standard_rules_resource() -> list[dict[str, object]]:
    """지원하는 표준 담보 규칙 카탈로그와 검증 여부(verified)를 제공하는 읽기 전용 리소스입니다."""
    return [rule.model_dump() for rule in get_service().rules().values()]


@mcp.resource("insurance://guide/document-request/{policy_type}/{product_name}")
def document_request_guide_resource(
    policy_type: str, product_name: str
) -> dict[str, object]:
    """보험사 공식 경로로 증권·약관 서류를 요청하는 안내를 제공하는 동적 템플릿 리소스입니다."""
    kind: PolicyKind = _to_guide_kind(policy_type.upper())
    return request_guide(kind, product_name)



def _guard[T](call: Callable[[], T]) -> T:
    """Turn domain errors into readable tool errors instead of server crashes."""
    try:
        return call()
    except DomainError as exc:
        raise ValueError(str(exc)) from exc


@mcp.tool()
def get_document_request_guide(
    policy_type: PolicyType, product_name: str
) -> dict[str, object]:
    """보험사에 요청해야 할 증권과 약관 목록, 요청 문구, 공식 요청 경로를 돌려줍니다."""
    kind: PolicyKind = "OTHER" if policy_type == "OTHER" else _to_guide_kind(policy_type)
    return request_guide(kind, product_name)


def _to_guide_kind(policy_type: str) -> PolicyKind:
    mapping: dict[str, PolicyKind] = {
        "SILSON": "SILSON",
        "COMPREHENSIVE": "COMPREHENSIVE",
        "DRIVER": "DRIVER",
        "FIXED_BENEFIT": "FIXED_BENEFIT",
    }
    return mapping.get(policy_type, "OTHER")


@mcp.tool()
def get_onboarding_guide() -> dict[str, object]:
    """서비스 시작 시 가장 먼저 호출합니다. 온보딩 절차와 bound_user_id를 반환합니다."""
    guide = dict(get_service().onboarding_guide())
    guide["trigger_phrase"] = "보험비서 시작"
    guide["bound_user_id"] = get_bound_user()
    return guide


@mcp.tool()
def register_user(
    user_id: str,
    pin: str | None = None,
    display_alias: str | None = None,
    birth_year: int | None = None,
) -> dict[str, object]:
    """신규 사용자를 등록합니다. 타인과 겹치지 않도록 4자리 이상의 PIN을 함께 설정합니다."""
    user = UserIn(user_id=user_id, display_alias=display_alias, birth_year=birth_year, pin=pin)
    return _guard(lambda: get_service().register_user(user).model_dump())


@mcp.tool()
def get_user_profile(user_id: str, pin: str | None = None) -> dict[str, object]:
    """사용자의 온보딩 상태, 등록 보험 수, 미매핑 특약을 조회합니다."""
    return _guard(lambda: get_service().user_profile(user_id, pin=pin).model_dump())


@mcp.tool()
def list_standard_rules() -> list[dict[str, object]]:
    """Return the standard coverage rules. `verified` is False until checked against policy text."""
    return [rule.model_dump() for rule in get_service().rules().values()]


@mcp.tool()
def list_user_policies(user_id: str, pin: str | None = None) -> list[dict[str, object]]:
    """사용자의 활성 보험 계약 및 특약 목록을 조회합니다."""
    return _guard(
        lambda: [p.model_dump() for p in get_service().list_policies(user_id, pin=pin)]
    )


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
    pin: str | None = None,
) -> dict[str, object]:
    """보험을 등록하거나 갱신합니다. 미매핑 특약은 resolve_user_rider로 확정하세요."""
    policy = PolicyIn(
        company=company,
        product_name=product_name,
        policy_type=policy_type,
        silson_generation=silson_generation,
        enrolled_year=enrolled_year,
        riders=riders,
        replace_riders=replace_riders,
    )
    return _guard(lambda: get_service().register_policy(user_id, policy, pin=pin).model_dump())


@mcp.tool()
def resolve_user_rider(
    user_id: str,
    rider_id: str,
    mapping_status: ResolvableStatus,
    mapped_rule_id: str | None = None,
    custom_rule_config: dict[str, object] | None = None,
    coverage_amount: int | None = None,
    rule_config_override: dict[str, object] | None = None,
    pin: str | None = None,
) -> dict[str, object]:
    """미매핑 특약의 매핑을 확정합니다 (MAPPED, CUSTOM, IGNORED).

    rule_config_override: 증권/약관에서 확인한 이 특약만의 지급 요건(예:
    {"target_kcd_prefixes": ["S72"]}). POLICY_CERTIFICATE 출처 특약에서 계산에 반영됩니다.
    """
    body = RiderResolve(
        mapping_status=mapping_status,
        mapped_rule_id=mapped_rule_id,
        custom_rule_config=custom_rule_config,
        coverage_amount=coverage_amount,
        rule_config_override=rule_config_override,
    )
    return _guard(
        lambda: get_service().resolve_rider(user_id, rider_id, body, pin=pin).model_dump()
    )


@mcp.tool()
def delete_user_policy(
    user_id: str, policy_id: str, pin: str | None = None
) -> dict[str, bool]:
    """해지한 보험 계약을 삭제합니다."""
    return _guard(lambda: {"deleted": get_service().delete_policy(user_id, policy_id, pin=pin)})


@mcp.tool()
def update_user_rider(
    user_id: str, rider_id: str, coverage_amount: int, pin: str | None = None
) -> dict[str, bool]:
    """특약 1건의 가입금액을 변경합니다."""
    return _guard(
        lambda: {
            "updated": get_service().update_rider_amount(
                user_id, rider_id, coverage_amount, pin=pin
            )
        }
    )


@mcp.tool()
def evaluate_claim(
    user_id: str, claim: ClaimInput, pin: str | None = None
) -> dict[str, object]:
    """영수증/처방전 정보로 예상 보험금을 계산합니다. 입력된 진료 정보는 저장되지 않습니다."""
    return _guard(lambda: get_service().evaluate(user_id, claim, pin=pin).model_dump())


def main() -> None:
    """Run the MCP server over stdio for local AI clients (Antigravity, Claude Desktop, etc.)."""
    init_runtime()
    mcp.run()


if __name__ == "__main__":
    main()

