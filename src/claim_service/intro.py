"""Public introduction page for people and for AI assistants.

One Markdown text is the single source for three routes (/, /llms.txt, /about.md), so they cannot
drift apart. The worked example is produced by the real evaluation engine on synthetic data.
Nothing here may contain secrets, project identifiers, database details or personal contracts.
"""

import html

from claim_service.domain.catalog import STANDARD_RULES
from claim_service.domain.evaluator import evaluate_claim
from claim_service.domain.models import ClaimInput, PolicyOut, RiderOut

TOOLS: tuple[tuple[str, str], ...] = (
    ("get_onboarding_guide", "시작할 때 가장 먼저 호출. 등록 절차와 지원 담보 안내"),
    ("get_document_request_guide", "보험사에 증권을 공식 경로로 요청하는 안내와 요청 문구"),
    ("register_user", "사용자 등록 (별명과 PIN)"),
    ("get_user_profile", "등록 현황 조회: 보험 수, 확인이 필요한 특약"),
    ("list_standard_rules", "지원하는 표준 담보 목록과 검증 여부"),
    ("list_user_policies", "등록한 보험과 특약 목록"),
    ("register_user_policy", "보험 1건 등록 또는 갱신"),
    ("resolve_user_rider", "자동으로 분류되지 않은 특약을 확정"),
    ("delete_user_policy", "해지한 보험 삭제"),
    ("update_user_rider", "특약 가입금액 수정"),
    ("evaluate_claim", "영수증 정보로 예상 보험금과 필요 서류 계산 (입력은 저장하지 않음)"),
)

RESOURCES: tuple[tuple[str, str], ...] = (
    ("insurance://guide/onboarding", "온보딩 절차, 화면 캡처 안내, 지원 담보 요약 (정적 리소스)"),
    ("insurance://rules/standard", "지원하는 표준 담보 규칙 카탈로그 및 검증 상태 (정적 리소스)"),
    (
        "insurance://guide/document-request/{policy_type}/{product_name}",
        "보험사 공식 경로 증권·약관 요청 안내 및 문구 (동적 템플릿 리소스)",
    ),
)

PROMPTS: tuple[tuple[str, str], ...] = (
    ("insurance_assistant_prompt", "보험 등록 및 병원 영수증 예상 보험금 계산 표준 AI 비서 지침"),
)

LIMITS: tuple[str, ...] = (
    "**모든 약관 수치는 아직 약관 원문과 대조하지 않았습니다(verified=false).** "
    "결과는 '예상치'이며 지급 확정이 아닙니다.",
    "실손 규칙은 약관 원문 검증이 완료되지 않아 세대와 관계없이 계산하지 않습니다.",
    "**특약별 가입금액은 증권이나 보장분석 리포트가 있어야 채워집니다.** "
    "보험협회 조회 결과(내보험찾아줌)에는 계약 목록만 있고 특약과 금액이 없습니다.",
    "서비스는 약관 PDF를 직접 읽지 않습니다. 가입 정보는 사용자가 AI에 올린 증권·앱 화면을 "
    "AI가 읽어 등록하며, 읽기 오류는 사용자가 확인해야 합니다.",
    "사용자 구분은 별명과 PIN 정도입니다. 개인정보 처리방침과 사용자별 인증은 아직 없습니다.",
    "자동차·여행 보험처럼 병원 영수증 청구 대상이 아닌 보험은 다루지 않습니다.",
)

QUESTIONS: tuple[str, ...] = (
    "고객 보장분석 리포트에서 담보명과 가입금액을 엑셀이나 표 같은 구조화된 형태로 "
    "받을 수 있습니까?",
    "고객이 가장 자주 오해하는 지급 조건은 무엇입니까? (예: 통깁스만 인정, 반깁스는 제외)",
    "이런 도구를 업무에 쓸 때 규제나 업무상 걸리는 점이 있습니까?",
)


def _example() -> str:
    """Run the real engine on a synthetic policy so the example can never be hand-written wrong."""
    rules = {rule.rule_id: rule for rule in STANDARD_RULES}
    policy = PolicyOut(
        policy_id="demo",
        company="예시화재",
        product_name="예시 종합보험",
        policy_type="COMPREHENSIVE",
        source_type="POLICY_CERTIFICATE",
        riders=[
            RiderOut(
                rider_id="r1",
                rider_name="골절진단비",
                coverage_amount=300000,
                mapped_rule_id="FRACTURE_DIAGNOSIS",
                source_type="POLICY_CERTIFICATE",
            ),
            RiderOut(
                rider_id="r2",
                rider_name="깁스치료비",
                coverage_amount=500000,
                mapped_rule_id="CAST_TREATMENT",
                source_type="POLICY_CERTIFICATE",
            ),
        ],
    )
    cases = (
        ("통깁스(석고붕대) 처치", "석고붕대(통깁스)"),
        ("부목(반깁스) 처치", "부목(반깁스)"),
    )
    lines: list[str] = []
    for label, treatment in cases:
        claim = ClaimInput(kcd_code="S82.1", treatment_name=treatment)
        result = evaluate_claim("demo", [policy], rules, claim)
        lines.append(f"### 같은 발목 골절(S82.1), {label}")
        for benefit in result.matched_benefits:
            lines.append(
                f"- {benefit.rider_name}: **{benefit.status}**, "
                f"예상 {benefit.estimated_amount:,}원 — {benefit.basis}"
            )
        lines.append(f"- 합계 예상: {result.total_estimated_payout:,}원")
        lines.append("")
    return "\n".join(lines)


