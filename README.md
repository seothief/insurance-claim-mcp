# insurance-claim-mcp

약봉투·진료비 영수증의 정보(KCD 질병코드, 처치, 진료비)를 가입 보험 약관과 대조해 **청구 가능성과 예상 보험금**을 안내하는 FastAPI + MCP 서비스입니다.

> 정보 제공용 예상치입니다. 실제 지급 여부와 금액은 보험사 심사에 따라 달라집니다.

## 구성
- FastAPI REST API (`/api/*`)
- FastMCP 원격 MCP 서버 (`/mcp`), 같은 프로세스에서 함께 제공
- 무상태 설계: 평가 요청과 결과를 저장하지 않으며 합성 증권 데이터만 사용

## 로컬 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m uvicorn claim_service.main:app --app-dir src --port 8080
```

- 상태 확인: `GET /api/health`
- MCP 엔드포인트: `POST /mcp/`

## 데이터베이스

- 기본: 로컬 SQLite (`claim_service.db`, 저장소 밖이 아닌 프로젝트 루트에 생성되며 `.gitignore`로 커밋 제외)
- 클라우드: 환경변수 `DATABASE_URL`을 PostgreSQL URL로 지정 (예: `postgresql+psycopg://...`, 드라이버 설치 필요)
- 평가 요청(질병코드, 진료비)은 저장하지 않고 계산 결과만 반환합니다.
- REST/MCP 접근은 서버 공용 `X-API-Key`로 인증합니다. `X-User-Id`는 요청을 특정 사용자 별명에 귀속시키며 인증을 대체하지 않습니다. PIN 보호 계정은 PIN 확인을 유지합니다. [클라이언트 연결 가이드](docs/mcp-client-setup.md)를 참조하세요.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m mypy src
```

## 배포

`main`에 CI를 통과한 변경을 병합하면 GitHub Actions가 Cloud Run에 자동 배포하고
`/api/health`, `/api/version`, `/llms.txt`를 확인합니다. 수동 배포는 GitHub의
**Actions → Deploy to Cloud Run → Run workflow** 한 번으로 실행할 수 있습니다.
최초 설정에 필요한 GitHub 변수, Workload Identity Federation 및 권한은
[배포 설정 안내](docs/deployment.md)를 참조하세요. 운영 배포는 이 로컬 작업에서 실행하지 않습니다.

## 진행 현황
[STATUS.md](STATUS.md)
