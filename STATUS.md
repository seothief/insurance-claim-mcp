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

### 남은 항목
- GitHub 저장소 생성과 push (`gh` CLI 미설치, 인증 방식 확정 필요).
- Phase 1 이후: 도메인 코어, REST, 보안, MCP 도구, CI, 배포.

## 사용자 확보 대기 항목
- 4세대 실손 표준약관 또는 가입 상품 약관 (약관 수치 `verified` 확정용).
- GCP 프로젝트 결정 (Phase 6 전).
