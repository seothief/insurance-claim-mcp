"""Public, secret-free instructions for connecting people and AI clients (KO / EN)."""

from __future__ import annotations

import html


def build_start_markdown_en(base_url: str = "", user_context_json: str | None = None) -> str:
    """Build the English connection guide for Expats in Korea and Global (US/JP) users."""
    origin = base_url.strip().rstrip("/")
    ai_prefix = f"{origin}/ai" if origin else "/ai"
    user_url_prefix = f"{origin}/u" if origin else "/u"
    context_block = ""
    if user_context_json:
        context_block = f"""
## Live Database Snapshot for Current User

The JSON below contains the user's live `profile`, registered `policies` & riders,
and `standard_rules` fetched directly from the server database.
- **Policy lookup questions**: Answer immediately in the user's language using `policies` below.
- **Hospital bill / EOB evaluation**: Compare the receipt against `policies` and `standard_rules`
  (respecting `verified: true` and `source_type: POLICY_CERTIFICATE`), explain estimated payouts
  and required claim documents in plain language, and provide a clickable `{ai_prefix}/evaluate?...`
  link for server verification.
- **Registering a new policy certificate / schedule of benefits**: Show the extracted table first,
  then provide a clickable `{ai_prefix}/register-policy?...` link so the user can save it with one
  tap (this automatically creates the `user_id` + `pin` account if new).

```json
{user_context_json}
```
"""
    return f"""# AI Insurance Claim & Coverage Assistant — Start Guide (Global & Korea Expat)

This service helps users check **estimated insurance payouts and required claim documents**
from hospital receipts / itemized bills without giving personal data (name, SSN/ARC, phone number,
policy number) to third-party lead-generation apps or calling insurance sales agents.
Results are informational estimates and do not guarantee claim approval.
{context_block}
## Instructions for the AI Assistant

If the user shared this link in ChatGPT, Claude, Gemini, or an Agentic Browser AI (e.g., Aside):

1. **Default Mode (No API Key, No App Install Required)**:
   - **Never ask the user for an API key or MCP configuration.**
   - Immediately use the **Keyless Web Bridge (`/u/*`, `/ai/*`)** below to onboard the user
     (`user_id` + `pin` of 4–32 characters; longer passcodes are recommended for security),
     register their policy riders, or evaluate hospital receipts.
2. **Supported Markets & Use Cases**:
   - **Use Case A — Foreign Residents / Expats in Korea**:
     - Translate and parse Korean insurance policy certificates (`보험증권`) or the official
       **Korea Credit Information Services (`credit4u.or.kr`) > `[보험신용정보]` >**
       **`[정액형보험]` / `[실손형보험]`** detail tables
       (`보장구분 | 보장명 | 보장상태 | 보장금액`).
     - If you are an **Agentic Browser AI (e.g., Aside)** and the user is logged into
       `credit4u.or.kr`, iterate through each contract's detail table, **export a clean CSV**
       (`Company,Product,Category,RiderName,Status,CoverageAmount`), and register them directly.
     - When evaluating Korean hospital bills (`진료비 계산서·영수증` and `진료비 세부내역서`),
       map `급여` (NHIS covered copay) to `cost_covered`, `비급여` (non-covered) to
       `cost_uncovered`, and Korean `KCD` codes (identical to WHO `ICD-10`).
   - **Use Case B — US / Japan / Global Insurance Users**:
     - Register **US Supplemental Health / Accident / Hospital Indemnity** policies (e.g., Aflac,
       MetLife, Cigna, Colonial Life — `Fracture Benefit`, `Hospital Indemnity / Daily Confinement`,
       `ER Visit`, `Illness/Accident Surgery`, `Suture/Laceration`, `Burn`, `Cast`, `Flu`) or
       **Japanese Medical/Accident policies (`医療保険・傷害保険` — `骨折`, `入院日額`,**
       **`手術給付金`, `ギプス`, `創傷縫合`)** from a Policy Certificate / Schedule of Benefits.
     - Evaluate Itemized Hospital Bills & EOBs using standard **ICD-10** diagnosis codes
       (`kcd_code`), procedure/CPT descriptions (`treatment_name`), inpatient days
       (`inpatient_days`), and covered vs. non-covered/out-of-pocket amounts.

## Keyless Web Bridge Endpoints (`/u/*`, `/ai/*`)

- **Single-Fetch User Snapshot (Recommended for Mobile ChatGPT / Claude / Gemini)**:
  `{user_url_prefix}/{{user_id}}/{{pin}}/en`
  (Opening this single URL returns the user's profile, all registered policies/riders, and rules.)
- **Action Links (Open directly or present as a clickable Markdown link for the user to tap)**:
  1. **Register or Update Policy (Auto-creates `user_id` + `pin` on first use)**:
     `{ai_prefix}/register-policy?user_id={{user_id}}&pin={{pin}}&company={{Insurer}}&product_name={{PlanName}}&policy_type={{COMPREHENSIVE|SILSON|FIXED_BENEFIT|DRIVER|DENTAL|OTHER}}&source_type=POLICY_CERTIFICATE&issuer={{Insurer}}&issued_on={{YYYY-MM-DD}}&riders={{RiderName1}}:{{Amount1}}|{{RiderName2}}:{{Amount2}}`
  2. **Resolve Ambiguous Rider**:
     `{ai_prefix}/resolve-rider?user_id={{user_id}}&pin={{pin}}&rider_id={{rider_id}}&mapping_status={{MAPPED|IGNORED}}&mapped_rule_id={{rule_id}}`
  3. **List Registered Policies**:
     `{ai_prefix}/policies?user_id={{user_id}}&pin={{pin}}`
  4. **Evaluate Hospital Bill / Receipt**:
     `{ai_prefix}/evaluate?user_id={{user_id}}&pin={{pin}}&kcd_code={{ICD10_or_KCD}}&treatment_name={{Procedure}}&cost_covered={{CoveredAmount}}&cost_uncovered={{UncoveredAmount}}&hospital_type={{clinic|hospital|general}}&is_inpatient={{true|false}}&inpatient_days={{Days}}`

- [한국어 안내 (`/start`)](/start) · [Service Intro (`/`)](/)
"""


