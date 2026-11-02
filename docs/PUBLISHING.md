# 마켓 등록 가이드 (MCP Registry · PyPI · Agensi)

이 서버는 **무료(MIT)** 로 공개합니다. 등록 대상과 산출물은 다음과 같습니다.

| 대상 | 무엇을 올리나 | 산출물 |
|---|---|---|
| PyPI | 설치형 MCP 서버 (`uvx insurance-claim-mcp`) | `dist/*.whl`, `dist/*.tar.gz` |
| 공식 MCP Registry | 서버 메타데이터 (PyPI 패키지를 가리킴) | `server.json` |
| Agensi.io | 서버를 쓰는 방법을 담은 에이전트 스킬 (무료, 한국판·미국판 2개) | `dist/insurance-claim-mcp-skill.zip`, `dist/us-supplemental-claims-skill.zip` |

Agensi는 MCP 서버가 아니라 SKILL.md 묶음(zip)을 파는 스킬 마켓입니다. 스킬은 이 서버가 연결돼 있어야 동작합니다.
Cloud Run 원격 서버(`/mcp`)는 운영자가 발급한 키가 있어야 하므로 공개 등록에는 넣지 않습니다.

## 0. 공통 준비

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m mypy src
```

버전을 올릴 때는 `pyproject.toml`의 `version`과 `server.json`의 `version`, `packages[0].version`을 같이 바꿉니다.

## 1. PyPI

PyPI 계정과 API 토큰이 필요합니다(본인이 발급).

```powershell
uv build
uv publish            # 토큰 입력 또는 UV_PUBLISH_TOKEN 환경변수
```

설치 확인: 새 폴더에서 `uvx insurance-claim-mcp` 실행 후 `Starting MCP server ... stdio` 로그가 보이면 정상입니다.
README의 `mcp-name: io.github.seothief/insurance-claim-mcp` 줄은 MCP Registry가 PyPI 소유권을 확인하는 데 쓰므로 지우지 않습니다.

## 2. 공식 MCP Registry

PyPI 게시가 끝난 뒤 진행합니다. [mcp-publisher](https://github.com/modelcontextprotocol/registry/releases)를 설치합니다.

```powershell
mcp-publisher login github     # 브라우저에서 seothief 계정으로 승인
mcp-publisher publish          # 저장소 루트의 server.json 사용
```

확인: `https://registry.modelcontextprotocol.io/v0/servers?search=insurance-claim-mcp`
등록되면 PulseMCP 등 레지스트리를 미러링하는 디렉터리에도 순차 반영됩니다.

## 3. Agensi.io (무료 스킬)

```powershell
.\.venv\Scripts\python.exe scripts\build_agensi_zip.py
```

1. https://www.agensi.io/sell 에서 판매자 가입
2. `dist/` 아래 zip 두 개를 각각 별도 스킬로 업로드 (zip마다 최상위 폴더 아래에 `SKILL.md`)
3. 가격: Free, 제목·태그·설명은 `agensi-listing.json`의 `listings` 항목별 값 사용
4. 자동 보안 스캔 → AI 검토 → 사람 검토(보통 24~48시간). 실패 시 사유를 고쳐 다시 올리면 됩니다.

무료 스킬은 정산 계좌(Stripe/KYC)가 필요 없습니다.
