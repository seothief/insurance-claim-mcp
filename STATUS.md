# 진행 현황

최종 갱신: 2026-10-15 (Phase 0)

## Phase 0. 기반 — 로컬 완료

### 확인된 사실 (실제 실행 결과)
- Python 3.12.6, git 2.45.1, Node 20.18.0 확인.
- 가상환경 `.venv`에 의존성 설치. 버전: fastapi 0.143.1, fastmcp 4.1.0, pydantic 2.14.1, pydantic-settings 2.16.0, uvicorn 0.54.0, pytest 9.1.1, ruff 0.17.0, mypy 2.4.0, httpx 0.28.1.
- fastmcp 4.1.0에 `FastMCP.http_app`과 `fastmcp.utilities.lifespan.combine_lifespans`가 존재함을 확인.
- `pytest` 3개 통과 (`/api/health`, `/api/version`, MCP `service_status` 도구 목록).
- `ruff check src tests` 통과.
- `uvicorn claim_service.main:app --app-dir src`로 실행 후 `/api/health` 200, `/mcp/` initialize HTTP 200 확인.

### 설계 제안 (미검증)
- FastAPI 앱이 MCP 서브앱을 `/mcp`에 마운트하고, lifespan을 `combine_lifespans`로 결합한다.
- 무상태 MVP, DB 없음, 합성 seed만 사용.

### 정리한 항목
- `generate_pptx.py` 삭제 (발표자료용, 사용자 승인).
- PoC 파일 5개를 `legacy/`로 이동.

### GitHub 연동 및 다른 PC 재현 (확인 완료)
- 원격 저장소 `https://github.com/seothief/insurance-claim-mcp` (private)에 `main` push 완료. 원격 HEAD `202dffb`.
- 커밋 작성자: `seothief83 <seothief83@gmail.com>`.
- 다른 PC 재현: 원격을 새 폴더에 `git clone` → `python -m venv .venv` → `pip install -r requirements.lock.txt` → `pytest -q` 3 passed → `ruff check src tests` 통과.
- 교훈: 긴 설치 명령은 셸 출력이 끊기므로, 출력을 파일로 남기고 완료 여부를 확인해야 한다.

### 남은 항목
- Phase 1 이후: 도메인 코어, REST, 보안, MCP 도구, CI, 배포.

## Phase 1. 보험정보 관리 DB — 로컬 완료 (브랜치 `feat/policy-management-db`)

### 확인된 사실 (실제 실행 결과)
- SQLAlchemy 2.1.4 도입 (`pyproject.toml`, `requirements.lock.txt`).
- `pytest -q`: 19 passed (평가 엔진 단위 테스트 + DB/REST/MCP 통합 테스트).
- `ruff check src tests`: 통과.
- `mypy` (strict, `src`): 통과.

### 구현 내용
- DB: 로컬 SQLite 기본(`sqlite:///claim_service.db`), `DATABASE_URL`로 PostgreSQL 전환 가능.
- 테이블: `coverage_rules`, `users`, `user_policies`, `user_policy_riders`.
- 표준 담보 규칙 6종 시드 (`verified: false`, 출처 미확보 명시).
- 특약명 키워드 자동 매핑 (골절진단/깁스/독감/질병수술/상해수술).
- 청구 평가 엔진은 DB를 읽지 않는 순수 함수이며, 청구 요청 데이터는 저장하지 않음.
- REST: `/api/catalog/rules`, `/api/users/{user_id}/policies` (GET/POST/DELETE), `/api/users/{user_id}/riders/{rider_id}` (PATCH), `/api/users/{user_id}/evaluate` (POST).
- MCP 도구: `list_standard_rules`, `list_user_policies`, `register_user_policy`, `delete_user_policy`, `update_user_rider`, `evaluate_claim`.
- 샘플 사용자 `user_123` (합성 데이터, PII 없음) 최초 실행 시 시드.

### 설계 제안 (미검증)
- 증권 PDF/캡처의 AI 추출 후 MCP 도구로 등록하는 흐름 (추출 자체는 클라이언트 LLM 담당).
- 실손 공제 수치는 `verified: false` 상태이므로 약관 원문 대조 전까지 예상치로만 제공.

### 남은 항목
- 약관 원문 대조 후 `verified` 전환, 사용자 인증(`user_id` 발급 방식), 증권 PDF 추출 가이드 문서화.

## Phase 1-B. 가입 절차 · 등록 갱신 · AI 재질의 — 로컬 완료 (브랜치 `feat/policy-management-db`)

