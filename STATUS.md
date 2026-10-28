# 진행 현황

최종 갱신: 2026-10-28

## V2 원격 CI 통과·OIDC 배포 조건 보완 (2026-10-28)

- 사용자 승인으로 V2 변경을 커밋 `0ab1675`로 게시함. 원격 `v2`만 새로 만들었고 `main`은 기존 `6736a02` 그대로임.
- GitHub 실행 `40641503010`: **ci / test, ci / container 통과**. 실제 GitHub 러너에서 frozen 설치·Ruff·mypy·SQLite/PostgreSQL 시험·컨테이너 빌드·migration·인증 MCP smoke를 확인함.
- `v2` 브랜치에 force push/삭제 금지·PR 검토·CI check 정책을 설정함. 관리자 비상 우회는 유지하지만 production 환경은 별도 사용자 승인이 필수임. V1/main 보호 규칙은 변경하지 않음.
- 사용자가 첫 배포를 승인했으나 `google-github-actions/auth`에서 GCP provider attribute condition 거부로 중단됨. 앱 이미지 게시·운영 migration·트래픽 전환 이전에 중단됐으며 V1을 수정하지 않음.
- 기본 GitHub subject 설정과 V2 provider issuer/mapper를 확인함. 고정 `sub` 문자열 의존을 제거하고 **repository·ref·environment를 각각 정확히 확인**하는 조건으로 V2 provider만 보완함. 서명·issuer·audience 검증은 GCP가 계속 수행함.
- 새 배포 전 OIDC 사전점검은 repository/ref/environment/sub 식별 정보만 출력하고 JWT·요청 토큰은 출력하지 않음. 이는 GCP의 실제 서명 검증을 대체하지 않으며, 새 실행에서 실제 claim과 인증 성공을 확인해야 함.
- 보완 후 로컬 V2 **30 passed, 1 skipped**, Ruff·actionlint 통과. 독립 검토의 OIDC 요청 리다이렉트 위험도 반영해 Authorization 헤더를 다른 위치로 전달하지 않도록 리다이렉트를 거부하고 회귀 시험을 추가함. 아직 V2 앱 배포가 완료됐다고 주장하지 않음.

## V2 클라우드 리소스·배포 환경 실제 설정 (2026-10-28)

- 사용자의 운영자 로그인 후 GCP bootstrap 권한과 GitHub 저장소 접근을 재확인함. Neon은 개인 키에 필요한 `org_id` 누락이 원인이었으며, 조직 1개(Free)를 확인해 명시적으로 지정함. 키를 다시 받거나 출력하지 않음.
- GitHub 환경 생성의 실제 403 응답에서 `administration=write` 누락을 확인했고, 사용자가 기존 토큰 권한을 보완한 뒤 환경 생성에 성공함. 별도 `v2` 브랜치 커밋·게시와 CI/CD 검증도 사용자에게 명시적으로 승인받음.
- **실제 생성:** Cloud Run `insurance-claim-mcp-v2`·migration Job, 전용 Artifact Registry, runtime/migrator/deployer 서비스 계정, DB/점검 비밀 3개, V2 WIF pool/provider와 리소스 단위 IAM. 이 시점의 서버는 아직 비밀 없는 placeholder이며 업무 서버 배포 완료가 아님.
- **실제 생성:** Neon 별도 프로젝트 `divine-scene-58993737`, DB `insurance_claim_v2`, SQL로 생성한 제한된 앱 역할. V2 이름의 프로젝트가 1개뿐임을 확인함. 기존 V1 프로젝트/DB는 변경하지 않음.
- runtime/migration DB URI 및 합성 배포 점검 키를 각각 GCP 비밀 버전 **1**로 저장함. GitHub에는 DB URL·Neon API 키를 복사하지 않고 숫자 버전과 WIF 참조만 설정함.
- GitHub `v2-production` 환경에 필수 사용자 승인, `v2` 브랜치만 허용하는 정책, V2 변수 6개와 WIF 참조 비밀 2개를 실제 설정함. `main`과 V1 워크플로는 변경하지 않음.
- 실제 Neon 초기화 중 일시적 423 잠금을 확인해 프로젝트 생성 자체는 재시도하지 않고 하위 잠금 응답만 제한 재시도하도록 보완함. 프로젝트 ID private 상태 기록의 `Path.open(opener=...)` 오류를 수정하고 회귀 시험을 추가함.
- 실제 libpq 연결에서 `sslrootcert=system`의 CA 경로 차이로 검증 실패를 확인함. `/etc/ssl/certs/ca-certificates.crt`를 명시해 `verify-full` 접속을 확인했고 Docker 빌드도 해당 파일 존재를 검사하도록 보완함. 인증서/호스트 검증을 끄지 않음.
- **V1 보호 확인:** 리소스 구성 전후 Cloud Run generation·준비 revision·트래픽 메타데이터가 동일함. V1 실행 코드·의존성·컨테이너·CI/배포 파일도 그대로 유지함.
- 최신 로컬 시험: V2 **28 passed, 1 skipped**, Ruff·mypy·actionlint 통과. 실제 GitHub CI·V2 앱 migration/배포·후보/정식 URL 검증은 다음 단계에서 수행함.

