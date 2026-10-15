"""REST routes: onboarding, policy registration with AI feedback, and claim evaluation."""

from fastapi import APIRouter, HTTPException, Response, status

from claim_service.domain.errors import (
    ConflictError,
    DomainError,
    InvalidMappingError,
    NotFoundError,
)
from claim_service.domain.models import (
    ClaimEvaluation,
    ClaimInput,
    CoverageRule,
    PolicyIn,
    PolicyOut,
    PolicyRegistration,
    RiderOut,
    RiderResolve,
    RiderUpdate,
    UserIn,
    UserProfile,
)
from claim_service.runtime import get_service

router = APIRouter(prefix="/api")


def _raise_http(exc: DomainError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, InvalidMappingError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/catalog/rules",
    response_model=list[CoverageRule],
    operation_id="listStandardRules",
    summary="지원하는 표준 담보 목록",
    description="서버가 알고 있는 표준 담보 규칙을 돌려줍니다. verified가 false인 값은 "
    "약관 원문 확인 전이므로 예상치로만 안내하세요.",
)
def list_rules() -> list[CoverageRule]:
    return list(get_service().rules().values())


@router.get(
    "/onboarding/guide",
    operation_id="getOnboardingGuide",
    summary="보험 등록 방법과 지원 담보 안내",
    description="처음 시작할 때 호출합니다. 보험 정보를 모으는 절차와 "
    "지원하는 담보 목록을 돌려줍니다.",
)
def onboarding_guide() -> dict[str, object]:
    return get_service().onboarding_guide()


@router.post(
    "/users",
    response_model=UserProfile,
    status_code=status.HTTP_201_CREATED,
    operation_id="registerUser",
    summary="사용자 가입",
    description="새 사용자를 만듭니다. user_id는 영문, 숫자, _, - 만 쓸 수 있습니다. "
    "이미 있으면 409를 돌려주므로, 먼저 getUserProfile로 확인하세요.",
)
def register_user(body: UserIn) -> UserProfile:
    try:
        return get_service().register_user(body)
    except DomainError as exc:
        raise _raise_http(exc) from exc


@router.get(
    "/users/{user_id}",
    response_model=UserProfile,
    operation_id="getUserProfile",
    summary="내 등록 현황 조회",
    description="사용자가 있는지, 보험이 몇 개 등록됐는지, 확인이 필요한 특약이 있는지 알려줍니다. "
    "없는 사용자면 404입니다.",
)
def get_user_profile(user_id: str) -> UserProfile:
    try:
        return get_service().user_profile(user_id)
    except DomainError as exc:
        raise _raise_http(exc) from exc


@router.post(
    "/users/{user_id}/policies",
    response_model=PolicyRegistration,
    operation_id="registerPolicy",
    summary="보험 등록 또는 갱신",
    description="보험증권이나 앱 화면에서 읽은 보험 1건을 등록합니다. 같은 보험사와 상품명이면 "
    "새로 만들지 않고 갱신합니다. 응답의 unresolved_riders가 있으면 ai_follow_up_prompt를 "
    "참고해 사용자에게 쉬운 말로 되묻고, resolveRider로 확정하세요.",
)
def register_policy(user_id: str, body: PolicyIn) -> PolicyRegistration:
    try:
        return get_service().register_policy(user_id, body)
    except DomainError as exc:
        raise _raise_http(exc) from exc


@router.get(
    "/users/{user_id}/policies",
    response_model=list[PolicyOut],
    operation_id="listPolicies",
    summary="등록한 보험 목록",
    description="사용자가 등록한 보험과 특약 목록을 돌려줍니다. 특약 ID(rider_id)도 포함됩니다.",
)
def list_policies(user_id: str) -> list[PolicyOut]:
    return get_service().list_policies(user_id)


@router.delete(
    "/users/{user_id}/policies/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    operation_id="deletePolicy",
    summary="해지한 보험 삭제",
    description="더 이상 가입하지 않은 보험을 삭제합니다. "
    "사용자가 삭제를 분명히 원할 때만 호출하세요.",
)
def delete_policy(user_id: str, policy_id: str) -> Response:
    if not get_service().delete_policy(user_id, policy_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="policy not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/users/{user_id}/riders/{rider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="updateRiderAmount",
    summary="특약 가입금액 수정",
    description="특약 하나의 가입금액만 바꿉니다. 금액은 원 단위 정수입니다.",
)
def update_rider(user_id: str, rider_id: str, body: RiderUpdate) -> Response:
    if not get_service().update_rider_amount(user_id, rider_id, body.coverage_amount):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rider not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/users/{user_id}/riders/{rider_id}/resolve",
    response_model=RiderOut,
    operation_id="resolveRider",
    summary="애매한 특약 확정",
    description="자동으로 분류되지 않은 특약을 확정합니다. MAPPED는 mapped_rule_id를 함께 보내고, "
    "CUSTOM은 custom_rule_config를 함께 보내며, IGNORED는 청구와 무관한 특약(사망 등)입니다. "
    "사용자에게 확인하지 않고 추측해서 확정하지 마세요.",
)
def resolve_rider(user_id: str, rider_id: str, body: RiderResolve) -> RiderOut:
    """Confirm a rider's mapping after the registering AI re-checks the policy."""
    try:
        return get_service().resolve_rider(user_id, rider_id, body)
    except DomainError as exc:
        raise _raise_http(exc) from exc


@router.post(
    "/users/{user_id}/evaluate",
    response_model=ClaimEvaluation,
    operation_id="evaluateClaim",
    summary="병원 영수증으로 예상 보험금 계산",
    description="영수증과 처방전에서 읽은 값으로 예상 보험금을 계산합니다. "
    "입력값은 저장하지 않습니다. "
    "결과는 정보 제공용 예상치이며 지급을 확정하는 표현으로 안내하면 안 됩니다. "
    "pending_riders가 있으면 확인되지 않은 특약이 있다는 뜻입니다.",
)
def evaluate(user_id: str, body: ClaimInput) -> ClaimEvaluation:
    """Evaluate a claim. The request is not stored; only informational estimates are returned."""
    return get_service().evaluate(user_id, body)