### 확인된 사실 (실제 실행 결과)
- `pytest -q`: 34 passed (평가 엔진 단위 테스트, REST/MCP 통합 테스트).
- `ruff check src tests`: All checks passed.
- `mypy src` (strict): Success, no issues found in 24 source files.
- MCP end-to-end 확인: 가입 → 보험 등록 → 미매핑 특약 재질의 → 특약 확정 → READY → 청구 평가.

### 구현 내용
- 가입 절차: `users`에 `display_alias`, `birth_year` 추가. 상태 `CREATED` → `NEEDS_CLARIFICATION` → `READY`.
  REST `POST /api/users`, `GET /api/users/{user_id}`, MCP `register_user`, `get_user_profile`.
- 등록 갱신(Upsert): `(user_id, company, product_name)` 기준. 같은 보험은 `UPDATED`로 갱신하며 중복 생성하지 않음.
  확정된 특약 매핑(`MAPPED`/`CUSTOM`/`IGNORED`)은 재등록 시 보존, 가입금액만 갱신.
- AI 재질의: 자동 매칭 실패 특약은 `NEEDS_CLARIFICATION`으로 반환하고 `ai_follow_up_prompt`와 후보 규칙을 함께 제공.
  `resolve_user_rider`(REST `POST .../riders/{rider_id}/resolve`)로 `MAPPED`/`CUSTOM`/`IGNORED` 확정.
- 실손 세대: 세대 미지정 시 가입연도로 추정. 2009·2017·2021년(세대 전환 해)은 추정하지 않고 확인 요청.
  연도도 없으면 "가입연도가 모두 없어 계산하지 않았습니다" 안내.
- 담보 규칙 추가 (모두 `verified: false`): 실손 1·2·3세대 템플릿, 화상진단(T20~T32), 창상봉합술, 입원일당, 응급실내원비.
  실손 1~3세대는 약관 수치가 없어 계산하지 않음(NOT_EVALUATED).
- 평가: `NEEDS_CLARIFICATION` 특약은 지급 계산에서 제외하고 `pending_riders`로 표시. `CUSTOM` 특약은 확정 조건으로 계산하되 "검증되지 않음"을 명시.
- 온보딩 가이드: `get_onboarding_guide` (REST `GET /api/onboarding/guide`).

### 설계 제안 (미검증)
- 공공 기준 데이터(KCD/EDI/협회 공시) 수집기는 아직 구현하지 않음. 검토 결과 스크래핑 대상은 공개 기준 데이터만 권장.
- 사용자 인증은 없음. `user_id`를 그대로 신뢰하므로 다중 사용자 서비스 전에 인증 방식을 정해야 함.

### 남은 항목
- 공공 기준 데이터 수집 모듈(KCD/EDI/협회 공시) 구현 및 `coverage_rules` 보강.
- 약관 원문 대조 후 `verified` 전환.
- 사용자 인증 설계.

## Phase 1-C. PostgreSQL · Docker · CI/CD 구성 — 코드 작성 완료, 실행 검증 일부 대기

### 확인된 사실 (실제 실행 결과)
- 로컬 `pytest -q`: 38 passed (SQLite), `ruff check src tests` 통과, `mypy src` 통과 (25개 파일).
- `psycopg[binary]==3.2.9` 설치 및 `requirements.lock.txt` 반영 확인 (`pip install --dry-run` 모두 satisfied).
- 브랜치 `feat/policy-management-db`를 원격에 푸시함 (커밋 `02a801c`).
- 이 PC에 Docker Desktop 설치됨 (CLI 29.8.2, Compose v5.6.0). 그러나 WSL2가 없어 엔진이 시작되지 않음 (`Docker Desktop is unable to start`).
  관리자 권한이 필요한 `wsl --install`은 실행되지 않았음 (UAC 미승인 추정). 이 PC에서의 컨테이너 실행은 아직 검증하지 못함.

### 구현 내용
- `create_db_engine`: `postgres://`, `postgresql://` URL을 `postgresql+psycopg://`로 정규화, PostgreSQL에 `pool_pre_ping` 적용.
- 선택적 API Key 보호: `API_KEY` 설정 시 `/api/health`, `/api/version` 외 모든 요청에 `X-API-Key` 또는 `Authorization: Bearer` 필요.
- `Dockerfile`, `.dockerignore`, `docker-compose.yml` (postgres:16-alpine + 앱, 헬스체크 연동).
- `.github/workflows/ci.yml`: lint(ruff, mypy), SQLite 테스트, PostgreSQL 16 서비스 컨테이너 테스트, docker compose 스모크 테스트.
- `.github/workflows/deploy-cloudrun.yml`: Cloud Run 배포 (저장소 변수/시크릿 설정 필요).
- 테스트는 `TEST_DATABASE_URL`이 있으면 해당 DB(PostgreSQL)에서 실행됨. CI의 PostgreSQL 잡에 이 변수를 연결함.

