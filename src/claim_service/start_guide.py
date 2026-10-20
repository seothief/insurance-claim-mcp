"""Public, secret-free instructions for connecting people and AI clients."""

from __future__ import annotations

import html


def build_start_markdown(base_url: str = "") -> str:
    """Build the public connection guide using the configured service domain, if available."""
    origin = base_url.strip().rstrip("/")
    mcp_url = f"{origin}/mcp" if origin else "/mcp"
    openapi_url = f"{origin}/openapi.json" if origin else "/openapi.json"
    ai_prefix = f"{origin}/ai" if origin else "/ai"
    return f"""# 보험 청구 도우미 연결 안내

이 서비스는 AI가 보험 가입 정보와 병원 영수증을 바탕으로
**예상 보험금과 필요 서류**를 안내하는 MCP 서비스입니다. 결과는 예상치이며 보험금 지급을
확정하지 않습니다.

## AI 사용자용 안내

사용자가 이 안내를 공유했다면 다음 순서로 도와주세요.

1. 연결할 AI 클라이언트가 MCP Streamable HTTP 또는 OpenAPI Actions를 지원하는지 확인합니다.
   - **지원하는 환경(Claude, Antigravity, Cline, Custom GPT 등)**:
     아래 MCP 또는 OpenAPI 설정을 안내합니다.
   - **지원하지 않는 일반 스마트폰 AI 앱(ChatGPT 무료 앱, Gemini 앱, Claude 기본 채팅 등)**:
     별도 API 키 설정 없이 아래 **[스마트폰 무료 AI 앱 웹 브릿지 (`/ai/*`)]** 주소를
     웹 읽기(GET) 도구로 호출해 사용자 등록, 보험증권 업로드, 영수증 계산을 수행합니다.
2. MCP/OpenAPI 연결 시에는 서비스 운영자가 신뢰할 수 있는 비공개 경로로 제공한 **공용 API 키**를
   클라이언트의 비밀 헤더 설정에 입력합니다. 이 공개 페이지, 프롬프트, 코드 저장소에는
   키가 없습니다. 키를 공개 채팅이나 저장소에 붙여넣지 마세요.
3. MCP 연결에는 아래 서버 주소와 `X-API-Key` 헤더를 사용합니다. 사용자 구분용 `X-User-Id`는
   본인이 정한 별명으로 설정할 수 있습니다. 이는 인증 수단이 아닙니다. PIN 보호 계정은
   `X-User-Pin` 또는 도구의 PIN 입력도 필요합니다.
4. 연결 후 `get_onboarding_guide`(또는 `{ai_prefix}/guide`)를 가장 먼저 호출합니다. 사용자 프로필을
   확인하고, 보험증권/보장내역은 내용을 보여 준 뒤 확인받아 등록합니다.
5. 영수증이나 처방전은 계산 요청에만 사용합니다. 결과는 예상치로 안내하고
   지급 확정 표현을 하지 않습니다.

## 스마트폰 무료 AI 앱 웹 브릿지 (`/ai/*`, 설치·API 키 불필요)

MCP나 Custom GPT 설정이 없는 스마트폰 AI 앱(무료 ChatGPT, Gemini, Claude 기본 채팅창)에서는
사용자에게 **별명(`user_id`, 영문/숫자)과 본인 확인용 PIN(4자리 이상)**을 물어본 뒤,
AI의 웹 읽기(GET) 기능으로 아래 주소를 순서대로 호출하세요. 모든 데이터는 공통 DB에 저장되어
다른 AI 앱에서도 이어서 조회됩니다.

1. **가입 및 내 등록 현황 조회**:
   `{ai_prefix}/onboard?user_id={{user_id}}&pin={{pin}}&display_alias={{별칭}}`
2. **개인 보험증권 업로드(등록/갱신)** — 증권 사진에서 읽은 내용을 사용자에게 먼저 확인받은 뒤 호출:
   `{ai_prefix}/register-policy?user_id={{user_id}}&pin={{pin}}&company={{보험사}}&product_name={{상품명}}&policy_type={{COMPREHENSIVE|SILSON|FIXED_BENEFIT|DRIVER|DENTAL|OTHER}}&source_type=POLICY_CERTIFICATE&issuer={{보험사}}&issued_on={{YYYY-MM-DD}}&riders={{특약명1}}:{{가입금액1}}|{{특약명2}}:{{가입금액2}}`
3. **애매한 특약 확정** (`unresolved_riders`가 있을 때 사용자 확인 후 호출):
   `{ai_prefix}/resolve-rider?user_id={{user_id}}&pin={{pin}}&rider_id={{rider_id}}&mapping_status={{MAPPED|IGNORED}}&mapped_rule_id={{rule_id}}`
4. **내 등록 보험 목록 조회**:
   `{ai_prefix}/policies?user_id={{user_id}}&pin={{pin}}`
5. **병원 영수증으로 예상 보험금 계산** (영수증 사진에서 질병코드·처치명·진료비를 읽어 호출):
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
- [서비스 소개](/) · [llms.txt](/llms.txt)
"""


def build_start_html(base_url: str = "") -> str:
    """Render the Markdown guide as a minimal HTML page."""
    markdown = html.escape(build_start_markdown(base_url))
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="사람과 AI를 위한 보험 청구 도우미 연결 안내">
<title>보험 청구 도우미 연결 안내</title>
<link rel="alternate" type="text/markdown" href="/start.md">
</head>
<body>
<main>
<p><a href="/">서비스 소개</a> · <a href="/start.md">Markdown</a></p>
<pre style="white-space: pre-wrap; font-family: inherit; line-height: 1.6">{markdown}</pre>
</main>
</body>
</html>
"""