## V2 운영자 접근 설정 준비 (2026-10-28)

- 사용자가 기존 GCP 프로젝트 `project-93d02748-0cbc-4596-902`에 V2 리소스를 분리하고, 같은 Linux 환경의 터미널에서 직접 로그인·비밀 입력할 수 있다고 확인함.
- 읽기 전용 REST `testIamPermissions` 추가 진단: 현재 VM compute 서비스 계정의 오류는 **`ACCESS_TOKEN_SCOPE_INSUFFICIENT`**임. 앞선 IAM 부족 분류를 구체화/정정함. 이 VM 계정에 광범위한 역할을 추가하지 않고 별도 운영자 로그인으로 진행함.
- GitHub CLI 2.103.3을 릴리스 checksum 확인 후 사용자 캐시에 설치함. 인증은 실행하지 않았고 기본 CLI·Git·VM 자격 설정은 유지함.
- `v2/scripts/operator_access.py` 추가: 실제 터미널에서만 Google 브라우저 로그인 및 GitHub/Neon 임시 키 숨김 입력, V2 전용 CLI/Git 경로·0700/0600 비밀 저장, 민감 출력 없는 읽기 전용 접근 검사. 설정 파일은 저장소 외부 `~/.config/insurance-claim-v2/`에 저장하며 로컬 평문 보관임을 안내함.
- 독립 검토에서 `gh auth login --insecure-storage`도 전역 키링에 영향을 줄 수 있다는 지적을 받아 해당 호출을 제거함. GitHub는 저장소 한정 임시 fine-grained 토큰을 직접 숨김 입력하고 명시적 `GH_TOKEN`으로만 사용하며, 키가 없을 때도 기존 키링으로 fallback하지 않도록 변경함.
- 아직 사용자의 대화형 로그인·Neon 키 입력을 받지 않았으므로 환경 설정 완료나 클라우드 리소스 생성·배포 완료를 주장하지 않음. 도우미 실행 후 접근 권한을 재검증하고 필요한 설정만 추가 요청할 예정.
- 도우미 테스트 추가 후 V2 SQLite **26 passed, 1 skipped**. V2 `ruff check src tests scripts`·`mypy src` 통과. 시스템 Python 3.10에서 도우미 `--help` 실행도 확인함. 새 보호 파일·환경 분리·기존 자격 보존 테스트는 합성 키만 사용했으며 실제 사용자 로그인을 수행하지 않음.

## V2 독립 인프라 기반 구축 (2026-10-28)

### 사용자 결정과 변경 범위

