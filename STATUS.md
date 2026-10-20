# 진행 현황

최종 갱신: 2026-10-20

## 최신 진행 상황 (2026-10-20)

- 스마트폰 무료 AI 앱 개인화 웹 브릿지(`/ai/*`) 추가: MCP나 Custom GPT 설정이 없는 스마트폰 기본 AI 앱(무료 ChatGPT 앱, Gemini 앱, Claude 모바일 앱 등)에서도 내장 웹 읽기(GET) 기능만으로 공통 DB(`user_id` + `pin`)에 접근해 개인화 온보딩(`/ai/onboard`), 보험증권 사진 판독 후 등록/갱신(`/ai/register-policy`), 미매핑 특약 확정(`/ai/resolve-rider`), 등록 보험 조회/삭제(`/ai/policies`, `/ai/delete-policy`), 병원 영수증 기반 예상 보험금 계산(`/ai/evaluate`)을 수행할 수 있도록 `src/claim_service/api/ai_bridge.py` 및 `/start`(`src/claim_service/start_guide.py`)를 구현함.
- 모바일 ChatGPT 웹 리더(`ChatGPT-User`, `OAI-SearchBot`) 호환성 및 단일 조회(`/u/{user_id}/{pin}`) 보완: `/robots.txt` 및 `/favicon.ico`를 공개 경로로 열어 크롤러 401 차단을 해제하고, AI 웹 리더가 `/start.md` 또는 `/ai/*`를 열 때 `text/markdown`·`application/json` 대신 `text/html` 페이지로 응답하도록 보완함. 또한 모바일 ChatGPT의 URL 샌드박스(AI가 임의 조합한 URL 호출 차단)에서도 한 번의 접속만으로 사용자 프로필·등록 보험 전체 목록·표준 규칙을 즉시 읽을 수 있도록 `/u/{user_id}/{pin}`(및 `/start?user_id=...&pin=...`) 단일 조회 경로를 추가함.
- 보안 및 도배(Spam) 방어 강화: `/ai/*` 및 `/u/*` 경로는 4~32자 PIN 입력을 강제하며, PIN이 설정되지 않은 기존 계정(예: `user_123`)의 접근을 차단(HTTP 403)하고, 계정별 연속 5회 PIN 오입력 시 5분간 요청을 차단(HTTP 429)함. 또한 공개 커뮤니티 유입 시 악성 스크립트 도배를 막기 위해 IP당 5분 내 쓰기 요청 제한(20회), 전역 신규 계정 생성 제한(5분당 60개), 계정당 최대 보험 등록 건수 제한(20건)을 적용함.
- 검증: 전체 `pytest -q` 79 passed, `ruff check src tests scripts` 통과, `mypy src` 30개 파일 통과.

## 이전 진행 상황 (2026-10-19)

- MCP 3대 구성요소 완성(`feat/mcp-resources`): 기존 Tools(11개) 및 Prompts(1개)에 더해 읽기 전용 MCP Resources 3종(`insurance://guide/onboarding`, `insurance://rules/standard`, 동적 템플릿 `insurance://guide/document-request/{policy_type}/{product_name}`)을 `src/claim_service/mcp/server.py` 및 공개 소개(`src/claim_service/intro.py`)에 추가함.
- 포트폴리오 문서 정비: `README.md`에 아키텍처 및 MCP 3요소 설계 의도를 보강하고, `docs/mcp-client-setup.md` 내 로컬 PC 파일 경로 메모를 제거함.
- 검증: 전체 `pytest -q` 74 passed, `ruff check src tests scripts` 통과, `mypy src` 29개 파일 통과.

## 이전 진행 상황 (2026-10-17)

