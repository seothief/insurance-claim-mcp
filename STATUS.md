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

### 남은 항목
- GitHub Actions 실행 결과 확인 및 실패 시 수정.
- 이 PC에서 WSL2 설치(관리자 권한, 재부팅 가능) 후 `docker compose up`으로 로컬 PostgreSQL 검증.
- GCP 프로젝트 결정 후 Cloud Run 배포 설정.
- 사용자 보험 프로필 내보내기/가져오기, 약관 원문 대조.

## 사용자 확보 대기 항목
- 4세대 실손 표준약관 또는 가입 상품 약관 (약관 수치 `verified` 확정용).
- GCP 프로젝트 결정 (Phase 6 전).