### 설계 제안 (미검증)
- GitHub Actions 결과(특히 PostgreSQL 잡, docker-smoke 잡)는 아직 확인하지 못함. 비공개 저장소라 이 PC에서 API로 조회할 수 없음.
- Cloud Run 배포는 GCP 프로젝트, Workload Identity, DB URL, `API_KEY` 시크릿 준비 후에만 동작함.
- `--allow-unauthenticated`로 배포하므로 `API_KEY`가 유일한 보호 수단임.

### CI 결과 (사용자가 GitHub Actions 화면으로 확인)
- CI #1 (`02a801c`), CI #2 (`1137e7c`) 모두 성공 (각 약 2분 21초, 2분 35초).
- CI #2부터 `test-postgres` 잡이 `TEST_DATABASE_URL`로 PostgreSQL 16을 실제로 사용함.
- 잡별 세부 결과는 화면 요약만 확인했고 개별 로그는 보지 못함.

### 남은 항목
- 이 PC에서 WSL2 설치(관리자 권한, 재부팅 가능) 후 `docker compose up`으로 로컬 PostgreSQL 검증.
- GCP 프로젝트 결정 후 Cloud Run 배포 설정.
- 사용자 보험 프로필 내보내기/가져오기, 약관 원문 대조.

## Phase 1-D. ChatGPT 모바일 사용자 대응 — 코드와 문서 작성 완료, 실제 GPT 연결은 미검증

### 전제 조건 (사용자 지정)
- 사용자는 스마트폰에 ChatGPT 앱만 설치한 일반인이다. MCP 설정, user_id, 질병코드 같은 용어를 모른다.
- 사용자가 할 수 있는 일은 앱 화면 캡처, 영수증과 약봉투 사진 촬영, 채팅이다.

### 확인된 사실 (실제 실행 결과)
- `pytest -q` 38 passed, `ruff check src tests` 통과, `mypy src` 통과 (25개 파일).
- OpenAPI 3.1.0 스키마에 경로 9개, 작업 10개가 있다 (health, version 제외). 확인한 뒤 모든 작업에
  영어 camelCase `operationId`와 한글 요약·설명을 붙였다: `registerUser`, `getUserProfile`, `registerPolicy`,
  `listPolicies`, `deletePolicy`, `updateRiderAmount`, `resolveRider`, `evaluateClaim`, `getOnboardingGuide`,
  `listStandardRules`. (처음 확인 시 `/api/catalog/rules`만 자동 생성 이름이어서 추가로 고침)
- `/api/health`, `/api/version`은 스키마에서 제외함 (GPT 도구로 노출할 필요가 없음).
- 온보딩 가이드에 일반인용 화면 캡처 안내(`capture_guide_for_users`)를 추가함.

### 구현 내용
- `docs/chatgpt-custom-gpt-guide.md`: Custom GPT 만드는 순서, 붙여넣기용 지침, API 키 인증 설정, 알려진 한계.

### 설계 제안 (미검증)
- ChatGPT의 GPT Actions가 이 스키마를 문제없이 읽고 호출하는지는 직접 해 보지 못했다.
- 사용자별 인증이 없다. GPT가 공유하는 `API_KEY` 하나로는 사용자를 구분하지 못하고, 별명(`user_id`)을 아는 사람은
  그 사용자의 보험 정보를 조회할 수 있다. 일반 공개 전에 사용자별 인증이 필요하다.
- 개인 보험 정보를 서버 DB에 저장하므로 개인정보 처리방침과 보관 기간 정책이 필요하다.
- ChatGPT 이미지 판독 오류 가능성 때문에 등록 전에 사용자 확인 단계를 지침에 넣었다.

### 남은 항목
- 서버를 https 주소로 배포한 뒤 Custom GPT를 만들어 실제로 등록과 계산이 되는지 시험.
- 사용자별 인증 설계, 개인정보 처리방침.

## Phase 1-E. Cloud Run 배포 — 배포 완료, 외부 연결 시험 대기

