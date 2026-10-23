# MCP 클라이언트 연결 가이드

이 서비스의 보험 업무 인터페이스는 MCP입니다. REST 업무 API, OpenAPI 스키마, 웹 안내 페이지 및 Custom GPT Actions는 제공하지 않습니다.

## 원격 Streamable HTTP 연결

- MCP URL: `https://insurance-claim-mcp-878600435547.asia-northeast3.run.app/mcp`
- 인증 헤더: `X-User-Key: <사용자별 발급 키>` (또는 `Authorization: Bearer <키>`)
- 선택 헤더: `X-User-Id: <내 별명>`으로 도구 요청을 특정 사용자에 연결합니다. 키 소유자와 다르면 거부됩니다.
- 성공한 키 인증은 해당 계정의 PIN 입력을 대체합니다 (PIN 보호 계정도 키만으로 접근 가능).

키 발급은 운영자 전용 CLI로만 가능합니다. [사용자별 API/MCP 키](user-api-keys.md)를 참고하세요.

```json
{
  "mcpServers": {
    "insurance-claim": {
      "url": "https://insurance-claim-mcp-878600435547.asia-northeast3.run.app/mcp",
      "type": "streamableHttp",
      "headers": {
        "X-User-Key": "${INSURANCE_CLAIM_API_KEY}",
        "X-User-Id": "<내 별명>"
      }
    }
  }
}
```

클라이언트에서 환경변수 치환을 지원하지 않으면 해당 제품의 보호된 비밀 저장소를 사용하세요. 원문 키를 설정 예시·대화·로그에 넣지 마세요. PIN 보호 계정은 PIN을 공용 헤더나 설정 파일에 저장하지 말고 필요한 MCP 도구 호출에만 입력합니다.

## 로컬 stdio 연결

저장소 루트에서 가상 환경을 만들고 의존성을 설치한 뒤 MCP 서버를 실행합니다.

```powershell
python -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.lock.txt
.\\.venv\\Scripts\\python.exe -m claim_service.mcp.server
```

클라이언트의 stdio MCP 설정에는 실행 파일로 `.venv\Scripts\python.exe`, 인자로 `-m`, `claim_service.mcp.server`를 지정하고 `PYTHONPATH`에 저장소의 `src` 디렉터리를 설정합니다. 클라이언트의 환경변수 전달 기능으로 `DATABASE_URL`을 설정하세요. stdio 연결에는 HTTP API 키 인증이 적용되지 않습니다.

## 안전한 사용 흐름

1. 서비스 안내 및 시작 절차는 MCP `get_onboarding_guide` 또는 `insurance://guide/onboarding`으로 확인합니다.
2. 사용자 데이터가 필요하면 사용자 본인의 별명과 PIN(키 인증이 없는 환경)을 확인하고 MCP 도구를 사용합니다.
3. 보험 등록·갱신·특약 변경·삭제 전에는 변경 내용을 사용자에게 보여주고 명시적으로 확인받습니다.
4. 청구 평가 결과는 정보 제공용 예상치이며 보험사의 지급 여부나 금액을 확정하지 않습니다. 미검증 규칙은 추측해 계산하지 않습니다.
5. 발급 키, PIN, 주민등록번호, 증권번호, 계좌번호를 대화·로그에 남기지 않습니다.

서버 도구·리소스·프롬프트가 이 문서와 다르면 연결된 MCP 서버가 제공하는 최신 설명을 우선합니다.