- 유지보수 개선(2026-10-17): 사용 이력이 확인된 Neon 스킬 파일은 유지. PoC `legacy/` 5개 파일 삭제. Cloud/Neon 운영 데이터는 변경하지 않음.
- GCP Secret Manager 조회/DB URL 정규화를 `scripts/gcp_secrets.py`로 공통화하고 CI Ruff 검사에 `scripts/`를 포함. GitHub Actions `main` CI 성공 후 Cloud Run 자동 배포, main 수동 실행 및 `/api/health`, `/api/version`, `/llms.txt` 스모크 확인을 구성. `PUBLIC_BASE_URL` 누락도 배포 환경에서 보완함.
- 배포 최초 설정 안내는 `docs/deployment.md`에 기록. GitHub Actions 변수/시크릿과 Workload Identity Federation은 이 로컬 환경에서 조회 권한을 확인하지 못했으며 설정 완료 여부는 미확인. 실제 운영 배포는 실행하지 않음.
- 검증: 전체 `pytest -q` 72 passed, `ruff check src tests scripts` 통과, `mypy src` 29개 파일 통과, GitHub Actions YAML 파싱 및 `git diff --check` 통과. Docker/Cloud 배포는 실행하지 않음.

- 사용자 결정(2026-10-17): 공용 `API_KEY` 인증을 유지하고 사용자 구분은 `X-User-Id`로 한다. 사용자별 API 키 기능은 다음 배포 후보 코드에서 제거하며, 현재 Cloud Run 배포는 변경하지 않는다. `X-User-Id`는 인증 수단이 아니므로 공용 키를 대체하지 않으며, 기존 PIN 보호도 유지한다.
- 코드 변경: 사용자별 키 인증/DB 테이블/운영 CLI/운영 가이드를 제거하고 MCP 클라이언트 문서를 공용 `X-API-Key` + 사용자별 `X-User-Id` 설정으로 수정함. 기존 DB 테이블 및 키 데이터는 배포 때 자동 삭제하지 않음.

- 사용자별 무만료 API/MCP 키 구현: 무작위 키 원문은 발급 시 한 번만 보여주고 DB에는 SHA-256 해시만 저장. `X-User-Key` 인증 시 서버가 사용자 ID를 바인딩하며 해당 계정 PIN 입력을 대체하고, 잘못된 사용자 키만으로는 공용 키가 설정된 서비스에 접근할 수 없음. 관리자 CLI 발급·목록·폐기와 사용자 키 운영/클라이언트 설정 문서를 추가함.
- 검증: 전체 `pytest -q` 64 passed, 인증 통합 테스트 11 passed, Ruff 통과, mypy 29개 소스 파일 통과, `git diff --check` 통과. 운영 키 CLI의 임시 SQLite 확인에서 발급/목록/폐기는 성공했으며 첫 확인의 한국어 성공문구 비교는 PowerShell 출력 인코딩 차이로 실패했으나 키 ID가 폐기 후 목록에서 제거됨을 확인함.
- 배포 전에는 운영 DB를 직접 조회·변경하지 않음. 브랜치 `feat/per-user-api-keys`; 기존 사용자 변경 파일은 그대로 보존.
- 사용자별 무만료 키 기능을 Cloud Build `39e9c5f9-2636-445b-85bd-de48ce66408a`로 빌드하고, 이미지 `claim-service:user-api-keys-20261016`를 Cloud Run에 배포함. 리비전 `insurance-claim-mcp-00008-dlx` Ready 및 트래픽 100% 확인. `APP_VERSION`만 갱신하고 기존 `PUBLIC_BASE_URL`, `DATABASE_URL`/`API_KEY` Secret 참조, `SEED_SAMPLE_DATA=false`를 보존함.
- 배포 후 앱 시작 시 `init_schema()`가 실행되어 누락된 테이블(사용자 API 키 테이블 포함)이 있으면 생성될 수 있음. 별도 운영 DB 쿼리나 사용자 데이터 변경은 하지 않음. 공개 URL에서 `/api/health`, `/api/version`, `/llms.txt` HTTP 200 및 버전 `user-api-keys-20261016` 확인. 인증이 필요한 `/api/catalog/rules`는 키 없이 HTTP 401을 반환함.
- fail-closed 평가 변경과 합성 샘플 사용자 시드 기본 비활성화 변경을 각각 `fb16046`, `e11fecc`로 커밋. 시드 관련 배포/Compose/테스트 설정은 두 번째 커밋에 포함했고, 나머지 로컬 변경은 커밋에서 제외.
- 검증: 사용자가 확인한 전체 테스트 62 passed (2.05s), Ruff 통과, mypy 28개 소스 파일 통과.
- Cloud Build `459f0596-a3b6-42c4-9315-23e93fecece9` 성공. 이미지 `claim-service:e11fecc`를 Cloud Run `insurance-claim-mcp-00007-jpm`에 배포, Ready 상태 및 트래픽 100%를 확인. `APP_VERSION=e11fecc`, `SEED_SAMPLE_DATA=false`; 기존 `DATABASE_URL`, `API_KEY` Secret Manager 참조와 `PUBLIC_BASE_URL`은 보존.
- 배포 후 `/api/health`, `/api/version`, `/llms.txt`는 HTTP 200, 버전은 `e11fecc`. MCP `list_standard_rules` 읽기 전용 호출은 클라이언트 상호운용 결과 미확인 상태이므로 Aside 측 스모크 테스트 필요.
- Docker 데몬이 실행되지 않아 로컬 Docker 테스트는 하지 않았으며 Cloud Build에서 이미지 빌드 성공.
- Aside 팀 전달: fail-closed 배포와 시드 비활성화 완료, 사용자/보험 데이터 변경 없음. Aside 운영자가 보호된 `X-API-Key` 설정을 통해 `list_standard_rules` 읽기 전용 테스트 후 규칙 개수 및 `verified` 상태 요약 회신 요청. 키/PIN/개인정보를 대화에 포함하지 말 것.