### 확인된 사실 (실제 실행 결과)
- 서비스 URL: `https://insurance-claim-mcp-878600435547.asia-northeast3.run.app` (리전 `asia-northeast3`, 리비전 `insurance-claim-mcp-00001-p6k`).
- 설정: 최소 인스턴스 0, 최대 2, 메모리 512Mi, 공개 접근 허용 + API 키 보호.
- GCP 프로젝트 `project-93d02748-0cbc-4596-902`. Artifact Registry 저장소 `insurance-claim` 생성, 이미지 `app:v1` 빌드 성공(Cloud Build 1분 18초).
- 운영 DB: Neon PostgreSQL 18.6 (Singapore, `neondb`), 연결 확인 시 public 테이블 0개였음.
- 공개 주소 시험 결과(v1): `/api/health` 200, 키 없이 `/api/catalog/rules` 401, 틀린 키 401, 올바른 키 200(5459 bytes),
  키 없이 `/openapi.json` 401.
- 로컬 `pytest -q` 40 passed, `ruff` 통과, `mypy src` 통과 (25개 파일).

### 발견한 문제와 조치
- `/openapi.json`이 키 없이는 401이라 ChatGPT가 스키마를 가져오지 못한다. 스키마에는 사용자 데이터가 없으므로 공개 경로로 바꿨다.
- ChatGPT Actions는 스키마에 `servers`가 필요하다. 환경변수 `PUBLIC_BASE_URL`을 넣으면 `servers`에 표시되도록 했다.
- 위 두 가지를 반영한 이미지 `app:v2` 배포 후, 원격 `/mcp`(끝에 슬래시 없음) 접속 시 Cloud Run 프록시 뒤에서
  `http://.../mcp/`로 307 리다이렉트가 발생해 MCP 클라이언트가 HTTPS→HTTP 다운그레이드로 차단하는 문제를 발견함.
- 미들웨어에서 `/mcp`를 내부적으로 `/mcp/`로 정규화하고, `Dockerfile`의 uvicorn에 `--proxy-headers --forwarded-allow-ips=*`를 추가함.
- MCP 서버에 에이전트 행동 지침(`instructions`)과 `@mcp.prompt()`(`insurance_assistant_prompt`)를 내장하고,
  `app:v3` 이미지를 빌드해 Cloud Run 리비전 `insurance-claim-mcp-00003-zbg`로 배포 완료.
- 원격 검증 결과(v3): `https://insurance-claim-mcp-878600435547.asia-northeast3.run.app/mcp`(슬래시 없음) 및 `/mcp/` 모두
  리다이렉트 없이 도구 10개 + 프롬프트 `insurance_assistant_prompt` 조회 및 호출 통과.
- 이 PC의 Cline(`cline_mcp_settings.json`)과 Gemini CLI(`~/.gemini/settings.json`)에 원격 MCP 서버 등록 완료.
- 다중 AI 클라이언트(Gemini, Claude, Cline, ChatGPT) 연결 가이드 `docs/mcp-client-setup.md` 작성.
- 기본 컴퓨트 서비스 계정에 Cloud Build 권한이 없어 첫 빌드가 실패했다. 4개 역할을 부여해 해결했다.

### 설계 제안 (미검증)
- 샘플 사용자 `user_123`이 운영 DB에도 시드된다. 실사용 전에 끄거나 삭제할지 정해야 한다.
- 무료 Neon은 유휴 시 DB가 잠들어 첫 요청이 느릴 수 있다. 측정하지 않았다.
- Cloud Run 최소 인스턴스 0이라 첫 요청에 콜드 스타트가 있다. 측정하지 않았다.
- GitHub Actions의 `deploy-cloudrun.yml`은 Workload Identity 방식이고 아직 설정하지 않았다. 지금은 `gcloud`로 수동 배포했다.

### 남은 항목
- v2 배포, Custom GPT 연결 시험, 사용자별 인증, 개인정보 처리방침.

## Phase 1-F. 무상태 MCP(`stateless_http=True`) 전환 및 하이브리드 사용자 특정(PIN + 헤더 귀속) — 배포 및 원격 MCP 호출 검증 완료

### 확인된 사실 (실제 실행 결과)
- Cloud Run 환경에서 기본 stateful MCP 세션이 컨테이너 재시작/스케일링 시 `Session not found`(-32600) 오류를 내는 문제를 확인하고 `mcp.http_app(path="/", stateless_http=True)`로 전환함.
- 하이브리드 사용자 특정 구현:
  1. `users.pin_hash`(PBKDF2-HMAC-SHA256, 120,000회 반복) 컬럼 추가 및 기존 DB 자동 마이그레이션(`ALTER TABLE users ADD COLUMN pin_hash`).
  2. PIN이 설정된 계정은 올바른 `pin` 파라미터 또는 `X-User-Pin` 헤더가 없으면 `AccessDeniedError`(HTTP 403 / MCP ValueError)로 타인 접근 및 별명 충돌을 차단함.
  3. 전용 AI 클라이언트가 `X-User-Id` 헤더로 귀속된 경우 다른 `user_id` 접근을 차단하고 `get_onboarding_guide`에 `bound_user_id`를 반환함.