- V1은 유지하고 V2용 새 서버·DB·배포 파이프라인을 별도로 구축하도록 요청받음. DB는 Neon 별도 프로젝트를 선택함. 앞선 동일 서버/DB 내 확장 제안보다 이 결정이 우선함.
- 브랜치: `feat/v2-isolated-infrastructure`. 기존 미커밋 문서를 보존하며 진행. V1의 `src/`, `tests/`, `scripts/`, 루트 의존성·Dockerfile·Compose 및 기존 CI/Cloud Run 배포 워크플로는 수정하지 않음.

### 구현한 사항 — 로컬 코드 기준

- `v2/` 독립 Python 패키지·frozen `uv.lock`·비루트 컨테이너·Compose·테스트 추가. V1 모듈과 환경변수 `DATABASE_URL`/`APP_VERSION`/`.env`를 재사용하지 않음.
- 별도 ASGI/FastMCP 서버: `/api/health`, `/api/ready`, `/api/version`, `/mcp`와 인증된 `get_workspace_context`. 고객·보험·예상액 계산 업무 도구는 아직 구현하지 않았고 V1로 fallback하지 않음.
- 명시적 schema migration과 DB service/project/version 소유권 검사. V1 테이블·다른 프로젝트·미소유 DB를 거부하고 앱 시작 시 자동 migration하지 않음.
- actor·workspace·membership·만료/폐기 키 분리. 서버에는 키 해시만 저장하며 요청별 identity 정리, 비활성 소속 거부, V1/위조 identity 헤더 차단 구현.
- GCP bootstrap 스크립트: V2 전용 Cloud Run 서비스·migration Job·Artifact Registry·서비스 계정·DB 비밀·점검 키·WIF 구성. 배포 계정의 Cloud Run 권한은 V2 리소스에만 부여하며 V1 대상 명령은 없음. 실제 실행하지는 않음.
- Neon 구축 스크립트: 별도 프로젝트/DB 생성·재개, SQL로 제한된 앱 역할 생성, owner/runtime DB 비밀 분리·직접 전달, 인증서 검증 TLS, 기존 자격 자동 회전 금지. 실제 Neon API를 호출하지는 않음.
- 독립 CI 및 `v2` 브랜치/env 승인 기반 배포: 이미지 digest → migration Job → 0% candidate → 실제 인증 MCP/workspace 확인 → V2 트래픽 승격 → 정식 URL 재검사. 실패 시 기존 V2 트래픽 복구를 시도함. 실제 GitHub/Cloud Run 실행은 하지 않음.
- `v2/README.md`, `docs/v2-deployment.md` 작성 및 기존 요구사항/계획에 독립 서버 결정을 반영함.

### 실제 검증 결과

- Python 3.12.12를 사용자 캐시의 격리된 uv 환경으로 준비함. 시스템 Python·V1 의존성/자격 설정은 변경하지 않음.
- V1 회귀: `v2/.venv/bin/pytest -q`를 저장소 루트에서 실행, **71 passed**. `git diff --exit-code`로 V1 실행/배포 파일 무변경 확인.
- V2 SQLite: **21 passed, 1 skipped**(PostgreSQL 전용 권한 시험). V2 PostgreSQL: 사용자 캐시의 일회성 PostgreSQL 16.2에서 **22 passed**. 운영 DB를 사용하지 않았으며 시험 서버는 종료함.
- V2 `ruff check src tests scripts`, `mypy src` 통과. 새 GitHub 워크플로 2개는 actionlint 1.7.8 통과.
- 실제 로컬 HTTP 시험: 명시적 migration·합성 점검 키 등록 후 Uvicorn에서 initialize·도구 열거·인증된 workspace 호출 통과. SQLite와 **별도 읽기 전용 PostgreSQL 앱 역할** 양쪽에서 확인함.
- 오프라인 배포 제어 시험: migration/후보 실패 시 미승격, 정식 URL 실패 시 이전 V2 트래픽 복구 명령, 같은 SHA의 다른 workflow run revision 구분 확인.
- 독립 검토의 인증된 배포 probe 누락·같은 SHA revision 충돌 지적을 보완했고, 재검토에서 해당 변경의 추가 blocker는 발견되지 않음. 이는 실제 클라우드 검증을 대체하지 않음.

