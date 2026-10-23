# 사용자별 API/MCP 키 (운영자 전용)

각 사용자는 `/mcp` 요청을 인증하는 전용 키를 가집니다. 키는 `X-User-Key` 헤더(또는 `Bearer`)로 보내며,
서버는 이 키로 요청을 소유 사용자에게 귀속시킵니다. 성공한 키 인증은 해당 계정의 PIN 입력을 대체합니다.

- 서버에는 SHA-256 해시만 저장됩니다. 원문 키를 운영자가 다시 조회할 수 없습니다.
- 원문 키는 **발급 시 한 번만** 출력됩니다. 즉시 안전한 비밀 전달 경로로 소유자에게 보내세요.
- 키는 만료되지 않습니다. 사용하지 않게 되면 명시적으로 폐기합니다.
- 이전 공용 `API_KEY`(Secret Manager) 인증은 제거되었습니다. 배포/컴포즈에서 `API_KEY`를 더 이상 참조하지 않습니다.

## 발급

저장소 루트에서 프로젝트 가상환경으로 실행합니다. DB는 `DATABASE_URL` 또는 `--database-url`로 지정합니다.

```powershell
# 운영 DB(Neon 등)를 가리킬 때
$env:DATABASE_URL = "postgresql+psycopg://..."   # 예시
.\\.venv\\Scripts\\python.exe scripts\\manage_user_keys.py issue --user-id <별명>
```

결과 예시:

```
사용자 'my_alias'에게 키를 발급했습니다 (key_id: ...)
새 키 (이번에만 표시; 안전한 비밀 전달 경로로 보내세요):
<raw_key>
서버에는 SHA-256 해시만 저장됩니다.
```

발급 대상 사용자가 아직 DB에 없으면 먼저 MCP `register_user`로 등록해야 합니다.

## 목록

```powershell
.\\.venv\\Scripts\\python.exe scripts\\manage_user_keys.py list --user-id <별명>
```

key_id와 접두어(prefix)만 표시합니다. 원문 키는 절대 표시하지 않습니다.

## 폐기

```powershell
.\\.venv\\Scripts\\python.exe scripts\\manage_user_keys.py revoke --user-id <별명> --key-id <key_id>
```

폐기한 키는 즉시 무효화되며 이전 상태로 되돌릴 수 없습니다. 재발급이 필요하면 새 키를 발급하세요.

## 연동 예시 (MCP 클라이언트 설정)

```json
{
  "mcpServers": {
    "insurance-claim": {
      "url": "https://insurance-claim-mcp-...-run.app/mcp",
      "type": "streamableHttp",
      "headers": {
        "X-User-Key": "<발급받은 키>",
        "X-User-Id": "<별명>"
      }
    }
  }
}
```

`X-User-Id`는 권장이지만 필수는 아닙니다. 헤더로 보낸 `X-User-Id`가 키 소유자와 다르면 요청은 거부됩니다.

## 보안 주의

- 원문 키를 대화, 로그, 소스 코드, 이슈 또는 공개 문서에 넣지 마세요.
- 키 발급 후에는 운영자의 비밀 저장소에만 보관하고 소유자에게 승인된 채널로 전달합니다.
- 계정이 공유되는 환경에서 키는 그 사용자 본인만 사용해야 합니다.