- fail-closed 평가 보강: `ClaimInput`에서 입원/통원, 상해 여부, 응급 여부, 입원 일수, 통원 의료기관 유형의 미제공을 `None`으로 표현. 필수 진료 사실이 확인되지 않으면 결과를 `NOT_EVALUATED`로 반환하며 예상 지급액은 0원.
- `verified: false`인 표준 특약 규칙과 약관 원문 검증이 없는 CUSTOM 특약은 더 이상 계산하지 않음. 실손도 규칙 미검증 또는 필수 진료 유형/기관 정보 부재 시 계산 보류. 지급 확정 표현 없이 검증 제한을 결과 disclaimer에 명시.
- 약관 PDF/원문은 이번 작업에서 대조하지 않았고 어떤 규칙도 검증 처리하지 않음. 따라서 현재 비어 있는 약관 조건은 추정해 채우지 않음. API 입력 스키마에서 누락 사실을 허용하므로 클라이언트가 `NOT_EVALUATED` 응답을 처리하는지 별도 확인 필요.
- 검증 결과: evaluator 단위 테스트 21 passed, API extra 통합 테스트 15 passed, Ruff 통과, mypy 28개 소스 파일 통과. 전체 `pytest -q` 실행 결과는 셸 출력에서 완료를 확인하지 못해 전체 스위트 통과로 기록하지 않음.
- 개인 계정 ADC 방식 선택. Windows에서 gcloud CLI를 PATH에서 찾았으며, `CurrentUser` 실행 정책은 `Undefined`라 실행 정책 변경은 하지 않음. 후속 확인에서 ADC 파일 및 액세스 토큰 발급은 성공했으나 `gcloud auth list` 활성 계정 표시는 확인되지 않음.
- 인증 점검 도구 `scripts/check_gcloud_auth.py`, ADC 토큰 자동 갱신 도우미 `scripts/gcloud_auth.py`, 제한된 읽기 전용 샘플 검토 도구 `scripts/review_sample_data.py`, 모니터 개선 및 `docs/gcloud-auth.md`를 추가함. 인증 정보·토큰·Secret 값은 출력하지 않도록 설계함.
- 후속 확인에서 일반 gcloud CLI 활성 계정은 감지되지 않았지만 ADC 파일과 액세스 토큰 발급은 확인됨. 제한된 읽기 전용 검토 결과: coverage_rules 13, users 2, user_policies 5, user_policy_riders 16. `user_123` 존재 및 샘플 별칭 표식 일치, 보험 2건·특약 5건 연결. 단, 연결된 보험/특약 모두 `SYNTHETIC_SAMPLE` 출처 검증에 실패함. 이전 마이그레이션 또는 이후 수정 데이터일 가능성을 배제할 수 없어 삭제 금지 상태로 두며 어떤 운영 레코드도 변경하지 않음.
- 로컬 작업 브랜치 `feat/disable-synthetic-seed`에서 합성 사용자 `user_123` 자동 시드를 기본 비활성화함. 표준 담보 규칙 시드는 계속 유지하고, Docker Compose 및 Cloud Run 배포 워크플로도 사용자 샘플 시드를 끄도록 변경함.
- 검증: `pytest -q` 58 passed, `ruff check src tests scripts` 통과, `mypy src` 28개 파일 통과. 새 설정에서 샘플 사용자는 생성되지 않고 표준 규칙은 유지되는 테스트 포함.
- ADC를 사용한 운영 DB 읽기 전용 검토를 완료함. `user_123`는 존재하고 별칭은 샘플 표식과 일치하나, 연결된 보험 2건과 특약 5건의 `source_type`은 `SYNTHETIC_SAMPLE`이 아님. 삭제 대상 여부를 확정할 수 없어 레코드를 보존함.
- 다음 단계: 보험/특약 2건과 특약 5건의 출처를 증권 또는 감사 가능한 기록과 대조해 사용자가 삭제 대상을 확정. 그전까지 운영 데이터는 변경하지 않음. 샘플 시드 비활성화 브랜치는 별도 검토·병합·배포 전 상태.
- `main` 커밋 `5d4b848`(보험증권 출처 근거 없이는 예상 보험금을 계산하지 않음)이 Cloud Run에 배포됨.
- Cloud Run 리비전 `insurance-claim-mcp-00006-8vk`가 준비 상태이며 트래픽 100%를 받고, `/api/health`는 HTTP 200을 반환함.
- 배포 시 앱 시작으로 `init_runtime()`과 스키마 초기화가 실행됨. migration 함수 호출은 확인했으나, DB에 추가된 컬럼 및 저장 데이터는 직접 조회하지 못했으므로 세부 DB 상태는 미확인.
- 운영 DB에서 표 전체 건수와 `user_123` 관련 건수·출처 표식만 확인함. 사용자별 별칭·보험 상세는 진행 보고에 포함하지 않음. 조회는 읽기 전용이었으며 어떤 운영 레코드도 삭제·수정하지 않음.
- `user_123`의 계정 별칭은 샘플 표식과 일치하지만 보험·특약 출처가 합성 샘플로 확인되지 않았으므로 사용자 데이터가 섞였을 가능성을 배제할 수 없음. 별도 근거와 명시적 대상 확정 전 삭제 금지.
- v1.0 전 약관·표준 수치의 근거, 미검증 한계 고지, 운영 개인정보 안내를 점검. AI 연결은 변경 방침이 정해진 뒤 별도 반영.
- 현재까지 v1.0 릴리스 태그는 생성하지 않음.

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