### 실제 인프라 적용의 남은 조건

- 설정된 GCP 프로젝트의 Cloud Run 메타데이터 조회가 **IAM 권한 부족**으로 실패함. 인증·IAM·프로젝트를 자동 변경하지 않았으며 서비스/Job/비밀/WIF를 실제 생성하지 않음.
- `NEON_API_KEY`가 없어 새 Neon 프로젝트·DB를 생성하지 않음. GitHub environment/보호 규칙/변수·비밀·원격 브랜치 설정, 커밋·푸시·실제 배포도 실행하지 않음.
- 로컬 Docker가 없어 이미지 빌드·Compose는 미실행. 실제 Neon API·GCP IAM/WIF·Cloud Run 배포/롤백·상용 AI 앱 연결은 운영자 자격 설정 후 검증해야 함.
- 다음 적용 절차는 `docs/v2-deployment.md` 참조. 고객 업무 기능의 출시에는 별도 권한·처리 근거·감사·호출 제한·자료 수명·규칙 검증 구현이 추가로 필요함.

## 최신 진행 상황 (2026-10-28)

### 사용자 확인 및 합의

- 사용자가 실제 데이터 입력·MCP 연결·예상 보험금 산출까지 핵심 기능 검증을 완료했다고 확인함. 이번 문서 작업에서 해당 운영 결과를 재시험하지는 않음.
- V2의 직접 이용자는 보험설계사·대리점이며, 각자가 사용하는 AI가 상담·문서 판독·업무 처리를 담당하고 본 프로젝트는 MCP 서비스만 전담함. 자체 UI·CRM·고객용 앱·업무 REST API는 초기 범위에서 제외함.

### 코드 확인 및 설계 제안

- 현재 키 소유자와 보험 가입자가 `user_id`로 결합되어 있고, 계약은 `(user_id, company, product_name)`로 업서트됨을 코드에서 확인함. V2는 호출자·업무 공간·고객·명시적 권한을 분리하고 복수 계약 식별을 추가하는 방향으로 제안함.
- 현재 증권 출처 특약의 `rule_config_override`는 미검증 표준 규칙을 대체해 평가할 수 있음. V2에서는 출처 진술과 조건 검증을 분리하고, 미검토 override로 검증 게이트를 통과시키지 않는 요구사항을 명시함. 기존 엔진이나 데이터는 변경하지 않음.
- `docs/v2-requirements.md` 작성: 합의된 범위, P0 요구사항·수용 기준, 새 MCP 계약 후보, 개인정보·권한·규칙 검증 및 출시 게이트. 제안된 V2 도구·경로는 아직 구현되지 않음.
- `docs/v2-implementation-plan.md` 작성: V1 보존형 테이블·인증 분리, S0~S5 구현 계획, 필수 시험, 실제 AI 호환성 확인 및 이행·복구 전략. README에 설계 링크 추가.
- 읽기 전용 독립 검토에서 README의 기존 Fail-Closed 설명이 override 예외를 누락한다는 지적을 받음. 현재 구현의 예외와 클라이언트 제출 출처의 한계, V2 검증 강화가 미구현이라는 점을 README에 반영함.
- 브랜치: `docs/v2-mcp-requirements`. 코드 확인 기준: `6736a02`.

### 검증 및 미실행 범위

- 문서 검증: `git diff --check` 통과. 변경 문서 4개의 UTF-8·파일 끝 개행·코드 펜스·공백 및 로컬 링크 11개 확인, 새 설계 문서의 Markdown 표 10개 열 수 일치 확인. V2 구현·DB 이행·키 발급·운영 배포는 실행하지 않음.
- 현재 로컬 Python은 3.10.12로 프로젝트 요구사항(`>=3.12`)에 미달함. 이번 작업은 문서만 변경하며 Python 테스트·Ruff·mypy 실행 결과를 주장하지 않음.

## 최신 진행 상황 (2026-10-24)

