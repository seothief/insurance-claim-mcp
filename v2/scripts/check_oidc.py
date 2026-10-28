"""Preflight only: GCP, not this decoder, validates the actual JWT signature and audience."""

import base64
import json
import os
import sys
import urllib.parse
import urllib.request


class RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        # Never forward GitHub's request credential to another location.
        return None


def decode_claims(token: str) -> dict:
    part = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def validate_claims(claims: dict) -> None:
    expected = {
        "repository": "seothief/insurance-claim-mcp",
        "ref": "refs/heads/v2",
        "environment": "v2-production",
    }
    if any(claims.get(key) != value for key, value in expected.items()):
        raise ValueError("Unexpected V2 workflow identity")


def main() -> int:
    try:
        url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or not (parts.hostname or "").endswith(
            ".actions.githubusercontent.com",
        ):
            raise ValueError("Unexpected GitHub OIDC endpoint")
        query = dict(urllib.parse.parse_qsl(parts.query))
        query["audience"] = "https://iam.googleapis.com/" + os.environ["V2_IDENTITY_PROVIDER"]
        url = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))
        request = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"],
        })
        opener = urllib.request.build_opener(RejectRedirect())
        with opener.open(request, timeout=30) as response:
            payload = json.loads(response.read(1024 * 1024))
        claims = decode_claims(payload["value"])
        for name in ["repository", "ref", "environment", "sub"]:
            value = claims.get(name)
            print("OIDC " + name + ":", value[:300] if isinstance(value, str) else "<missing>")
        validate_claims(claims)
        print("V2 deployment identity claims accepted; raw token never logged")
        return 0
    except Exception:
        print("V2 OIDC preflight failed; credentials and token suppressed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