def build_start_markdown(
    base_url: str = "", user_context_json: str | None = None, lang: str = "ko"
) -> str:
    """Build the public connection guide using the configured service domain, if available."""
    if lang.lower().startswith("en"):
        return build_start_markdown_en(base_url, user_context_json)
    origin = base_url.strip().rstrip("/")
    mcp_url = f"{origin}/mcp" if origin else "/mcp"
    openapi_url = f"{origin}/openapi.json" if origin else "/openapi.json"
    ai_prefix = f"{origin}/ai" if origin else "/ai"
    user_url_prefix = f"{origin}/u" if origin else "/u"
    context_block = ""
    if user_context_json:
        context_block = f"""
## 현재 로그인된 사용자의 실시간 DB 데이터

아래 JSON은 서버 DB에서 즉시 조회된 현재 사용자의 프로필(`profile`), 등록된 보험·특약(`policies`),
그리고 서버 표준 담보 규칙(`standard_rules`)입니다.
- **내 보험 조회 질문**: 별도 URL을 다시 열지 말고 아래 `policies` 데이터로 즉시 안내하세요.
- **영수증/진료비 사진 평가 질문**: 아래 `policies`와 `standard_rules`를 대조해(`verified: true` 및
  `source_type: POLICY_CERTIFICATE` 조건 준수) 즉시 예상 보험금과 구비서류를 설명하고,
  서버 정밀 계산을 위한 `{ai_prefix}/evaluate?...` 클릭 링크도 함께 제공하세요.
- **새 보험증권 사진 등록 질문**: 사진에서 읽은 내용을 먼저 표로 보여준 뒤, 사용자가 스마트폰에서
  한 번만 터치해 공통 DB에 바로 저장할 수 있도록 `{ai_prefix}/register-policy?...` 클릭 링크를
  제공하세요.

```json
{user_context_json}
```
"""
    return f"""# 보험 청구 도우미 연결 안내

이 서비스는 AI가 보험 가입 정보와 병원 영수증을 바탕으로
**예상 보험금과 필요 서류**를 안내하는 MCP 서비스입니다. 결과는 예상치이며 보험금 지급을
확정하지 않습니다. (English Guide: [`/start/en`](/start/en))
{context_block}
## AI 사용자용 안내

사용자가 이 안내를 공유했다면 다음 순서로 도와주세요.

1. **기본 진행 방식 (일반 채팅 사용자 — API 키·설치 불필요)**:
   - 사용자가 ChatGPT, Claude, Gemini 등 채팅창에 이 안내 링크를 공유했다면
     **절대 API 키나 MCP 설정을 요구하지 마세요.**
   - 즉시 아래 **[스마트폰 무료 AI 앱 웹 브릿지 (`/u/*`, `/ai/*`)]** 주소를 사용해
     사용자 등록(ID + 4자 이상 PIN/비밀번호, 4~32자이며 길수록 안전), 보험증권 업로드,
     영수증 계산을 도와주세요.
2. **고급 연동 (운영자 공용 API 키 보유자 전용)**:
   - 사용자가 서비스 운영자가 신뢰할 수 있는 비공개 경로로 제공한 **공용 API 키**를
     보유하고 MCP 클라이언트나 OpenAPI Actions 설정 방법을 명시적으로 요청한 경우에만
     하단의 설정을 안내합니다. 이 공개 페이지, 프롬프트, 코드 저장소에는 키가 없습니다.
     키를 공개 채팅이나 저장소에 붙여넣지 마세요.
3. MCP 연결에는 아래 서버 주소와 `X-API-Key` 헤더를 사용합니다. 사용자 구분용 `X-User-Id`는
   본인이 정한 별명으로 설정할 수 있습니다. 이는 인증 수단이 아닙니다. PIN 보호 계정은
   `X-User-Pin` 또는 도구의 PIN 입력도 필요합니다.
4. 연결 후 `get_onboarding_guide`(또는 `{ai_prefix}/guide`)를 가장 먼저 호출합니다. 사용자 프로필을
   확인하고, 보험증권/보장내역은 내용을 보여 준 뒤 확인받아 등록합니다.
   - **특약·보장금액 한 번에 확보 안내 (`credit4u.or.kr`)**: 사용자에게 보험증권이 없다면
     **한국신용정보원 본인신용정보 열람서비스(`credit4u.or.kr`) > `보험신용정보` >**
     **`정액형보험` / `실손형보험`** 상세 화면의 하단 표(`보장구분`·`보장명`·`보장상태`·`보장금액`)
     또는 우측 상단 **`[정액형보장 상세내역 발급]`**(인쇄/PDF)을 가져오도록 안내하세요.
     **에이전트형·브라우저 제어 AI(Aside 등)**라면 사용자가 로그인한 상태에서 모든 계약의
     상세 화면을 순회하며 표를 읽어 **CSV(`보험사,상품명,보장구분,보장명,보장상태,보장금액`)로**
     **먼저 깔끔하게 정리·저장해 준 뒤**, 그 데이터를 바탕으로 바로 등록하세요.
     (일반 채팅 AI도 그렇게 정리된 CSV나 캡처/PDF를 받아 바로 등록할 수 있습니다.)
5. 영수증이나 처방전은 계산 요청에만 사용합니다. 결과는 예상치로 안내하고
   지급 확정 표현을 하지 않습니다.

## 스마트폰 무료 AI 앱 웹 브릿지 (`/u/*`, `/ai/*`, 설치·API 키 불필요)

MCP나 Custom GPT 설정이 없는 스마트폰 AI 앱(무료 ChatGPT, Gemini, Claude 기본 채팅창)에서는
다음 방법을 사용하세요. 모든 데이터는 공통 DB에 저장되어 다른 AI 앱에서도 이어서 조회됩니다.

- **한 번에 내 보험 DB 불러오기 (ChatGPT 모바일 앱 권장)**:
  사용자가 채팅창에 `{user_url_prefix}/{{user_id}}/{{pin}}` 주소를 보내면, 해당 웹페이지 본문에
  사용자의 프로필·등록 보험 전체 목록·표준 규칙이 즉시 포함되어 반환됩니다.
  (AI가 임의의 새 URL을 직접 열지 못하는 샌드박스 환경이라면, 사용자에게
  `{user_url_prefix}/{{user_id}}/{{pin}}` 주소를 채팅창에 그대로 입력해 달라고 안내하세요.)
- **세부 작업용 주소 (직접 웹 읽기 호출 또는 사용자 터치용 클릭 링크 제공)**:
  AI가 직접 URL을 열 수 있으면 바로 호출하고, 직접 열 수 없는 환경(모바일 ChatGPT 등)에서는
  아래 주소를 **클릭 가능한 마크다운 링크**로 만들어 사용자가 한 번 터치해 실행하도록 안내하세요.

1. **가입 및 내 등록 현황 조회**:
   `{ai_prefix}/onboard?user_id={{user_id}}&pin={{pin}}&display_alias={{별칭}}`
2. **개인 보험증권 업로드(등록/갱신)** — 증권 사진 내용을 사용자에게 확인받은 뒤 호출/링크 제공:
   `{ai_prefix}/register-policy?user_id={{user_id}}&pin={{pin}}&company={{보험사}}&product_name={{상품명}}&policy_type={{COMPREHENSIVE|SILSON|FIXED_BENEFIT|DRIVER|DENTAL|OTHER}}&source_type=POLICY_CERTIFICATE&issuer={{보험사}}&issued_on={{YYYY-MM-DD}}&riders={{특약명1}}:{{가입금액1}}|{{특약명2}}:{{가입금액2}}`
3. **애매한 특약 확정** (`unresolved_riders`가 있을 때 사용자 확인 후 호출/링크 제공):
   `{ai_prefix}/resolve-rider?user_id={{user_id}}&pin={{pin}}&rider_id={{rider_id}}&mapping_status={{MAPPED|IGNORED}}&mapped_rule_id={{rule_id}}`
4. **내 등록 보험 목록 조회**:
   `{ai_prefix}/policies?user_id={{user_id}}&pin={{pin}}`
5. **병원 영수증으로 예상 보험금 계산** (질병코드·처치명·진료비를 읽어 호출/링크 제공):
   `{ai_prefix}/evaluate?user_id={{user_id}}&pin={{pin}}&kcd_code={{질병코드}}&treatment_name={{처치명}}&cost_covered={{급여}}&cost_uncovered={{비급여}}&hospital_type={{clinic|hospital|general}}`

## MCP 연결

- 전송 방식: Streamable HTTP
- MCP 서버: `{mcp_url}`
- 헤더: `X-API-Key: <운영자가 안전하게 제공한 공용 키>`
- 선택 헤더: `X-User-Id: <사용자 별명>`

MCP 클라이언트 설정 예시 (자리표시자를 클라이언트의 비밀 저장 기능으로 설정):

```json
{{
  "mcpServers": {{
    "insurance-claim": {{
      "type": "streamableHttp",
      "url": "{mcp_url}",
      "headers": {{
        "X-API-Key": "<공용 키를 안전한 비밀 설정에서 참조>",
        "X-User-Id": "<내 별명>"
      }}
    }}
  }}
}}
```

## OpenAPI Actions 연결

- OpenAPI 스키마: `{openapi_url}`
- Actions 인증: API key를 헤더(`X-API-Key`)로 설정
- 같은 공용 키를 사용합니다. API 키는 공개 스키마나 이 문서에 포함되어 있지 않습니다.

## 안전 및 한계

- MCP/OpenAPI 접근은 공용 API 키를 사용하며, 모바일 웹 브릿지(`/ai/*`)는 사용자별 4자리 이상 PIN과
  연속 실패 차단(Rate Limit)으로 보호됩니다.
- 공용 키가 바뀌면 기존 키를 쓰는 모든 연결의 설정을 갱신해야 합니다. 새 키는 운영자의
  안내를 받은 뒤 안전한 비밀 설정에만 입력하세요.
- 약관 수치는 원문과 대조되지 않은 미검증 예상치일 수 있습니다. 결과는 지급 보장이 아니며
  실제 지급 여부는 보험사의 심사에 따릅니다.
- 보험증권/영수증 이미지에서 읽은 내용을 등록·계산 전에 사용자가 확인해야 합니다.
  진료 정보는 계산 입력으로만 사용하며 저장하지 않습니다.
- [서비스 소개](/) · [English Guide](/start/en) · [llms.txt](/llms.txt)
"""


def build_start_html(
    base_url: str = "", user_context_json: str | None = None, lang: str = "ko"
) -> str:
    """Render the Markdown guide as a minimal HTML page."""
    is_en = lang.lower().startswith("en")
    markdown = html.escape(build_start_markdown(base_url, user_context_json, lang=lang))
    html_lang = "en" if is_en else "ko"
    title = (
        "AI Insurance Claim Assistant — Start Guide"
        if is_en
        else "보험 청구 도우미 연결 안내"
    )
    return f"""<!doctype html>
<html lang="{html_lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{title}">
<title>{title}</title>
<link rel="alternate" type="text/markdown" href="/start.md">
</head>
<body>
<main>
<p><a href="/">서비스 소개</a> · <a href="/start">한국어</a> ·
<a href="/start/en">English</a> · <a href="/start.md">Markdown</a></p>
<pre style="white-space: pre-wrap; font-family: inherit; line-height: 1.6">{markdown}</pre>
</main>
</body>
</html>
"""