- **종합 이용 가이드 작성(`docs/user-guide.md`)**: 최종 사용자(보험 가입자)와 설정자·운영자를 위한 사용법 문서 신설. "보험비서 시작" 트리거·계정(PIN)·보험 등록·청구 예상액 계산·결과 읽는 법(ELIGIBLE/NOT_EVALUATED/EXCLUDED, verified=false)을 안내하고, 운영자용 API 키 발급·폐기·MCP 연결 설정(X-User-Key)과 보안 주의를 포함. 기존 `docs/mcp-client-setup.md`·`docs/user-api-keys.md`는 기술 상세로 유지하고 교차 링크. README.md 상단에 이용 가이드 링크 추가.

- **KCD 작업 계열 `main` 통합·푸시 완료(실행 결과)**: KCD 표준 코드 마스터(①)·담보 규칙 KCD 참조(②)·특약별 약관 규칙 귀속(③) 5커밋을 `origin/main` 위로 **rebase**한 뒤 `main`에 fast-forward 병합, `git push origin main` 완료(`75c0bac..9749e96`). rebase 중 충돌 3건(STATUS.md 기록 병합, repository.py import 블록, engine.py user_api_keys/rule_config_override 마이그레이션 병합)을 양쪽 모두 보존 방향으로 해결. 원격 작업(2026-10-23, per-user API key 인증 전환)과의 통합 검증: `pytest -q` **71 passed**, `ruff`·`mypy` 통과.
- **KCD 전체 적재 완료(검증된 사실)**: 공공데이터포털 "건강보험심사평가원_상병마스터"(`건강보험심사평가원_상병마스터_20250930.csv`, CP949 인코딩, 47,798행)를 `scripts/load_kcd.py --replace`로 로컬 DB `kcd_codes`에 적재함. **21,299개 코드**(3단 2,085 · 4단 12,503 · 5단 6,711, 대분류 A~Z 26개 전부). catalog의 하드코딩 KCD 참조(골절 S02~S92, 독감 J09~J11, 화상 T20~T32)가 전부 공식 마스터에 존재함을 대조 검증(`RULE_CONFIG_MISSING_PREFIXES=0`).
- **브랜치 정리 완료(실행 결과)**: main에 병합 완료된 로컬 브랜치 4개(`feat/kcd-master`, `feat/disable-synthetic-seed`, `feat/per-user-api-keys`, `feat/policy-management-db`)와 미병합 옛 브랜치 `feat/policy-collection-guidance`를 삭제함. 백업 태그 `backup/pre-cleanup-2026-10-22`는 유지. 이제 로컬 브랜치는 `main`만 남음.
- **설계 결정(배포 KCD 적재 전략)**: 현재 계산 로직(`match_kcd_code`)은 KCD 마스터를 직접 참조하지 않아 배포 DB에 KCD가 없어도 정상 동작함. KCD 마스터를 계산에 직접 참조하는 시점에 **옵션 A(상병마스터 CSV를 리포지토리 포함 → 이미지 COPY → `init_runtime`이 비어 있을 때만 적재)** 로 전환 예정. 공공데이터 이용허락·출처 표기 확인 대기.
- **데이터 포맷 발견(검증된 사실)**: HIRA 상병마스터는 **점 없는 코드**(`S720`)를 쓰고, **숫자 자리수 = 분류 단계**(숫자2=3단, 3=4단, 4~5=5단)다. 이에 맞춰 `domain/kcd.py`의 정규화를 **점 없는 표준형**으로 확장함(`S72.0`→`S720`). 점 있는 KCD 공식 표기 입력도 동일 코드로 조회되도록 함. 인코딩은 UTF-8(BOM)·CP949·EUC-KR 자동 감지로 확장.
- KCD 표준 코드 마스터 인프라 구축(`feat/kcd-master`): 보험 계산의 "공통 언어"(진료 코드 판정)를 하드코딩에서 공식 표준 분류 기반으로 전환하기 위한 기반 작업.
  - 신설: `kcd_codes` 테이블(`src/claim_service/db/tables.py`) — 코드·대분류·분류단계·한글명·영문명·출처버전·`verified`
  - 신설: `src/claim_service/domain/kcd.py` — KCD 코드 정규화·단계 분류·prefix 검증 헬퍼
  - 추가: `PolicyRepository.upsert_kcd_codes/get_kcd_codes/count_kcd_codes/clear_kcd_codes`
  - 신설: `scripts/load_kcd.py` — 인코딩 자동 감지·헤더 자동 감지·`--replace`·`--verify-rule-configs`(catalog KCD 참조 대조) 지원. 적재된 `kcd_codes`는 SQLite(`*.db`)로 커밋 제외.
  - 신설: `tests/test_kcd.py` — 코드 파싱·리포지토리·catalog KCD 참조 검증
