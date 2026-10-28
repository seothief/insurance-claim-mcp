# Insurance Claim MCP V2 — 독립 인프라

V1 코드·컨테이너·DB·배포 워크플로를 재사용하지 않는 별도 서버입니다. 설계사·대리점의 자체 AI가 호출하는 MCP 기반을 제공합니다.

**현재 구현 범위:** 명시적 DB 마이그레이션, V2 DB 소유권 검사, 만료·폐기 가능한 업무 공간별 키, 상태/준비 확인, MCP `get_workspace_context`, 독립 CI/배포·구축 스크립트 및 합성 키로 인증된 릴리스 검사. 고객·보험 등록 및 예상액 계산 도구는 아직 구현하지 않았습니다. V1 호출로 대신 처리하지 않습니다.

## 로컬 실행

Python 3.12 이상과 [uv](https://docs.astral.sh/uv/) 0.9.7 기준입니다. 다음 명령은 **v2 디렉터리**에서 실행합니다.

```bash
uv sync --frozen --extra dev
uv run --frozen python -m claim_mcp_v2.db migrate
uv run --frozen uvicorn claim_mcp_v2.main:app --host 127.0.0.1 --port 8082
```

기본 로컬 DB는 `v2/claim_service_v2.db`입니다. V1의 `DATABASE_URL`, `.env`, `APP_VERSION`은 읽지 않습니다. 서버 시작 시 테이블을 만들거나 기존 DB를 자동 변환하지 않습니다.

다른 터미널에서 최초 설계사 자격을 발급할 수 있습니다. 원문 키는 1회만 출력되므로 로그·대화에 복사하지 않고 보호된 파일/비밀 저장소로 전달합니다.

```bash
umask 077
uv run --frozen python -m claim_mcp_v2.admin bootstrap \
  --workspace-name pilot --actor-name agent > local.credentials.json
uv run --frozen python scripts/smoke.py --url http://127.0.0.1:8082 \
  --key-file local.credentials.json
```

연결: `http://127.0.0.1:8082/mcp` + 보호된 `Authorization: Bearer <V2 키>` 헤더. 자격 유효기간 기본 30일, 최대 90일입니다. 같은 대리점이라도 설계사별 자격을 발급해야 합니다. 현재 bootstrap은 새 업무 공간과 설계사를 함께 생성하는 운영 명령이며, 대리점 구성원 추가는 후속 기능입니다.

## PostgreSQL + 컨테이너

```bash
read -rs -p 'V2 local PostgreSQL password: ' V2_POSTGRES_PASSWORD
export V2_POSTGRES_PASSWORD
docker compose -f compose.yml up -d --build --wait app-v2
python3 scripts/smoke.py --url http://127.0.0.1:8082
```

개발 비밀번호는 URL-safe 문자(영문·숫자·`-`·`_`)로 정하고 볼륨 재사용 시 동일한 값을 유지하세요. Compose 프로젝트 `insurance-claim-v2`, DB 서비스 `db-v2`, 볼륨 `pgdata-v2`, 호스트 포트 `127.0.0.1:8082`로 V1과 분리합니다. DB는 호스트에 포트를 공개하지 않습니다. 최초 migration 서비스가 성공해야 앱을 시작합니다. 볼륨 삭제 명령은 운영 데이터가 아닌 명시적으로 폐기 가능한 개발/CI 환경에서만 사용하세요.

## 시험

```bash
uv run --frozen pytest -q
uv run --frozen ruff check src tests scripts
uv run --frozen mypy src
```

`V2_TEST_DATABASE_URL`을 지정하면 별도 로컬 PostgreSQL에서 DB 시험을 실행합니다. 테스트는 테이블을 삭제할 수 있으므로 운영 URI를 넣지 마세요. 로컬 호스트와 `test-v2` 소유권 표식만 허용합니다. CI는 별도 PostgreSQL 컨테이너를 생성합니다.

클라우드 구축·비밀·배포·운영자 명령 및 미확인 항목: [V2 배포 가이드](../docs/v2-deployment.md).