- 로컬 검증: `pytest -q` **43 passed**, `ruff check src tests` 통과, `mypy src` 통과 (26개 파일).
- Cloud Run `app:v4` 이미지 빌드 및 리비전 `insurance-claim-mcp-00004-2vr` 배포 완료.
- 실제 Cline MCP 도구 호출(`insurance-claim__get_onboarding_guide`)이 Cloud Run 원격 서버에서 오류 없이 즉시 성공함을 확인함.
- 로컬 Antigravity(`~/.gemini/config/mcp_config.json`) 등 stdio 클라이언트에서 단독 실행할 수 있도록 `claim_service.mcp.server`에 `main()`(`init_runtime()` + `mcp.run()`) 진입점과 `get_service()` 지연 초기화를 추가함 (`pytest` 44 passed).

## Phase 1-G. AI가 읽는 공개 소개 페이지 — `main` 병합 및 Cloud Run 배포 완료

### 확인된 사실 (실제 실행 결과)
- 공개 경로 3개 추가: `/`(HTML), `/about.md`, `/llms.txt`. 한 곳(`src/claim_service/intro.py`)에서 만든
  같은 내용이며, 예시 계산은 실제 평가 엔진을 합성 데이터로 실행한 결과다.
- `api/auth.py`의 `PUBLIC_PATHS`에 세 경로를 추가해 `API_KEY`가 있어도 키 없이 열린다.
- 로컬 검증: `pytest -q` **53 passed**(소개 페이지 테스트 9개 포함), `ruff` 통과, `mypy src` 통과(27개 파일).
- `main`에 fast-forward 병합(`c3516cc`). 병합 전 `main`은 Phase 0 상태(`4deca89`)였다.
- 이미지 `app:v5` 빌드(Cloud Build `SUCCESS`) 후 Cloud Run 리비전 `insurance-claim-mcp-00005-5l7`로 배포,
  트래픽 100%. **롤백 지점은 직전 리비전 `insurance-claim-mcp-00004-2vr`(`app:v4`).**
- 운영 서비스 확인(키 없이 요청): `/`, `/about.md`, `/llms.txt`, `/api/health` 200. `/api/catalog/rules`,
  `/api/users/user_123/policies`, `POST /mcp`는 401.
- `fetch_web_content`로 실제 주소의 `/`를 읽어, 한 줄 요약·계산 예시·한계 6개·설계사 질문 3개가 그대로 읽히는 것을 확인했다.
- 소개 페이지에는 API 키, GCP 프로젝트 ID, 서비스 주소, DB 정보가 없다(테스트로 검증).

### 설계 제안 (미검증)
- 설계사 등 외부인에게 링크 하나(`/`)만 전달하고, 받은 사람이 자신의 AI에게 설명을 요청하는 용도.
- AI가 링크를 열지 못하면 `/about.md`를 복사해 붙여 넣는다.

### 확인하지 못한 것
- 외부 AI(ChatGPT, Gemini 등)가 이 링크를 열 수 있는지, `llms.txt`를 자동으로 읽는지.
- 카카오톡 링크 미리보기 카드가 표시되는지(`og:title`, `og:description`은 넣음).
- `main` 푸시로 GitHub Actions CI가 실행됐는지와 그 결과. `deploy-cloudrun.yml`은 Workload Identity가
  설정되지 않아 동작하지 않는 것으로 알고 있으나 확인하지 않았다.

### 병행 작업
- `feat/contract-list-import` 브랜치(`324e475`): 보험협회 계약 목록 PDF를 로컬에서 읽어 유효·청구 대상 계약만 고르는
  스크립트. 실제 PDF 드라이런에서 19건 중 등록 6건, 제외 13건. `main`에는 아직 병합하지 않았다.
  알려진 문제: 인쇄물이 긴 상품명을 잘라 출력해 상품명이 `…파트너(1`처럼 끊긴다.
- 내보험찾아줌 결과(`생명보험협회.pdf`)와 삼성화재 계약사항 PDF에는 특약별 가입금액이 없다. 특약 정보는
  보험증권이나 설계사의 보장분석 리포트가 필요하다.

## 사용자 확보 대기 항목
- 4세대 실손 표준약관 또는 가입 상품 약관 (약관 수치 `verified` 확정용).
- 특약·가입금액이 담긴 문서(보험증권 또는 보장분석 리포트) 샘플.
- GCP 프로젝트 결정 (Phase 6 전).