def build_markdown(base_url: str = "") -> str:
    rules = "\n".join(
        f"- {rule.display_name} ({'검증됨' if rule.verified else '미검증'})"
        for rule in STANDARD_RULES
    )
    tools = "\n".join(f"- `{name}`: {desc}" for name, desc in TOOLS)
    resources = "\n".join(f"- `{uri}`: {desc}" for uri, desc in RESOURCES)
    prompts = "\n".join(f"- `{name}`: {desc}" for name, desc in PROMPTS)
    limits = "\n".join(f"- {item}" for item in LIMITS)
    questions = "\n".join(f"{i}. {q}" for i, q in enumerate(QUESTIONS, start=1))
    start_url = f"{base_url.rstrip('/')}/start" if base_url else "/start"
    return f"""# 보험 영수증 → 예상 보험금 계산 MCP (프로토타입)

> **이 문서를 읽는 AI에게:** 아래 내용을 바탕으로 사용자(보험설계사)에게 이 서비스가 무엇인지
> 쉬운 말로 설명하세요. 순서는 1) 한 줄 요약 2) 동작 흐름 3) 예시 4) 현재 한계 5) 설계사에게
> 묻고 싶은 질문입니다. **한계 부분은 빠뜨리지 말고 그대로 전달하세요.** 결과는 예상치이며
> 보험금 지급을 확정하거나 청구를 권유하는 표현을 쓰면 안 됩니다. 문서에 없는 기능이나 수치는
> 지어내지 마세요. 영어 요약: *An MCP server that estimates insurance payouts from hospital
> receipts against a user's registered policies. Prototype; policy figures are unverified.*

## AI 연결 시작
사람과 AI를 위한 [공개 연결 안내]({start_url})를 참고하세요.
이 안내에는 인증 키가 포함되어 있지 않습니다.

## 한 줄 요약
고객이 병원 영수증·약봉투를 AI 챗봇에 올리면, 고객이 등록한 보험을 기준으로
**청구 가능한 항목, 예상 금액, 필요 서류**를 알려 주는 도구입니다.

## 풀려는 문제
- 고객은 자기가 어떤 특약에 가입했는지, 어떤 병원비가 청구되는지 모르는 경우가 많습니다.
- 같은 치료라도 약관에 따라 지급이 갈립니다. 깁스치료비 특약은 통깁스만 되고
  반깁스(부목)는 제외되는 식입니다.

## 동작 흐름
1. 고객이 보험증권이나 보험앱 화면을 AI에 올리면, AI가 보험사·상품명·특약·가입금액을 읽어
   서비스에 등록합니다. (애매한 특약은 AI가 고객에게 되묻고 확정합니다.)
2. 고객이 병원 영수증·처방전을 올리면, AI가 질병코드(KCD)·진료비·처치를 읽어 서비스에 보냅니다.
3. 서비스가 등록된 보험과 규칙을 대조해 예상 보험금, 사유, 필요 서류를 돌려줍니다.

    "예시 (가상의 보험, 서비스 엔진 결과 — 규칙 검증 전)",
가입: 골절진단비 300,000원, 깁스치료비 500,000원 (가상 데이터)

{_example()}
## 제공 도구 (MCP Tools, {len(TOOLS)}개)
{tools}

## 제공 리소스 (MCP Resources, {len(RESOURCES)}개)
{resources}

## 제공 프롬프트 (MCP Prompts, {len(PROMPTS)}개)
{prompts}

## 지원하는 담보
{rules}

## 현재 한계 (정직하게)
{limits}

## 개인정보
- 영수증에서 읽은 질병코드와 진료비는 계산에만 쓰고 저장하지 않습니다.
- 저장하는 것은 별명, PIN 해시, 등록한 보험과 특약 목록입니다.
- 주민등록번호, 증권번호, 계좌번호는 받지 않습니다.

## 연결 방법
MCP 클라이언트(Antigravity, Claude, Cline 등)나 OpenAPI(ChatGPT 커스텀 GPT)로 연결합니다.
서버 접속에는 키가 필요하며, 이 소개 페이지에는 키를 싣지 않았습니다. 체험을 원하시면
개발자에게 문의하세요.

## 설계사님께 여쭙고 싶은 것
{questions}
"""


def build_html(base_url: str = "") -> str:
    """A plain server-rendered page: the Markdown in a <pre>, plus Open Graph tags for previews."""
    body = html.escape(build_markdown(base_url))
    start_url = f"{base_url.rstrip('/')}/start" if base_url else "/start"
    start_markdown_url = f"{base_url.rstrip('/')}/start.md" if base_url else "/start.md"
    description = html.escape(
        "병원 영수증을 AI에 올리면 가입한 보험 기준으로 받을 수 있는 보험금을 계산해 주는 "
        "MCP 프로토타입 소개 (예상치, 약관 미검증)"
    )
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>보험 영수증 → 예상 보험금 계산 MCP</title>
<meta name="description" content="{description}">
<meta property="og:type" content="website">
<meta property="og:title" content="보험 영수증 → 예상 보험금 계산 MCP (프로토타입)">
<meta property="og:description" content="{description}">
<link rel="alternate" type="text/markdown" href="/about.md">
</head>
<body>
<main>
<p><a href="{html.escape(start_url, quote=True)}">AI 연결 시작</a> ·
<a href="{html.escape(start_markdown_url, quote=True)}">연결 안내(Markdown)</a> ·
<a href="/about.md">소개(Markdown)</a> · <a href="/llms.txt">llms.txt</a></p>
<pre style="white-space: pre-wrap; font-family: inherit; line-height: 1.6">{body}</pre>
</main>
</body>
</html>
"""