- 데이터 조사 결과(검증된 사실): KCD(한국표준질병·사인분류) 전체 코드는 통계청 표준분류/KOICD(엑셀 다운로드)와 HIRA 상병마스터(공공데이터포털 파일)로 공개 제공됨(대분류 22·소분류 2,093·세분류 12,603·세세분류 6,335 등). 자동 다운로드 API는 로그인/키가 필요하고 GitHub 공개 데이터셋은 없어, 원본 파일은 공식 사이트에서 수동 다운로드 후 적재함.
- **개인 특약의 약관 규칙 귀속(③, `feat/kcd-master`)**: 특약별 `rule_config_override`(증권/약관에서 확인한 지급 요건)를 도입. `RiderIn/RiderOut/RiderResolve`와 `user_policy_riders`에 반영하고, `evaluate_claim`이 증권(`POLICY_CERTIFICATE`) 특약의 override를 표준 규칙 `rule_config`보다 우선해 계산함(검증 게이트는 증권 근거로 통과, 결과 basis에 "특약의 증권/약관에서 확인한 지급 요건 기준" 표기). USER_STATED 특약은 override가 있어도 Fail-Closed 유지. MCP `resolve_user_rider`에 `rule_config_override` 파라미터 추가.
- 검증: `pytest -q` 66 passed, `ruff check src tests scripts` 통과, `mypy src` 27개 파일 통과(신규 로더는 `MYPYPATH=src` 하에서 통과).
- **담보 규칙 리팩터링(②, `feat/kcd-master`)**: `rider_rules.py`의 KCD 판정을 하드코딩 문자열 매칭(`startswith`)에서 `domain.kcd.match_kcd_code` 기반으로 교체. 점 유무(`S72.0`/`S720`)와 무관하게 동일 판정하고, 제외 코드(치아파절 `S02.5`)가 우선 적용됨. 실제 마스터(21,299코드)와 연계 스모크 검증 완료(골절·화상·독감 판정 정상, 치아파절 제외 정상).
- 미커밋 일회성 파일 4개 삭제: 운영 DB 정리 일회성 스크립트(`scripts/prune_users.py`, `scripts/review_accounts.py`)와 아키텍처 인포그래픽(html/png) 2개. 모두 git에 추적되지 않던 파일로, 사용자 결정에 따라 삭제함. Git 히스토리 변경 없음.
- 삭제 후 `git status --short --branch` 상 추적되지 않은 파일 없음. 작업 트리 깨끗함(`main...origin/main` 동기화 상태 유지).

## 최신 진행 상황 (2026-10-23)

