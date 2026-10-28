# V2 독립 서버·DB·배포 가이드

## 1. 분리 원칙과 현재 상태

사용자 결정: **V1은 그대로 두고 V2용 새 서버·Neon 별도 프로젝트 DB·배포 파이프라인을 구성**한다. 같은 프로세스·DB·MCP 엔드포인트에 V2를 추가한다는 이전 설계보다 이 결정이 우선한다.

| 항목 | V1 — 변경하지 않음 | V2 — 신규 구성 |
|---|---|---|
| 실행 코드 | `src/claim_service` | `v2/src/claim_mcp_v2` |
| 의존성 | 루트 `pyproject.toml`·lock | `v2/pyproject.toml`·`uv.lock` |
| 컨테이너 | 루트 `Dockerfile` | `v2/Dockerfile`, build context `v2` |
| Cloud Run | `insurance-claim-mcp` | `insurance-claim-mcp-v2` |
| DB | 기존 Neon 프로젝트/DB | 새 Neon 프로젝트의 `insurance_claim_v2` |
| DB 비밀 | 기존 `DATABASE_URL` | `insurance-claim-v2-database-url` 및 `insurance-claim-v2-migration-database-url` |
| 릴리스 점검 키 | 해당 없음 | `insurance-claim-v2-smoke-key`, 합성 workspace의 context 확인만 사용 |
| 배포 | 기존 `main` CI/Deploy | `v2` 브랜치의 독립 CI/Deploy |
| HTTP MCP | 기존 서비스 URL의 `/mcp` | 새 서비스 URL의 `/mcp` |

GCP 프로젝트 자체는 기존 프로젝트를 명시적으로 선택할 수 있지만 리소스·서비스 계정·OIDC provider·비밀·저장소를 분리한다. 배포 계정에는 V2 서비스/Job 단위로만 Cloud Run 변경 권한을 부여한다. 프로젝트 전체 `run.admin`/`run.developer`는 부여하지 않는다.

**구현된 것은 인프라 기반과 구축 코드다. 실제 클라우드 생성·배포는 별도 실행·검증이 필요하다.** V2는 현재 `get_workspace_context`만 제공하며 고객·보험·평가 도구는 아직 없다. Cloud Run 준비 확인 성공도 업무 기능·약관 검증 완료를 의미하지 않는다.

## 2. 운영자 사전 준비

필요한 자격은 로컬 비밀 저장소/환경변수에만 설정한다. 대화나 저장소 파일에 토큰·DB URL을 붙여 넣지 않는다.

- GCP: 대상 프로젝트의 API 활성화, V2 리소스/서비스 계정/WIF/IAM 생성 권한이 있는 운영자 인증
- Neon: 별도 프로젝트 생성 권한이 있는 `NEON_API_KEY`; 현재 요금제의 프로젝트 한도 확인
- GitHub: 저장소의 `v2` 브랜치·보호 규칙 및 `v2-production` environment/변수·비밀 설정 권한
- 로컬: gcloud, Python 3.12+, uv 0.9.7. 컨테이너 시험에는 Docker/Compose 필요

GCP 로그인·활성 프로젝트·공용 자격을 스크립트가 자동 변경하지 않는다. 모든 클라우드 명령은 `V2_GCP_PROJECT_ID`를 명시한다. 신규 리소스에는 요금이 발생할 수 있으며 스크립트는 요금제를 자동 상향하지 않는다.

### 대화형 운영자 로그인 — 직접 입력이 필요한 단계

현재 VM 기본 서비스 계정의 오류는 추가 검사에서 `ACCESS_TOKEN_SCOPE_INSUFFICIENT`로 확인됐다. 단순 IAM 누락으로 단정하거나 이 VM 계정에 Owner 권한을 추가하지 않는다. 사용자와 확인한 기존 프로젝트에 대해 **별도 V2 CLI 설정으로 운영자 로그인**을 받는다.

