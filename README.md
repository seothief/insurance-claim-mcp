# insurance-claim-mcp

약봉투·진료비 영수증의 정보(KCD 질병코드, 처치, 진료비)를 가입 보험 약관과 대조해 **예상 보험금**을 안내하는 MCP(Model Context Protocol) 서비스입니다.

> 정보 제공용 예상치입니다. 실제 지급 여부와 금액은 보험사 심사에 따라 달라집니다.

## 핵심 설계 및 아키텍처

- **LLM 추론 + 결정론적(Deterministic) 규칙 엔진 분리**
  - 비정형 데이터(보험증권·병원 영수증 이미지) 판독과 사용자 대화는 AI 클라이언트가 수행하고, 환각(Hallucination)이 없어야 하는 약관 대조 및 예상 보험금 계산은 서버 규칙 엔진이 전담합니다.
  - **기본 검증 게이트**: 증권 출처가 아닌 항목은 계산에서 제외해 별도 표시하고, 미검증 규칙은 원칙적으로 `NOT_EVALUATED`(0원)로 계산을 보류합니다.
  - **현재 override 예외**: 정책·특약이 `POLICY_CERTIFICATE`로 분류되고 `MAPPED` 특약에 `rule_config_override`가 있으면, 미검증 표준 규칙 대신 해당 조건으로 계산할 수 있습니다. 출처 분류는 클라이언트가 제출한 값이며 서버의 약관 원문 대조 완료를 의미하지 않습니다. V2의 출처 진술·조건 검증 분리는 아래 설계 문서의 제안이며 아직 구현되지 않았습니다.
- **MCP 3대 구성요소(Tools · Resources · Prompts) 표준 구현**
  - **Tools (11개)**: 사용자 등록(`register_user`), 보험 등록/갱신(`register_user_policy`), 미매핑 특약 재질의 확정(`resolve_user_rider`), 예상 보험금 계산(`evaluate_claim`) 등 상태 변경 및 연산 수행
  - **Resources (3개)**: 온보딩 가이드(`insurance://guide/onboarding`), 표준 담보 규칙 카탈로그(`insurance://rules/standard`), 보험사 공식 서류 요청 안내 동적 템플릿(`insurance://guide/document-request/{policy_type}/{product_name}`)
- **Prompts (1개)**: 단계별 보험 등록 및 영수증 평가를 유도하는 표준 AI 비서 지침(`insurance_assistant_prompt`) 및 `ai_follow_up_prompt` 기반 역질문 오케스트레이션
- **MCP 전용 인터페이스 및 서버리스 최적화**
  - 보험 업무는 **FastMCP (`Streamable HTTP /mcp` 및 로컬 `stdio`)**로만 제공합니다. Cloud Run 상태 확인용 `/api/health`, `/api/version` 외에는 REST API, OpenAPI 스키마, 웹 브리지 또는 소개 페이지를 제공하지 않습니다.
  - Cloud Run 서버리스 스케일링 환경을 위해 `stateless_http=True` 및 `combine_lifespans`를 적용하고, 리버스 프록시 뒤에서 `/mcp` 307 리다이렉트 시 발생하는 HTTPS→HTTP 다운그레이드를 ASGI 미들웨어 경로 정규화로 해결했습니다.

## 이용 가이드

최종 사용자(보험 가입자)와 설정자·운영자를 위한 종합 사용법은 [이용 가이드](docs/user-guide.md)를 참조하세요.

## V2 설계 — 설계사·대리점용 MCP

설계사·대리점이 자신이 사용하는 AI에서 여러 고객의 보험 정보를 관리하고 예상 보험금을 산출하는 MCP 전용 확장을 준비합니다. 상담·문서 판독·고객 전달은 외부 AI가 담당하며, 자체 UI·CRM·업무 REST API는 만들지 않습니다.

- [V2 요구사항](docs/v2-requirements.md): 서비스 경계, 고객별 권한, MCP 계약, 검증·개인정보 및 출시 조건
- [V2 전환 설계 및 구현 계획](docs/v2-implementation-plan.md): 데이터·인증 분리, 단계별 구현·시험, 기존 이용자 보호

V2는 **별도 서버·Neon 별도 프로젝트·배포 파이프라인**으로 분리했습니다. 독립 인프라의 실제 배포·DB migration·인증 MCP 검증을 완료했으며, 현재는 `get_workspace_context`만 제공합니다. 고객·보험·평가 업무 도구는 후속 구현 대상입니다. V1 실행 코드·DB·배포 워크플로는 변경하지 않았습니다.

- [V2 로컬 실행](v2/README.md) · [V2 클라우드 구축·배포](docs/v2-deployment.md)
- V2 MCP: `https://insurance-claim-mcp-v2-sg2qj3p5rq-du.a.run.app/mcp` (V2 전용 키 필요)

## 로컬 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m uvicorn claim_service.main:app --app-dir src --port 8080
```
- 상태 확인: `GET /api/health`, `GET /api/version` (인증 불필요)
- 설치가 실패하거나 `pip`이 없는 경우(`No module named pip`, `pip._vendor` 누락): [로컬 개발 환경 설치](docs/setup.md)
- MCP 엔드포인트 (Streamable HTTP): `POST /mcp` (또는 `/mcp/`)
- MCP 로컬 실행 (stdio): `.\.venv\Scripts\python.exe -m claim_service.mcp.server`

## 데이터베이스 및 보안

- 기본: 로컬 SQLite (`claim_service.db`, 프로젝트 루트에 생성되며 `.gitignore`로 커밋 제외)
- 클라우드: 환경변수 `DATABASE_URL`을 PostgreSQL URL로 지정 (예: `postgresql+psycopg://...`)
- 평가 요청(질병코드, 진료비)은 저장하지 않고 계산 결과만 반환합니다.
- MCP HTTP 접근은 사용자별 API 키(`X-User-Key` 헤더 또는 `Bearer`)로 인증합니다. 키 원문은 발급 시 한 번만 표시되고 서버에는 SHA-256 해시만 저장됩니다. 키 인증은 요청을 소유 사용자에 귀속시킵니다(PIN 입력 대체). PIN 보호 계정은 `PBKDF2-HMAC-SHA256`(120,000회 반복) 해시로 검증을 유지합니다. 키 발급·폐기는 [사용자별 API/MCP 키 가이드](docs/user-api-keys.md), 연결 설정은 [클라이언트 연결 가이드](docs/mcp-client-setup.md), 종합 사용법은 [이용 가이드](docs/user-guide.md)를 참조하세요.

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
