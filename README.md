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

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
```

## 진행 현황
[STATUS.md](STATUS.md)
