"""Public, secret-free instructions for connecting people and AI clients."""

from __future__ import annotations

import html


def build_start_markdown(base_url: str = "") -> str:
    """Build the public connection guide using the configured service domain, if available."""
    origin = base_url.strip().rstrip("/")
    mcp_url = f"{origin}/mcp" if origin else "/mcp"
    openapi_url = f"{origin}/openapi.json" if origin else "/openapi.json"
    return f"""# 보험 청구 도우미 연결 안내

이 서비스는 AI가 보험 가입 정보와 병원 영수증을 바탕으로
**예상 보험금과 필요 서류**를 안내하는 MCP 서비스입니다. 결과는 예상치이며 보험금 지급을
확정하지 않습니다.

## AI 사용자용 안내

사용자가 이 안내를 공유했다면 다음 순서로 도와주세요.

1. 연결할 AI 클라이언트가 MCP Streamable HTTP 또는 OpenAPI Actions를 지원하는지 확인합니다.
2. 서비스 운영자가 신뢰할 수 있는 비공개 경로로 제공한 **공용 API 키**를 클라이언트의
   비밀 헤더 설정에 입력합니다. 이 공개 페이지, 프롬프트, 코드 저장소에는 키가 없습니다.
   키를 공개 채팅이나 저장소에 붙여넣지 마세요.
3. MCP 연결에는 아래 서버 주소와 `X-API-Key` 헤더를 사용합니다. 사용자 구분용 `X-User-Id`는
   본인이 정한 별명으로 설정할 수 있습니다. 이는 인증 수단이 아닙니다. PIN 보호 계정은
   `X-User-Pin` 또는 도구의 PIN 입력도 필요합니다.
4. 연결 후 `get_onboarding_guide`를 가장 먼저 호출합니다. 사용자 프로필을 확인하고,
   보험증권/보장내역은 내용을 보여 준 뒤 확인받아 등록합니다.
5. 영수증이나 처방전은 계산 요청에만 사용합니다. 결과는 예상치로 안내하고
   지급 확정 표현을 하지 않습니다.

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

- 서버 접근은 모든 사용자에게 동일한 공용 API 키를 사용합니다. 별명은 사용자 인증을
  대체하지 않습니다.
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