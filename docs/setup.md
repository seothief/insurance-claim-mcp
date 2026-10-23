# 로컬 개발 환경 설치

이 문서는 이 저장소를 처음 받은 PC에서 테스트·정적 분석까지 실행할 수 있게 만드는 절차입니다.
Windows PowerShell 기준이며, 실제 검증 환경은 Python 3.12.6입니다.

## 요구 사항

- Python **3.12 이상** (`pyproject.toml`의 `requires-python = ">=3.12"`)
- Git
- (선택) Docker Desktop — `docker compose` 스모크 테스트를 돌릴 때만 필요

버전 확인:

```powershell
python --version
```

`python`이 없으면 `py --version`을 시도하고, 이후 명령의 `python`을 `py`로 바꿔 실행합니다.

## 권장 절차 (가상환경 사용)

```powershell
git clone https://github.com/seothief/insurance-claim-mcp.git
cd insurance-claim-mcp

python -m venv .venv
```

**여기서 반드시 pip 존재를 확인합니다.** 이 단계가 이 프로젝트에서 가장 자주 실패하는 지점입니다.

```powershell
.\\.venv\\Scripts\\python.exe -m pip --version
```

정상이면 `pip 26.2 from ...`처럼 버전이 출력됩니다. 그다음 의존성을 설치합니다.

```powershell
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.lock.txt
```

## pip이 없을 때 (`No module named pip`)

venv를 만들었는데 pip이 빠진 경우입니다. 먼저 venv 안에서 ensurepip를 실행합니다.

```powershell
.\\.venv\\Scripts\\python.exe -m ensurepip --upgrade
.\\.venv\\Scripts\\python.exe -m pip --version
```

`Looking in links: ...` / `Installing collected packages: pip`가 보이면 성공입니다.

## pip이 깨졌을 때 (`No module named 'pip._vendor'`)

ensurepip가 불완전하게 설치되어 `pip --version`이 `ModuleNotFoundError: No module named 'pip._vendor'`로
실패하는 경우입니다. 이때는 venv를 지우고 **시스템 pip으로 venv에 pip을 심는 방법**이 가장 확실합니다.

```powershell
Remove-Item -Recurse -Force .venv
python -m venv .venv
$env:PYTHONPATH = ""   # 시스템 site-packages와 섞이지 않게 비웁니다
python -m pip install --python .\\.venv\\Scripts\\python.exe pip
.\\.venv\\Scripts\\python.exe -m pip --version
```

위 방법도 실패하면 **대안: 시스템 파이썬에 직접 설치**로 넘어갑니다.

## 대안: 시스템 파이썬에 직접 설치

가상환경이 계속 깨지는 PC에서 검증을 끝내는 가장 빠른 경로입니다. 프로젝트 전역 패키지에
설치되므로 다른 프로젝트와 격리되지 않는다는 점만 감수하면 됩니다.

```powershell
python -m pip --version
python -m pip install -r requirements.lock.txt
python -c "import fastapi, fastmcp, sqlalchemy, pytest; print('deps OK')"
```

`Defaulting to user installation because normal site-packages is not writeable` 경고는
사용자 디렉터리(`%APPDATA%\\Python\\Python312\\site-packages`)에 설치된다는 뜻이며, 설치 실패가 아닙니다.

## 설치 확인 및 검증

```powershell
# 가상환경을 쓰는 경우 접두어를 붙입니다: .\\.venv\\Scripts\\python.exe
python -m pytest -q
python -m ruff check src tests scripts
python -m mypy src
```

기대 결과 (2026-10-23 기준):

```
pytest: 43 passed
ruff:   All checks passed!
mypy:   Success: no issues found in 26 source files
```

## 로컬 서버 실행

```powershell
# MCP over Streamable HTTP
python -m uvicorn claim_service.main:app --app-dir src --port 8080

# MCP over stdio (데스크톱 AI 클라이언트용)
python -m claim_service.mcp.server
```

- 상태 확인(인증 불필요): `GET /api/health`, `GET /api/version`
- MCP 엔드포인트: `POST /mcp` — `X-User-Key` 헤더가 필요합니다. 키 발급은
  [사용자별 API/MCP 키](user-api-keys.md)를 참조하세요.

## 플랫폼 참고 (Linux / Docker / CI)

`requirements.lock.txt`에는 Windows 전용 패키지(`pywin32`, `pywin32-ctypes`)가 포함되어 있습니다.
Linux 이미지와 CI에서는 아래처럼 제외하고 설치합니다.

```bash
grep -viE '^(pywin32|pywin32-ctypes)' requirements.lock.txt > requirements.linux.txt
pip install -r requirements.linux.txt
```

## 자주 겪는 문제 정리

| 증상 | 원인 | 대처 |
| --- | --- | --- |
| `No module named pip` | venv 생성 시 pip 미포함 | `python -m ensurepip --upgrade` |
| `No module named 'pip._vendor'` | ensurepip 불완전 설치 | venv 삭제 후 재생성, 또는 시스템 pip으로 `--python` 지정 설치 |
| `Defaulting to user installation ...` | 시스템 site-packages 쓰기 불가 | 경고일 뿐이며 정상 동작. 필요하면 `--user` 명시 |
| `ModuleNotFoundError: fastapi` (설치 후) | 다른 Python 인터프리터로 실행 | `sys.executable`과 `pip --version` 경로가 같은지 확인 |
| `pytest: command not found` | 스크립트 경로 미등록 | `python -m pytest`로 실행 |
| 한글 출력이 깨짐 | 콘솔 인코딩 | 실행 전 `$env:PYTHONIOENCODING = "utf-8"` 설정 |
| `ruff`/`mypy` 결과 파일이 비어 보임 | PowerShell 리다이렉션 기본 인코딩(UTF-16) | `Out-File -Encoding utf8` 사용 |

## 보안 주의

- `.env`, API 키, PIN은 절대 저장소에 커밋하지 않습니다.
- `requirements.lock.txt`는 UTF-8(BOM 없음)로 유지합니다. BOM이 붙으면 일부 도구에서 첫 줄 파싱이 실패합니다.