- **인증 방식 전환(사용자별 전용 키)**: 공용 `API_KEY` 인증을 제거하고, 사용자별 키(`X-User-Key` 또는 `Bearer`)로 MCP HTTP를 인증하도록 변경함. 유효한 키는 요청을 소유 사용자에게 귀속시키고 해당 계정의 PIN 입력을 대체함.
- DB: `user_api_keys` 테이블(`key_id`, `user_id`, `key_hash` SHA-256, `key_prefix`, `note`, `created_at`, `last_used_at`, `revoked_at`) 추가. 원문 키는 발급 시 1회만 표시하고 서버에는 SHA-256 해시만 저장함.
- 운영자 CLI: `scripts/manage_user_keys.py`의 `issue`/`list`/`revoke`. `list`는 key_id·prefix·상태(사용 중/폐기됨)만 표시하며 원문·해시는 노출하지 않음.
- 공용 키 회전 도구 정리: `scripts/rotate_api_key.py`, `tests/test_rotate_api_key.py`, `docs/api-key-rotation.md` 제거. `docs/user-api-keys.md` 신규 추가.
- 배포/로컬 설정: `.github/workflows/deploy-cloudrun.yml`에서 `API_KEY` Secret 주입 제거, `docker-compose.yml`에서 `API_KEY` 환경변수 제거. `config.py`의 `api_key` 설정 제거.
- 문서 갱신: `README.md`, `docs/mcp-client-setup.md`, `docs/agent-connect-prompt.md`, `docs/deployment.md`.
- 테스트: `tests/test_user_api_keys.py` 신규(해시만 저장, 키→소유자 해석, PIN 대체, 폐기, 목록 비노출, 미존재 사용자 발급 거부). `tests/test_deploy.py`를 사용자 키 인증 기준으로 재작성.
- **검증(실행 결과)**: `pytest -q` 43 passed, `ruff check src tests scripts` 통과, `mypy src` 26개 파일 통과. 운영자 CLI는 임시 SQLite에서 발급→목록→폐기→상태 표시를 실제 실행해 확인함.
- 브랜치: `feat/per-user-api-keys-v2`.
- 설치 매뉴얼: `docs/setup.md` 신규(요구 사항, venv·pip 실패 유형별 복구, 시스템 파이썬 대안, 검증 명령, 플랫폼 참고), `README.md`에서 링크, `requirements.lock.txt`의 UTF-8 BOM 제거.
- 로컬 환경 참고: 프로젝트 `.venv`가 pip 없이 생성되어(`pip._vendor` 누락) 사용할 수 없어, 시스템 파이썬(`C:\Python312`, pip 26.2, 사용자 site-packages)에 잠금 의존성을 설치해 검증함. 운영 배포는 실행하지 않음.
- **운영 DB 레거시 스키마 마이그레이션**: 운영 DB에 2026-10-17 사용자별 키 구현 당시의 `user_api_keys`(`token_hash`, `key_prefix` 등 없음, 행 0개)가 남아 있어 `column key_prefix does not exist` 오류가 발생함. `metadata.create_all`은 기존 테이블을 건너뛰므로 `init_schema()`에 `token_hash → key_hash` 이름 변경과 `key_prefix`/`note`/`last_used_at`/`revoked_at` 추가 마이그레이션을 구현함(기존 행 보존, 테이블 삭제 없음). 마이그레이션 테스트를 추가함.
- **운영 DB 적용 결과(실행)**: 마이그레이션 적용 후 컬럼이 `key_id,user_id,key_hash,created_at,key_prefix,note,last_used_at,revoked_at`로 확인됨. `shj` 사용자에게 키 1건을 발급하고 해시 조회로 소유자 귀속을 확인함. 키 원문은 이 문서에 기록하지 않음.
- **배포(실행 결과)**: PR #1 병합(`98f3d29`) 후 `main` CI 통과, `Deploy to Cloud Run` 워크플로가 이미지 빌드·푸시·배포·스모크 검증까지 모두 success. 배포 버전 `/api/version` = `98f3d2998d3a6bbcc1f22a2fdce6eb4afc019ccd`.
- **원격 인증 검증(실행 결과)**: 키 없는 `/mcp` 401, 잘못된 키 401, 유효 키로 `initialize` 200, PIN 보호 계정(`shj`)을 **PIN 없이** `get_user_profile` 호출해 200(키가 PIN을 대체함), 키 소유자와 다른 `X-User-Id` 요청 401.

## 최신 진행 상황 (2026-10-22)

