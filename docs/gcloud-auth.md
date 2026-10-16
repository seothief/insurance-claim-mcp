# Google Cloud 인증 (Windows)

로컬 개발에서는 개인 Google 계정의 `gcloud` 로그인과 Application Default Credentials(ADC)를 각각 한 번 설정합니다. 토큰은 Google Cloud CLI의 사용자 프로필에 저장되며 CLI가 필요할 때 자동 갱신합니다. 저장된 로그인은 로그아웃·폐기되거나 조직 정책상 재인증이 요구되기 전까지 보통 매번 다시 입력할 필요가 없습니다.

## 1회 설정

PowerShell에서 저장소 폴더로 이동한 뒤, `gcloud.ps1`이 실행 정책에 막히는 Windows 환경을 고려해 `gcloud.cmd`를 사용합니다.

```powershell
gcloud.cmd auth login
gcloud.cmd config set project project-93d02748-0cbc-4596-902
gcloud.cmd auth application-default login
gcloud.cmd auth application-default set-quota-project project-93d02748-0cbc-4596-902
```

각 로그인 명령에서 브라우저가 열립니다. 적절한 Google 계정을 선택하고 권한 동의를 완료하세요. ADC quota project 설정은 계정에 해당 프로젝트의 서비스 사용 권한이 있어야 할 수 있습니다. 권한 오류가 나면 이 설정만 건너뛰고 프로젝트 관리자가 `serviceusage.services.use` 권한을 확인하도록 요청하세요.

> `gcloud auth login`은 gcloud CLI 명령에, `gcloud auth application-default login`은 Python 앱과 `scripts/monitor.py` 같은 로컬 프로그램에 사용됩니다. 둘은 서로 대체하지 않습니다. 서비스 계정 키 JSON은 만들거나 저장소에 추가하지 마세요.

## 매번 개발 시작할 때

저장소 루트에서 인증 상태만 확인합니다. 이 검사는 계정 이메일, 액세스 토큰, 시크릿 값을 출력하지 않습니다.

```powershell
.\.venv\Scripts\python.exe scripts\check_gcloud_auth.py
```

필요하면 모니터를 실행합니다.

```powershell
.\.venv\Scripts\python.exe scripts\monitor.py
```

합성 샘플 데이터 검토 도구는 제한된 표식·건수만 읽기 전용으로 확인합니다.
삭제 도구는 별도 승인이 없는 한 `--delete` 옵션 없이 미리 보기로만 실행하세요.

인증이 만료·폐기된 경우에만 안내된 로그인 명령을 다시 실행하면 됩니다. 조직의 세션 정책, 비밀번호 변경, 계정 보안 조치, refresh token 폐기 등은 재로그인을 요구할 수 있습니다.

## 보안 및 권한

- gcloud 사용자 설정과 ADC는 저장소 바깥의 사용자 프로필에 저장됩니다. `.env`, 토큰, 자격 증명 JSON을 커밋하지 마세요.
- `monitor.py`와 샘플 검토 스크립트는 공용 `scripts/gcp_secrets.py`를 통해 Secret Manager의 `DATABASE_URL`을 조회합니다. 모니터는 추가로 Cloud Logging을 읽습니다. 필요한 권한은 Secret Manager secret accessor와 로그 조회 권한입니다.
- `monitor.py`의 DB 조회는 `SELECT`만 수행하지만, `DATABASE_URL`에 쓰기 권한이 있는 DB 계정 정보가 Secret Manager에 저장되어 있습니다. 이 도구에서는 DB 변경 쿼리를 실행하지 않습니다.
- 인증 문제가 계속되면 프로젝트 ID와 현재 계정의 프로젝트 접근 권한을 관리자에게 확인하세요. 액세스 토큰이나 `DATABASE_URL`을 채팅·로그에 붙여 넣지 마세요.