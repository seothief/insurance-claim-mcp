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

## 1. 자동 게시 (PyPI + MCP Registry)

`v*` 태그를 push하면 `.github/workflows/publish.yml`이 빌드 → PyPI → 공식 MCP Registry 순서로 게시합니다.
PyPI는 Trusted Publishing, MCP Registry는 GitHub OIDC를 쓰므로 토큰이나 로그인이 필요 없습니다.

### 최초 1회: PyPI에 신뢰 게시자 등록

PyPI → 내 프로젝트 → `insurance-claim-mcp` → **관리(Manage)** → **게시(Publishing)** → GitHub 게시자 추가:

| 항목 | 값 |
|---|---|
| Owner | `seothief` |
| Repository name | `insurance-claim-mcp` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

GitHub 쪽 `pypi` 환경은 만들어져 있고, `v*` 태그에서만 배포되도록 제한돼 있습니다.

### 릴리스할 때마다

1. `pyproject.toml`의 `version`, `server.json`의 `version`과 `packages[0].version`을 같은 값으로 올리고 main에 머지
2. 태그 push

```powershell
git switch main
git pull
git tag v0.2.0
git push origin v0.2.0
```

태그와 두 파일의 버전이 다르면 build 단계에서 멈춥니다. 진행 상황은 GitHub **Actions → Publish**에서 볼 수 있습니다.
확인: https://pypi.org/project/insurance-claim-mcp/ , `https://registry.modelcontextprotocol.io/v0/servers?search=insurance-claim-mcp`

### 수동 게시 (자동 게시가 안 될 때만)

```powershell
uv build
uv publish --token <PyPI API 토큰>
mcp-publisher login github
mcp-publisher publish
```

PyPI는 계정 비밀번호로는 업로드를 받지 않습니다. 사용자 이름을 물으면 `__token__`을 입력합니다.
README의 `mcp-name: io.github.seothief/insurance-claim-mcp` 줄은 MCP Registry가 PyPI 소유권을 확인하는 데 쓰므로 지우지 않습니다.

## 3. Agensi.io (무료 스킬)

```powershell
.\.venv\Scripts\python.exe scripts\build_agensi_zip.py
```

1. https://www.agensi.io/sell 에서 판매자 가입
2. `dist/` 아래 zip 두 개를 각각 별도 스킬로 업로드 (zip마다 최상위 폴더 아래에 `SKILL.md`)
3. 가격: Free, 제목·태그·설명은 `agensi-listing.json`의 `listings` 항목별 값 사용
4. 자동 보안 스캔 → AI 검토 → 사람 검토(보통 24~48시간). 실패 시 사유를 고쳐 다시 올리면 됩니다.

무료 스킬은 정산 계좌(Stripe/KYC)가 필요 없습니다.
