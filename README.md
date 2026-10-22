# insurance-claim-mcp

약봉투·진료비 영수증의 정보(KCD 질병코드, 처치, 진료비)를 가입 보험 약관과 대조해 **예상 보험금**을 안내하는 MCP(Model Context Protocol) 서비스입니다.

> 정보 제공용 예상치입니다. 실제 지급 여부와 금액은 보험사 심사에 따라 달라집니다.

## 핵심 설계 및 아키텍처

- **LLM 추론 + 결정론적(Deterministic) 규칙 엔진 분리**
  - 비정형 데이터(보험증권·병원 영수증 이미지) 판독과 사용자 대화는 AI 클라이언트가 수행하고, 환각(Hallucination)이 없어야 하는 약관 대조 및 예상 보험금 계산은 서버 규칙 엔진이 전담합니다.
  - **Fail-Closed 안전장치**: 약관 원문 검증(`verified=true`)이 완료되지 않았거나 보험증권(`POLICY_CERTIFICATE`) 출처가 확인되지 않은 특약은 추측 계산하지 않고 `NOT_EVALUATED`(0원)로 반환합니다.
- **MCP 3대 구성요소(Tools · Resources · Prompts) 표준 구현**
  - **Tools (11개)**: 사용자 등록(`register_user`), 보험 등록/갱신(`register_user_policy`), 미매핑 특약 재질의 확정(`resolve_user_rider`), 예상 보험금 계산(`evaluate_claim`) 등 상태 변경 및 연산 수행
  - **Resources (3개)**: 온보딩 가이드(`insurance://guide/onboarding`), 표준 담보 규칙 카탈로그(`insurance://rules/standard`), 보험사 공식 서류 요청 안내 동적 템플릿(`insurance://guide/document-request/{policy_type}/{product_name}`)
- **Prompts (1개)**: 단계별 보험 등록 및 영수증 평가를 유도하는 표준 AI 비서 지침(`insurance_assistant_prompt`) 및 `ai_follow_up_prompt` 기반 역질문 오케스트레이션
- **MCP 전용 인터페이스 및 서버리스 최적화**
  - 보험 업무는 **FastMCP (`Streamable HTTP /mcp` 및 로컬 `stdio`)**로만 제공합니다. Cloud Run 상태 확인용 `/api/health`, `/api/version` 외에는 REST API, OpenAPI 스키마, 웹 브리지 또는 소개 페이지를 제공하지 않습니다.
  - Cloud Run 서버리스 스케일링 환경을 위해 `stateless_http=True` 및 `combine_lifespans`를 적용하고, 리버스 프록시 뒤에서 `/mcp` 307 리다이렉트 시 발생하는 HTTPS→HTTP 다운그레이드를 ASGI 미들웨어 경로 정규화로 해결했습니다.

## 로컬 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m uvicorn claim_service.main:app --app-dir src --port 8080
```
- 상태 확인: `GET /api/health`, `GET /api/version` (인증 불필요)
- MCP 엔드포인트 (Streamable HTTP): `POST /mcp` (또는 `/mcp/`)
- MCP 로컬 실행 (stdio): `.\.venv\Scripts\python.exe -m claim_service.mcp.server`

## 데이터베이스 및 보안

- 기본: 로컬 SQLite (`claim_service.db`, 프로젝트 루트에 생성되며 `.gitignore`로 커밋 제외)
- 클라우드: 환경변수 `DATABASE_URL`을 PostgreSQL URL로 지정 (예: `postgresql+psycopg://...`)
- 평가 요청(질병코드, 진료비)은 저장하지 않고 계산 결과만 반환합니다.
- MCP HTTP 접근은 서버 공용 `X-API-Key`(`hmac.compare_digest` 상수 시간 비교)로 인증합니다. `X-User-Id`는 요청을 특정 사용자 별명에 귀속시키며 인증을 대체하지 않습니다. PIN 보호 계정은 `PBKDF2-HMAC-SHA256`(120,000회 반복) 해시로 검증을 유지합니다. [클라이언트 연결 가이드](docs/mcp-client-setup.md)를 참조하세요.

## 테스트 및 정적 분석

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m mypy src
```

## 배포

`main`에 CI를 통과한 변경을 병합하면 GitHub Actions가 Cloud Run에 자동 배포하고
`/api/health`, `/api/version`을 확인합니다. 수동 배포는 GitHub의
**Actions → Deploy to Cloud Run → Run workflow** 한 번으로 실행할 수 있습니다.
최초 설정에 필요한 GitHub 변수, Workload Identity Federation 및 권한은
[배포 설정 안내](docs/deployment.md)를 참조하세요. 운영 배포는 이 로컬 작업에서 실행하지 않습니다.

## 진행 현황
[STATUS.md](STATUS.md)
