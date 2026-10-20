"""Public PIN-authenticated GET bridge (`/ai/*`) for mobile AI apps (ChatGPT, Gemini, Claude).

Mobile AI apps in standard chat mode often cannot send POST bodies or custom `X-API-Key` headers,
but can fetch `GET` URLs via built-in web browsing tools. Every user operation on `/ai/*` requires:
1. A valid `user_id` and a 4-to-32 character `pin`.
2. The target account to actually have a PIN hash set (`pin_protected=True`).
3. Brute-force protection (temporary lockout after repeated failed PIN attempts).
"""

from __future__ import annotations

import html
import json
import re
import time
from collections.abc import Callable, Coroutine
from typing import Annotated, Any, cast

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute

from claim_service.domain.errors import (
    AccessDeniedError,
    ConflictError,
    DomainError,
    InvalidMappingError,
    NotFoundError,
)
from claim_service.domain.models import (
    ClaimEvaluation,
    ClaimInput,
    HospitalType,
    PolicyIn,
    PolicyOut,
    PolicyRegistration,
    PolicyType,
    ResolvableStatus,
    RiderIn,
    RiderOut,
    RiderResolve,
    SourceType,
    UserIn,
    UserProfile,
)
from claim_service.runtime import get_service

_HTML_USER_AGENTS = (
    "chatgpt-user",
    "oai-searchbot",
    "claude-web",
    "claudebot",
    "perplexity",
    "mozilla",
)


def _wants_html(request: Request) -> bool:
    fmt = (request.query_params.get("format") or "").lower()
    if fmt == "json":
        return False
    if fmt == "html":
        return True
    accept = (request.headers.get("accept") or "").lower()
    if "text/html" in accept:
        return True
    ua = (request.headers.get("user-agent") or "").lower()
    return any(token in ua for token in _HTML_USER_AGENTS)


def _wrap_json_as_html(payload_obj: Any, title: str = "보험 청구 도우미 AI 응답") -> HTMLResponse:
    pretty = html.escape(json.dumps(payload_obj, ensure_ascii=False, indent=2))
    page = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<pre style="white-space: pre-wrap; font-family: monospace; line-height: 1.5">{pretty}</pre>
</main>
</body>
</html>
"""
    return HTMLResponse(content=page, status_code=status.HTTP_200_OK)


class _AiBridgeRoute(APIRoute):
    """Serve `text/html` wrapping JSON for AI web-browsing bots (ChatGPT-User, etc.)."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original_handler = super().get_route_handler()

        async def custom_handler(request: Request) -> Response:
            if not _wants_html(request):
                return await original_handler(request)
            try:
                response = await original_handler(request)
                raw_body = bytes(response.body).decode("utf-8")
                parsed = json.loads(raw_body)
                return _wrap_json_as_html(parsed)
            except HTTPException as exc:
                return _wrap_json_as_html(
                    {
                        "ok": False,
                        "status_code": exc.status_code,
                        "detail": exc.detail,
                    },
                    title="보험 청구 도우미 오류 안내",
                )
            except RequestValidationError as exc:
                return _wrap_json_as_html(
                    {
                        "ok": False,
                        "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
                        "detail": exc.errors(),
                    },
                    title="보험 청구 도우미 입력 형식 오류",
                )

        return custom_handler


router = APIRouter(prefix="/ai", include_in_schema=False, route_class=_AiBridgeRoute)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 300.0
_failed_attempts: dict[str, tuple[int, float]] = {}
_RIDER_SPLIT_RE = re.compile(r"[|;]|\s*,\s*(?=[^0-9])")


def reset_rate_limits() -> None:
    """Clear in-memory failed PIN counters (used by tests)."""
    _failed_attempts.clear()


def _check_lockout(user_id: str) -> None:
    entry = _failed_attempts.get(user_id)
    if entry is None:
        return
    count, first_ts = entry
    if time.monotonic() - first_ts > LOCKOUT_SECONDS:
        _failed_attempts.pop(user_id, None)
        return
    if count >= MAX_FAILED_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="PIN 입력 실패 횟수를 초과했습니다. 5분 후 다시 시도해 주세요.",
        )


def _record_failure(user_id: str) -> None:
    now = time.monotonic()
    entry = _failed_attempts.get(user_id)
    if entry is None or now - entry[1] > LOCKOUT_SECONDS:
        _failed_attempts[user_id] = (1, now)
    else:
        _failed_attempts[user_id] = (entry[0] + 1, entry[1])


def _clear_failures(user_id: str) -> None:
    _failed_attempts.pop(user_id, None)


def _raise_ai_http(user_id: str, exc: DomainError) -> HTTPException:
    if isinstance(exc, AccessDeniedError):
        _record_failure(user_id)
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, InvalidMappingError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _verify_pinned_user(user_id: str, pin: str) -> UserProfile:
    """Ensure the user exists, is PIN-protected, and the provided PIN matches."""
    _check_lockout(user_id)
    svc = get_service()
    try:
        profile = svc.user_profile(user_id, pin=pin)
    except DomainError as exc:
        raise _raise_ai_http(user_id, exc) from exc
    if not profile.pin_protected:
        _record_failure(user_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PIN이 설정되지 않은 계정은 공개 AI 브릿지로 접근할 수 없습니다.",
        )
    _clear_failures(user_id)
    return profile