같은 Linux 환경의 실제 터미널에서 다음 명령을 실행한다.

```bash
python3 /home/seothief83/workspace/insurance-claim-mcp/v2/scripts/operator_access.py login \
  --project project-93d02748-0cbc-4596-902 --region asia-northeast3
```

1. Google: 선택한 프로젝트를 구성할 수 있는 사용자 계정으로 브라우저에서 로그인한다. 인증 코드 입력을 요청하면 해당 터미널에만 입력한다.
2. GitHub: [임시 fine-grained 토큰](https://github.com/settings/personal-access-tokens/new)을 만든다. 저장소는 **`seothief/insurance-claim-mcp`만**, 만료는 7일을 권장한다. Repository permissions의 **Actions, Administration, Contents, Environments, Secrets, Variables는 Read and write**, **Workflows는 Write**로 설정한 뒤 숨김 입력에 붙여 넣는다. 대안으로 classic 토큰의 `repo`/`workflow` scope도 지원하지만 다른 저장소까지 범위가 넓어질 수 있다.
3. Neon: 콘솔의 계정 설정 → API keys에서 새 프로젝트 생성이 가능한 임시 API 키를 발급하고, 터미널의 숨김 입력에 붙여 넣는다.

토큰·인증 코드·비밀 파일 내용을 채팅에 보내지 않는다. 설정은 `~/.config/insurance-claim-v2/` 아래에만 저장한다. 디렉터리는 0700, 비밀 파일은 0600이며 Neon/GitHub 토큰은 로컬 평문 파일이므로 이 호스트와 같은 OS 사용자에 대한 신뢰가 필요하다. `gh auth login`은 기존 전역 키링에 영향을 줄 수 있어 **호출하지 않는다**. GitHub 작업은 전용 `GH_TOKEN` 환경변수로만 인증하고 키가 없을 때도 키링으로 fallback하지 않는다. 기본 gcloud/GitHub 설정·VM 계정·전역 Git 설정은 보존한다. 도우미는 로그인과 **읽기 전용 접근 확인만** 수행하며 리소스·IAM·브랜치를 생성하지 않는다. Fine-grained 토큰의 실제 쓰기 권한은 이후 V2 전용 설정 작업에서 각각 확인한다.

독립적으로 접근 상태를 재확인하려면 다음 명령을 사용한다. API 응답 본문이나 비밀은 출력하지 않는다.

```bash
python3 /home/seothief83/workspace/insurance-claim-mcp/v2/scripts/operator_access.py check
```

도우미의 자격은 부모 셸에 자동 export되지 않는다. 이후 자동 작업에서는 보호된 설정을 메모리로만 읽고 `operator_environment`로 V2 전용 환경을 전달한다. 아래 수동 운영 절차는 운영자가 동일한 전용 환경과 비밀을 안전하게 공급하는 경우의 참고용이다.

환경 구성·WIF 배포 검증이 끝나면 임시 GitHub/Neon 토큰을 발급 화면에서 폐기하고, 운영자용 로컬 비밀 사본의 보관/삭제를 결정한다. 배포 서버의 DB 비밀이나 설계사 키와 임시 구축용 토큰을 혼동하지 않는다.

## 3. GCP 리소스 준비

운영자가 대상과 권한을 확인한 뒤 저장소 루트에서 실행한다.

```bash
export V2_GCP_PROJECT_ID='<선택한 GCP 프로젝트 ID>'
export V2_GCP_REGION='asia-northeast3'
bash v2/scripts/bootstrap-gcp.sh
```

생성/설정 대상:

- Artifact Registry `insurance-claim-v2`
- 서비스 계정 `claim-v2-runtime`, `claim-v2-migrator`, `claim-v2-deployer`
- V2용 DB 비밀 2개와 릴리스 점검 키 비밀 1개(이 단계에서는 값/버전 없음)
- Cloud Run 서비스 `insurance-claim-mcp-v2`, migration Job `insurance-claim-mcp-v2-migrate`
- WIF pool `insurance-claim-v2`, provider `github-v2`

처음에는 비밀 없는 placeholder 서비스/Job을 만들어 리소스 단위 IAM을 부여한다. 서비스는 원격 MCP 클라이언트를 위한 공개 네트워크 진입점을 갖지만 placeholder에는 고객 자료나 업무 기능이 없다. placeholder 생성은 V2 앱 배포 성공으로 간주하지 않는다. migration Job은 이 단계에서 실행하지 않는다.

권한 분리:

| 주체 | 허용 범위 |
|---|---|
| runtime SA | V2 runtime DB secret만 열람 |
| migrator SA | V2 migration DB secret·합성 릴리스 점검 키 열람 |
| deployer SA | V2 Artifact Registry writer, V2 서비스/Job developer·Job 실행, V2 runtime/migrator SA actAs, 점검 키만 열람(DB 비밀 직접 열람 없음) |
| GitHub OIDC | 해당 저장소 + `refs/heads/v2` + `v2-production` environment가 모두 일치할 때만 deployer 가장 |

운영자 bootstrap 권한은 release 계정에 전달하지 않는다. 조직 정책이 public invocation/WIF/리전 등을 제한하면 정책을 임의 완화하지 말고 별도 승인받는다.

## 4. Neon 별도 프로젝트와 DB 생성

`NEON_API_KEY`는 보호된 로컬 환경변수로 공급하고, **v2 디렉터리**에서 실행한다.

```bash
uv sync --frozen --extra dev
uv run --frozen python scripts/provision_neon.py --create-project
```

- 기본 Neon 리전은 기존 문서와 같은 Singapore의 `aws-ap-southeast-1`이다. 필요한 경우 최초 생성 전에 `--region`으로 선택한다. 리전/국외 처리 적합성은 출시 전 검토한다.
- 새 프로젝트 이름 `insurance-claim-mcp-v2`, 새 DB `insurance_claim_v2`를 만든다. V1 프로젝트나 브랜치를 복제·수정하지 않는다.
- `.neon-state.json`에는 새 프로젝트 ID만 0600 권한으로 기록한다. 실패 후 이 파일을 보존하고 같은 명령으로 재개한다. 파일 없이 반복 생성하지 않는다.
- SQL로 제한된 로그인 역할 `insurance_claim_v2_app`을 만든다. Neon Console/API로 만든 역할은 `neon_superuser`를 상속하므로 앱 역할 생성에 사용하지 않는다.
- 소유자 URI는 migration 비밀에, 제한된 역할 URI는 runtime 비밀에 각각 stdin으로 전송한다. DB URL·비밀번호·토큰은 파일/표준 출력/명령 인자에 넣지 않는다.
- TLS는 `sslmode=verify-full`과 명시적 시스템 CA 파일 `/etc/ssl/certs/ca-certificates.crt`를 사용한다. 번들 libpq의 `sslrootcert=system` 기본 경로 차이로 발생한 검증 실패를 실제 접속 시험으로 확인해 CA 경로를 명시했으며, 인증서/호스트 검증은 끄지 않는다. 컨테이너 빌드도 해당 CA 파일의 존재를 확인한다. 자격을 만들었다고 V2 테이블이 자동 생성되지는 않는다.
- 별도 합성 workspace의 인증된 MCP 검사를 위한 점검 키도 비밀 저장소에 생성한다. migration은 원문을 출력하지 않고 해시만 등록하며, 초기 데이터에 고객 정보는 없다. 점검 키는 고객 업무 권한으로 확대하지 않는다.
- 결과에는 GitHub 설정에 필요한 프로젝트 ID와 숫자 secret version만 출력한다. 재실행 시 기존 앱 비밀번호·점검 키를 자동 회전하지 않는다.

프로젝트 생성과 state 기록 사이에 네트워크/파일 오류가 나면 콘솔에서 생성 여부를 먼저 확인한다. 한도 초과 시 유료 업그레이드·다른 프로젝트 재사용을 자동 실행하지 않는다.

공식 근거: [Neon 역할과 neon_superuser](https://neon.com/docs/manage/roles).

## 5. GitHub 설정과 배포 브랜치

GitHub environment **`v2-production`**을 만들고 승인자 및 배포 허용 브랜치를 `v2`로 제한한다. 브랜치 보호에서 PR 검토와 CI V2를 필수로 설정한다. 환경 이름만 적는다고 승인 규칙이 자동 생성되지는 않는다.

| 종류 | 이름 | 값 |
|---|---|---|
| Variable | `V2_GCP_PROJECT_ID` | 선택한 프로젝트 |
| Variable | `V2_GCP_REGION` | 예: `asia-northeast3` |
| Variable | `V2_NEON_PROJECT_ID` | 새 Neon 프로젝트 ID |
| Variable | `V2_DATABASE_SECRET_VERSION` | runtime secret의 숫자 버전 |
| Variable | `V2_MIGRATION_SECRET_VERSION` | migration secret의 숫자 버전 |
| Variable | `V2_SMOKE_SECRET_VERSION` | 합성 릴리스 점검 키의 숫자 버전 |
| Secret | `V2_GCP_WORKLOAD_IDENTITY_PROVIDER` | bootstrap 출력의 새 provider 전체 이름 |
| Secret | `V2_GCP_SERVICE_ACCOUNT` | `claim-v2-deployer@<project>.iam.gserviceaccount.com` |

GitHub에 DB URL이나 Neon API token을 복사할 필요는 없다. Cloud Run은 Secret Manager의 **숫자 버전**을 참조하며 `latest`로 자동 교체하지 않는다.

중요: 기존 `main`은 V1 자동 배포에 연결되어 있다. **V2 작업을 `main`으로 합쳐 배포하지 않는다.** 별도 `v2` release 브랜치에 검토된 변경을 반영하면 `Deploy V2 to Cloud Run`의 push 트리거가 동작한다. workflow 파일은 해당 브랜치에 있어야 한다. `workflow_dispatch`의 UI/API 수동 실행은 파일이 기본 브랜치에도 존재해야 하는 GitHub 제약이 있으므로, 최초 릴리스는 `v2` push 트리거를 사용한다. 이 제약을 우회하려고 V1 워크플로를 수정하지 않는다.

이번 로컬 작업은 브랜치 생성·푸시·GitHub environment 설정·클라우드 실행을 자동 완료하지 않는다.

## 6. 릴리스 절차와 실패 처리

1. V2 전용 frozen lock 설치·Ruff·mypy·SQLite/PostgreSQL 테스트를 실행한다.
2. 별도 Compose 컨테이너에서 migration→준비 확인→키 발급→인증된 MCP 호출을 검사한다. 합성 CI 자격만 보호된 임시 파일에 저장한다.
3. `v2-production` 승인 후 OIDC의 repository/ref/environment를 사전 확인하고 V2 deployer를 가장한다. JWT 원문은 로그에 남기지 않으며 실제 서명·issuer·audience 검증은 GCP가 수행한다. Provider는 고정 `sub` 형식 대신 명시적인 repository·ref·environment claim을 각각 제한한다.
4. `v2` build context만 빌드하고 V2 Artifact Registry에 푸시한다. 실제 배포에는 이미지 digest를 사용한다.
5. migration Job은 migration 전용 SA·DB 비밀로 명시적 migration을 실행한다. V1/미소유 DB·다른 프로젝트 표식은 거부한다. 별도 점검 키의 해시를 합성 workspace에 등록/확인하고 유효기간을 90일로 갱신한다. 폐기된 키·비활성 계정은 자동 활성화하지 않는다.
6. 새 앱 revision을 **트래픽 0%**와 candidate tag로 배포한다. runtime SA에는 현재 인프라 도구에 필요한 SELECT만 허용한다.
7. candidate의 service/version/readiness와 무인증 MCP 401을 확인한다. 이어 비밀 저장소에서 읽은 점검 키를 환경변수로만 공급하여 initialize·도구 열거·인증된 context 호출 및 기대 workspace를 검사한 뒤 100% 전환한다.
8. canonical URL에서도 같은 검사를 수행한다. 이 단계가 실패하면 직전 **V2** revision별 트래픽 배분으로 복구를 시도한다. 복구 실패는 운영자 조치가 필요하다.

migration/후보 검사가 실패하면 기존 V2 트래픽을 승격하지 않는다. V1 서비스·DB·트래픽은 어떤 단계에서도 대상에 넣지 않는다. DB migration은 additive/하위 호환을 유지해야 하며 traffic 복구가 DB를 되돌리는 것은 아니다. 파괴적 migration·데이터 복구는 별도 승인/백업 계획이 필요하다.

원격 릴리스 probe는 합성 workspace의 context만 검사하고 실제 고객 자격을 만들지 않는다. 원문 점검 키는 명령 인자/파일/출력에 넣지 않고 환경변수로 전달하며 shell tracing을 끈다. 실제 설계사 자격은 아래 절차로 별도 발급한다. 점검 키 교체는 기존 DB 해시와 일치해야 하므로 별도 운영자 절차로 처리한다. 상용 AI 앱별 호환성은 실제 앱에서 추가 확인해야 한다.

## 7. 최초 운영자 키와 운영 확인

migration 후, 승인된 **로컬 운영자 환경**에서 migration secret의 URI를 `V2_DATABASE_URL`로 공급한다. production 설정과 `V2_DATABASE_PROJECT_ID`도 지정한다. URI는 셸 히스토리나 로그에 넣지 않는다.

```bash
umask 077
uv run --frozen python -m claim_mcp_v2.admin bootstrap \
  --workspace-name pilot --actor-name agent > pilot.credentials.json
uv run --frozen python scripts/smoke.py --url '<새 V2 서비스 HTTPS URL>' \
  --key-file pilot.credentials.json
```

**bootstrap을 Cloud Run Job/CI에서 실행하면 원문 키가 클라우드 로그에 남을 수 있으므로 금지한다.** 앱 runtime 역할은 SELECT 전용이므로 이 관리 명령에 사용할 수 없다. 키를 설계사 클라이언트의 비밀 저장소로 안전하게 전달하고 로컬 사본의 보관/폐기를 관리한다. 폐기 명령은 `python -m claim_mcp_v2.admin revoke --key-id <내부 키 ID>`다.

현재 업무 도구가 없으므로 실제 고객 데이터를 넣지 않는다. 고객 접근 권한·자료 처리 근거·감사·호출 제한·보관/삭제 및 지급 조건 검증 구현이 완료되기 전에는 다고객 업무 서비스를 출시하지 않는다.

## 8. 이번 환경에서의 미완료 항목

- 사용자 운영자 로그인과 GitHub 토큰 권한 보완 후 GCP V2 리소스, Neon 별도 프로젝트/DB/앱 역할, 비밀 버전 및 GitHub 환경/승인/변수·WIF 참조 설정을 실제 완료했다. 개인 Neon 키에는 조직 ID를 명시한다.
- 초기 VM 계정의 scope 문제를 해결하려고 기본 자격을 변경하거나 광범위한 역할을 추가하지 않았다. V2 전용 사용자 로그인 설정을 사용한다.
- 로컬 Docker가 없어 이미지 빌드/Compose는 원격 CI에서 확인해야 한다. 생성된 placeholder를 V2 앱으로 교체하고 GitHub OIDC·제한된 배포 IAM·실제 migration·후보/정식 URL을 검증해야 한다.
- 테스트·린트·타입 검사 및 V1 보호 확인의 실제 결과는 [STATUS](../STATUS.md)에 기록한다.
