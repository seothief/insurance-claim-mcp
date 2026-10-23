# GitHub Actions → Cloud Run 배포 설정

## 실행 방식

- `main`에 대한 CI가 성공하면 배포 워크플로가 자동 실행됩니다.
- Actions의 **Deploy to Cloud Run → Run workflow**에서 `main`을 선택하면 한 번 실행으로 수동 배포할 수 있습니다.
- 배포는 `main`만 허용하고, 이미지 태그는 해당 커밋 SHA입니다.
- 빌드·배포 후 `/api/health`, `/api/version`을 검사합니다. 이 경로는 Cloud Run 운영 상태 확인용이며 인증 없이 접근할 수 있습니다.
- `APP_VERSION`은 최신 배포값으로 갱신합니다. DATABASE_URL과 그 밖의 기존 서비스 설정은 보존합니다. 공용 `API_KEY` Secret은 더 이상 사용하지 않습니다.

## GitHub 저장소 설정

저장소의 **Settings → Secrets and variables → Actions**에서 아래를 설정합니다.

| 종류 | 이름 | 값 |
| --- | --- | --- |
| Variable | `GCP_PROJECT_ID` | 대상 Google Cloud 프로젝트 ID |
| Variable | `GCP_REGION` | Cloud Run 및 Artifact Registry 리전 (예: `asia-northeast3`) |
| Variable | `GAR_REPOSITORY` | 해당 리전에 만든 Artifact Registry Docker 저장소 이름 |
| Secret | `GCP_WORKLOAD_IDENTITY_PROVIDER` | 전체 Workload Identity Provider 리소스 이름 |
| Secret | `GCP_SERVICE_ACCOUNT` | GitHub Actions가 가장할 배포 서비스 계정 이메일 |

서비스 계정 키 JSON은 만들지 않습니다. Workload Identity Federation의 provider 조건은
이 저장소의 GitHub 조직/소유자와 `main` 브랜치를 제한하고, IAM binding은 해당 provider의
principalSet에만 배포 서비스 계정을 가장하도록 부여합니다. 배포 계정에는 이미지 빌드·푸시와
Cloud Run 배포에 필요한 최소 권한을 부여하세요. Artifact Registry 저장소와 API는 사전에
생성·활성화되어 있어야 합니다.

Cloud Run **실행 서비스 계정**에는 `DATABASE_URL` Secret Manager 버전에 대한
Secret Accessor 권한이 필요합니다. 해당 Secret과 기존 Cloud Run 서비스
`insurance-claim-mcp`도 배포 전에 준비해야 합니다. 배포 워크플로는 비밀 값을 GitHub에
복사하지 않고 기존 Secret Manager 연결을 사용합니다. 인증은 사용자별 API 키([사용자별 API/MCP 키](user-api-keys.md))로
처리하므로 공용 `API_KEY` Secret은 필요하지 않습니다.

## 점검

먼저 CI를 통과한 `main` 커밋을 확인한 뒤 수동 워크플로를 실행합니다. 배포 단계가 실패하면
Actions 로그에서 실패한 단계와 권한/변수 이름을 확인하되 토큰, API 키, DB URL은 로그에
붙여 넣지 마세요. 성공 시 마지막 스모크 테스트가 새 커밋 버전을 확인합니다.