def _parse_riders(
    riders_spec: str,
    source_type: SourceType,
    issuer: str | None,
    issued_on: str | None,
) -> list[RiderIn]:
    """Parse `특약명:가입금액|특약명:가입금액` into RiderIn objects."""
    if not riders_spec.strip():
        return []
    items: list[RiderIn] = []
    for raw_token in _RIDER_SPLIT_RE.split(riders_spec.strip()):
        token = raw_token.strip()
        if not token:
            continue
        if ":" not in token:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"특약 형식 오류 ('특약명:금액' 형태로 입력하세요): {token}",
            )
        name_part, amount_part = token.rsplit(":", 1)
        rider_name = name_part.strip()
        cleaned_amount = amount_part.strip().replace(",", "").replace("원", "")
        if not rider_name or not cleaned_amount.isdigit():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"특약명 또는 금액이 올바르지 않습니다: {token}",
            )
        items.append(
            RiderIn(
                rider_name=rider_name,
                coverage_amount=int(cleaned_amount),
                source_type=source_type,
                issuer=issuer,
                issued_on=issued_on,
            )
        )
    return items


@router.get("/guide")
def ai_guide() -> dict[str, object]:
    """Public onboarding guide and URL template reference for mobile AI apps."""
    guide = dict(get_service().onboarding_guide())
    guide["mobile_ai_endpoints"] = {
        "onboard": "/ai/onboard?user_id={user_id}&pin={pin}&display_alias={alias}",
        "register_policy": (
            "/ai/register-policy?user_id={user_id}&pin={pin}&company={company}"
            "&product_name={product_name}&policy_type={policy_type}"
            "&source_type=POLICY_CERTIFICATE&issuer={issuer}&issued_on={YYYY-MM-DD}"
            "&riders={특약명1}:{금액1}|{특약명2}:{금액2}"
        ),
        "resolve_rider": (
            "/ai/resolve-rider?user_id={user_id}&pin={pin}&rider_id={rider_id}"
            "&mapping_status={MAPPED|IGNORED}&mapped_rule_id={rule_id}"
        ),
        "policies": "/ai/policies?user_id={user_id}&pin={pin}",
        "delete_policy": "/ai/delete-policy?user_id={user_id}&pin={pin}&policy_id={policy_id}",
        "evaluate": (
            "/ai/evaluate?user_id={user_id}&pin={pin}&kcd_code={KCD}"
            "&treatment_name={처치명}&cost_covered={급여}&cost_uncovered={비급여}"
            "&hospital_type={clinic|hospital|general}"
        ),
    }
    return guide


@router.get("/onboard", response_model=UserProfile)
def ai_onboard(
    user_id: str = Query(..., pattern=r"^[A-Za-z0-9_-]{1,64}$"),
    pin: str = Query(..., min_length=4, max_length=32),
    display_alias: str | None = Query(default=None, max_length=100),
    birth_year: int | None = Query(default=None, ge=1900, le=2100),
) -> UserProfile:
    """Create a PIN-protected user if new, or return existing profile if PIN matches."""
    _check_lockout(user_id)
    svc = get_service()
    try:
        profile = svc.user_profile(user_id, pin=pin)
        if not profile.pin_protected:
            _record_failure(user_id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="PIN이 설정되지 않은 계정은 공개 AI 브릿지로 접근할 수 없습니다.",
            )
        _clear_failures(user_id)
        return profile
    except NotFoundError:
        user_in = UserIn(
            user_id=user_id,
            pin=pin,
            display_alias=display_alias,
            birth_year=birth_year,
        )
        try:
            created = svc.register_user(user_in)
            _clear_failures(user_id)
            return created
        except DomainError as exc:
            raise _raise_ai_http(user_id, exc) from exc
    except DomainError as exc:
        raise _raise_ai_http(user_id, exc) from exc


