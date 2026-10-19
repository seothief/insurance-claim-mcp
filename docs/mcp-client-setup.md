# AI 클라이언트(Gemini, Claude, Cline, ChatGPT) 연결 가이드

처음 연결할 때는 서비스의 공개 [시작 안내](/start) 또는 [Markdown 안내](/start.md)를
참고하세요. 공개 안내에는 공용 API 키가 포함되지 않습니다. 아래 상세 설정도 키를
`<서버 공용 API_KEY>` 자리표시자로 나타내며, 실제 값은 운영자가 신뢰할 수 있는 별도 비밀
전달 경로로 제공해야 합니다.

이 서비스는 별도의 사용자 UI를 두지 않고 **`사용자 ↔ AI ↔ 서비스(MCP / OpenAPI)`** 구조로 동작합니다.
사용자는 자신이 구독 중인 AI와 대화하며 보험 화면 캡처나 병원 영수증 사진을 올리고, AI가 직접 서버 도구를 호출합니다.

## 공통 접속 정보
- **서버 기본 주소**: `https://insurance-claim-mcp-878600435547.asia-northeast3.run.app`
- **MCP 엔드포인트 (Streamable HTTP)**: `https://insurance-claim-mcp-878600435547.asia-northeast3.run.app/mcp` (`/mcp`와 `/mcp/` 모두 동작)
- **OpenAPI 스키마 주소**: `https://insurance-claim-mcp-878600435547.asia-northeast3.run.app/openapi.json`
- **인증 헤더**: `X-API-Key: <서버 API_KEY>` 또는 `Authorization: Bearer <서버 API_KEY>`
  (클라우드 배포 환경에서는 GCP Secret Manager의 `API_KEY` 시크릿으로 주입)

모든 요청에는 서버 공용 `X-API-Key`가 필요합니다. 사용자 데이터가 필요한 AI 클라이언트는 본인의 `X-User-Id`를 설정해 해당 별명에 요청을 귀속시킬 수 있습니다. 사용자 ID는 인증 수단이 아니며, 이를 통해 PIN 보호가 해제되지 않습니다. PIN 보호 계정은 `X-User-Pin` 또는 도구의 PIN 입력도 필요합니다.

---

## 1. Google Gemini CLI (`@google/gemini-cli`) 연결

1. 설치 및 구글 계정 로그인 (Google AI Plus 계정 사용 가능):
   ```powershell
   npm.cmd install -g @google/gemini-cli
   gemini
   ```
2. 설정 파일(`C:\Users\<사용자>\.gemini\settings.json`)에 MCP 서버 등록:
   ```json
   {
     "mcpServers": {
       "insurance-claim": {
         "httpUrl": "https://insurance-claim-mcp-878600435547.asia-northeast3.run.app/mcp",
         "headers": {
             "X-API-Key": "<서버 공용 API_KEY>",
             "X-User-Id": "<내 별명>"
         }
       }
     }
   }
   ```
3. 대화 시작 후 보험 캡처 이미지나 영수증 사진을 전달하면 Gemini가 자동으로 도구를 호출합니다.

---

## 2. Cline / Cursor / Windsurf / Claude Desktop 연결

MCP 설정 JSON(예: Cline의 `cline_mcp_settings.json`)에 아래 항목을 추가합니다:

```json
{
  "mcpServers": {
    "insurance-claim": {
      "url": "https://insurance-claim-mcp-878600435547.asia-northeast3.run.app/mcp",
      "type": "streamableHttp",
      "headers": {
        "X-API-Key": "<서버 공용 API_KEY>",
        "X-User-Id": "<내 별명>"
      },
      "disabled": false,
      "autoApprove": [
        "get_onboarding_guide",
        "get_user_profile",
        "list_standard_rules",
        "list_user_policies",
        "evaluate_claim"
      ]
    }
  }
}
```
- 조회·계산 도구는 `autoApprove`에 넣어 즉시 실행되게 하고, 데이터를 변경하는 `register_user`, `register_user_policy`, `resolve_user_rider`, `delete_user_policy`는 AI가 사용자에게 확인한 뒤 호출하게 합니다.

---

## 3. Antigravity 연결 (`mcp_config.json`)

Antigravity의 MCP 설정 파일(`C:\Users\<사용자>\.gemini\config\mcp_config.json`)에 Cloud Run 원격 서버를 등록합니다:

```json
{
  "mcpServers": {
    "insurance-claim": {
      "serverUrl": "https://insurance-claim-mcp-878600435547.asia-northeast3.run.app/mcp",
      "headers": {
        "X-API-Key": "<서버 공용 API_KEY>",
        "X-User-Id": "<내 별명>"
      }
    }
  }
}
```
- PIN 보호 계정이면 본인 전용 설정의 `"headers"`에 `"X-User-Pin": "<내 PIN>"`도 추가합니다. 공용 `X-API-Key`는 서버 접근 인증이며 사용자별 인증이 아니므로 안전하게 보호하세요.


---

## 4. ChatGPT (Custom GPT Actions) 연결
- `docs/chatgpt-custom-gpt-guide.md` 문서를 참고해 `https://insurance-claim-mcp-878600435547.asia-northeast3.run.app/openapi.json`을 불러오고 `X-API-Key` 헤더를 설정합니다.

---

## 5. AI가 따르는 표준 대화 흐름 (서버 내장 지침)
서버의 MCP `instructions` 및 `insurance_assistant_prompt`에 아래 순서가 내장되어 있습니다:
1. **별명 확인 (`get_user_profile` → 없으면 `register_user`)**
2. **보험 등록 (`register_user_policy`)**: 이미지에서 읽은 보험사·상품명·특약·금액을 사용자에게 먼저 보여주고 확인받은 뒤 호출 (휴먼 에러 및 OCR 오류 방지)
3. **애매한 특약 재질의 (`resolve_user_rider`)**: `unresolved_riders`가 반환되면 증권을 다시 확인하거나 사용자에게 물어 `MAPPED` / `CUSTOM` / `IGNORED`로 확정
4. **영수증 계산 (`evaluate_claim`)**: 급여/비급여/질병코드/처치명을 읽어 예상 보험금과 필요 서류 안내 (모든 약관 수치는 `verified: false`이므로 예상치로만 안내)