- MCP 전용 정리: 보험 업무 인터페이스를 FastMCP Streamable HTTP(`/mcp`)와 로컬 stdio로 한정하고, Cloud Run 운영 확인용 `/api/health`, `/api/version`만 유지함. OpenAPI·일반 웹 안내·REST 업무 API는 비활성화함.
- `/ai/*`, `/u/*` 웹 브리지, REST 라우터, 소개/시작 안내 생성 코드와 이에 종속된 테스트를 제거함. 샘플 사용자 자동 시드도 제거하고 표준 규칙 시드만 유지함.
- MCP 연결 가이드를 재작성하고 CI/배포 스모크 검사를 MCP 초기화 및 운영 상태 경로 기준으로 변경함. REST·웹 경로 제거, MCP 키 인증, 도구/리소스/프롬프트, 사용자 등록 플로우 회귀 테스트를 추가함.
- 배포 시 앱 시작 과정에서 기존 `init_runtime()`이 스키마 생성/추가형 마이그레이션과 표준 규칙 시드를 수행함. 운영 사용자·보험 레코드는 수정·삭제하지 않으며, 과거 샘플 레코드도 보존함.
- 검증: 전체 `pytest -q` 39 passed, `ruff check src tests scripts` 통과, `mypy src` 26개 파일 통과, `git diff --check` 통과.

## 최신 진행 상황 (2026-10-20)

- 스마트폰 무료 AI 앱 개인화 웹 브릿지(`/ai/*`) 추가: MCP나 Custom GPT 설정이 없는 스마트폰 기본 AI 앱(무료 ChatGPT 앱, Gemini 앱, Claude 모바일 앱 등)에서도 내장 웹 읽기(GET) 기능만으로 공통 DB(`user_id` + `pin`)에 접근해 개인화 온보딩(`/ai/onboard`), 보험증권 사진 판독 후 등록/갱신(`/ai/register-policy`), 미매핑 특약 확정(`/ai/resolve-rider`), 등록 보험 조회/삭제(`/ai/policies`, `/ai/delete-policy`), 병원 영수증 기반 예상 보험금 계산(`/ai/evaluate`)을 수행할 수 있도록 `src/claim_service/api/ai_bridge.py` 및 `/start`(`src/claim_service/start_guide.py`)를 구현함.
- 모바일 ChatGPT 웹 리더(`ChatGPT-User`, `OAI-SearchBot`) 호환성 및 단일 조회(`/u/{user_id}/{pin}`) 보완: `/robots.txt` 및 `/favicon.ico`를 공개 경로로 열어 크롤러 401 차단을 해제하고, AI 웹 리더가 `/start.md` 또는 `/ai/*`를 열 때 `text/markdown`·`application/json` 대신 `text/html` 페이지로 응답하도록 보완함. 또한 모바일 ChatGPT의 URL 샌드박스(AI가 임의 조합한 URL 호출 차단)에서도 한 번의 접속만으로 사용자 프로필·등록 보험 전체 목록·표준 규칙을 즉시 읽을 수 있도록 `/u/{user_id}/{pin}`(및 `/start?user_id=...&pin=...`) 단일 조회 경로를 추가함.
- 보안 및 도배(Spam) 방어 강화: `/ai/*` 및 `/u/*` 경로는 4~32자 PIN 입력을 강제하며, PIN이 설정되지 않은 기존 계정(예: `user_123`)의 접근을 차단(HTTP 403)하고, 계정별 연속 5회 PIN 오입력 시 5분간 요청을 차단(HTTP 429)함. 또한 공개 커뮤니티 유입 시 악성 스크립트 도배를 막기 위해 IP당 5분 내 쓰기 요청 제한(20회), 전역 신규 계정 생성 제한(5분당 60개), 계정당 최대 보험 등록 건수 제한(20건)을 적용함.
- 한국신용정보원 본인신용정보 열람서비스(`credit4u.or.kr`) 상세내역 확보 경로 추가: `document_guide.py`, `onboarding.py`, `start_guide.py`, `intro.py`, `mcp/server.py`에 `credit4u.or.kr > 보험신용정보 > 정액형·실손형보험 > 상세내역 발급(보장구분·보장명·보장금액 표)` 안내 및 브라우저 제어 AI용 수집 지침을 추가함.
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