## Phase 1-H. 보험증권 출처 검증 — 로컬 완료 (브랜치 `feat/source-verified-policies`)

### 확인된 사실 (실제 실행 결과)
- `pytest -q`: 57 passed.
- `ruff check src tests scripts`: 통과.
- `mypy src`: 28개 소스 파일 통과.
- 기존 SQLite 스키마에서 보험·특약 출처 컬럼을 추가하고 기존 레코드를 `USER_STATED`로 취급하는 migration 테스트를 추가함.
- MCP 문서 요청 안내 도구가 공식 보험사 발급 경로만 반환하는지와 제3자 앱·캡처·스크래핑 안내 문구가 없는지 테스트함.
- 이 항목 작성 당시에는 운영 데이터베이스 migration을 실행하지 않았음. 2026-10-16 배포에서 앱 시작 시 스키마 초기화가 실행됐으며, 실제 컬럼 및 사용자 데이터는 아직 직접 검증하지 않음.

### 구현 내용
- 정책·특약 출처 메타데이터를 저장하고 보험증권(`POLICY_CERTIFICATE`) 근거가 있는 담보만 예상 보험금 계산에 포함함.
- 증권이 없을 때 보험사 공식 경로로 서류를 요청할 수 있도록 문서 안내 도구와 합성 샘플 데이터를 추가함.
- `register_policy`에서 정책의 출처 메타데이터가 저장용 객체까지 전달되도록 수정함.

## 사용자 확보 대기 항목
- 4세대 실손 표준약관 또는 가입 상품 약관 (약관 수치 `verified` 확정용).
- GCP 프로젝트 결정 (Phase 6 전).