@router.get("/register-policy", response_model=PolicyRegistration)
def ai_register_policy(
    user_id: Annotated[str, Query(pattern=r"^[A-Za-z0-9_-]{1,64}$")],
    pin: Annotated[str, Query(min_length=4, max_length=32)],
    company: Annotated[str, Query(min_length=1, max_length=100)],
    product_name: Annotated[str, Query(min_length=1, max_length=200)],
    policy_type: Annotated[PolicyType, Query()] = "COMPREHENSIVE",
    riders: Annotated[str, Query()] = "",
    source_type: Annotated[SourceType, Query()] = "USER_STATED",
    issuer: Annotated[str | None, Query(max_length=100)] = None,
    issued_on: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
    silson_generation: Annotated[int | None, Query(ge=1, le=4)] = None,
    enrolled_year: Annotated[int | None, Query(ge=1980, le=2100)] = None,
    replace_riders: Annotated[bool, Query()] = False,
) -> PolicyRegistration:
    """Register or update a policy on a PIN-protected user account via GET query parameters."""
    _verify_pinned_user(user_id, pin)
    parsed_riders = _parse_riders(riders, source_type, issuer, issued_on)
    policy_in = PolicyIn(
        company=company,
        product_name=product_name,
        policy_type=policy_type,
        silson_generation=silson_generation,
        enrolled_year=enrolled_year,
        riders=parsed_riders,
        replace_riders=replace_riders,
        source_type=source_type,
        issuer=issuer,
        issued_on=issued_on,
    )
    try:
        return get_service().register_policy(user_id, policy_in, pin=pin)
    except DomainError as exc:
        raise _raise_ai_http(user_id, exc) from exc


@router.get("/resolve-rider", response_model=RiderOut)
def ai_resolve_rider(
    user_id: Annotated[str, Query(pattern=r"^[A-Za-z0-9_-]{1,64}$")],
    pin: Annotated[str, Query(min_length=4, max_length=32)],
    rider_id: Annotated[str, Query(min_length=1)],
    mapping_status: Annotated[ResolvableStatus, Query()],
    mapped_rule_id: Annotated[str | None, Query()] = None,
    coverage_amount: Annotated[int | None, Query(ge=0)] = None,
) -> RiderOut:
    """Confirm an unresolved rider mapping via GET query parameters."""
    _verify_pinned_user(user_id, pin)
    body = RiderResolve(
        mapping_status=mapping_status,
        mapped_rule_id=mapped_rule_id,
        coverage_amount=coverage_amount,
    )
    try:
        return get_service().resolve_rider(user_id, rider_id, body, pin=pin)
    except DomainError as exc:
        raise _raise_ai_http(user_id, exc) from exc


@router.get("/policies", response_model=list[PolicyOut])
def ai_list_policies(
    user_id: str = Query(..., pattern=r"^[A-Za-z0-9_-]{1,64}$"),
    pin: str = Query(..., min_length=4, max_length=32),
) -> list[PolicyOut]:
    """List registered policies and riders for a PIN-protected user."""
    _verify_pinned_user(user_id, pin)
    try:
        return get_service().list_policies(user_id, pin=pin)
    except DomainError as exc:
        raise _raise_ai_http(user_id, exc) from exc


@router.get("/delete-policy")
def ai_delete_policy(
    user_id: str = Query(..., pattern=r"^[A-Za-z0-9_-]{1,64}$"),
    pin: str = Query(..., min_length=4, max_length=32),
    policy_id: str = Query(..., min_length=1),
) -> dict[str, bool]:
    """Delete a policy for a PIN-protected user."""
    _verify_pinned_user(user_id, pin)
    try:
        deleted = get_service().delete_policy(user_id, policy_id, pin=pin)
    except DomainError as exc:
        raise _raise_ai_http(user_id, exc) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="policy not found")
    return {"deleted": True}


@router.get("/evaluate", response_model=ClaimEvaluation)
def ai_evaluate_claim(
    user_id: str = Query(..., pattern=r"^[A-Za-z0-9_-]{1,64}$"),
    pin: str = Query(..., min_length=4, max_length=32),
    kcd_code: str | None = Query(default=None),
    treatment_name: str | None = Query(default=None),
    treatment_code: str | None = Query(default=None),
    cost_covered: int = Query(default=0, ge=0),
    cost_uncovered: int = Query(default=0, ge=0),
    hospital_type: str | None = Query(default=None),
    is_inpatient: bool | None = Query(default=None),
    inpatient_days: int | None = Query(default=None, ge=0),
    is_injury: bool | None = Query(default=None),
    is_emergency: bool | None = Query(default=None),
    prescribed_drugs: str | None = Query(default=None),
) -> ClaimEvaluation:
    """Evaluate a hospital receipt against a PIN-protected user's stored policies."""
    _verify_pinned_user(user_id, pin)
    drugs = (
        [d.strip() for d in re.split(r"[|,]", prescribed_drugs) if d.strip()]
        if prescribed_drugs
        else []
    )
    valid_hospitals = {"clinic", "hospital", "general"}
    normalized_hospital: HospitalType | None = (
        cast(HospitalType, hospital_type) if hospital_type in valid_hospitals else None
    )
    claim = ClaimInput(
        kcd_code=kcd_code,
        treatment_name=treatment_name,
        treatment_code=treatment_code,
        cost_covered=cost_covered,
        cost_uncovered=cost_uncovered,
        hospital_type=normalized_hospital,
        is_inpatient=is_inpatient,
        inpatient_days=inpatient_days,
        is_injury=is_injury,
        is_emergency=is_emergency,
        prescribed_drugs=drugs,
    )
    try:
        return get_service().evaluate(user_id, claim, pin=pin)
    except DomainError as exc:
        raise _raise_ai_http(user_id, exc) from exc
