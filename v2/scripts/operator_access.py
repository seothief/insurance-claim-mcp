"""Interactive V2-only operator login and read-only access checks.

Run login in a real terminal. Never paste OAuth codes, API keys or credential files into chat.
This helper does not create cloud resources, change IAM, or modify the default CLI credentials.
"""

import argparse
import getpass
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPOSITORY = "seothief/insurance-claim-mcp"
CONFIG_ROOT = Path.home() / ".config" / "insurance-claim-v2"
SETTINGS_FILE = CONFIG_ROOT / "operator-access.json"
PERMISSIONS = [
    "resourcemanager.projects.get",
    "serviceusage.services.enable", "serviceusage.services.get", "serviceusage.services.use",
    "run.services.get", "run.services.list", "run.services.create", "run.services.update",
    "run.services.getIamPolicy", "run.services.setIamPolicy",
    "run.jobs.get", "run.jobs.create", "run.jobs.update", "run.jobs.run",
    "run.jobs.getIamPolicy", "run.jobs.setIamPolicy",
    "artifactregistry.repositories.get", "artifactregistry.repositories.create",
    "artifactregistry.repositories.getIamPolicy", "artifactregistry.repositories.setIamPolicy",
    "iam.serviceAccounts.get", "iam.serviceAccounts.create", "iam.serviceAccounts.actAs",
    "iam.serviceAccounts.getIamPolicy", "iam.serviceAccounts.setIamPolicy",
    "iam.workloadIdentityPools.get", "iam.workloadIdentityPools.create",
    "iam.workloadIdentityPoolProviders.get", "iam.workloadIdentityPoolProviders.create",
    "iam.workloadIdentityPoolProviders.update",
    "secretmanager.secrets.get", "secretmanager.secrets.create",
    "secretmanager.secrets.getIamPolicy", "secretmanager.secrets.setIamPolicy",
    "secretmanager.versions.add", "secretmanager.versions.access", "secretmanager.versions.list",
]
OVERRIDES = [
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE", "CLOUDSDK_AUTH_ACCESS_TOKEN",
    "CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT", "CLOUDSDK_CORE_ACCOUNT",
    "GOOGLE_APPLICATION_CREDENTIALS", "GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN",
    "GITHUB_ENTERPRISE_TOKEN", "GH_DEBUG", "CLOUDSDK_CORE_LOG_HTTP",
    "NEON_API_KEY",
]


def private_path(path: Path, directory: bool = False) -> None:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError("V2 credentials must be owned by this user and not be symlinks")
    expected = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not expected or info.st_mode & 0o077:
        raise ValueError("V2 credential directory/files must be private (0700/0600)")


def load_settings() -> dict[str, str]:
    private_path(CONFIG_ROOT, directory=True)
    private_path(SETTINGS_FILE)
    data = json.loads(SETTINGS_FILE.read_text())
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", data["V2_GCP_PROJECT_ID"]):
        raise ValueError("Invalid V2 project ID")
    if data["CLOUDSDK_CONFIG"] != str(CONFIG_ROOT / "gcloud"):
        raise ValueError("Default GCP credential directory is not allowed")
    if data["GH_CONFIG_DIR"] != str(CONFIG_ROOT / "github"):
        raise ValueError("Default GitHub credential directory is not allowed")
    if data["GIT_CONFIG_GLOBAL"] != str(CONFIG_ROOT / "gitconfig"):
        raise ValueError("Default global Git configuration is not allowed")
    for name in ["gcloud", "github"]:
        private_path(CONFIG_ROOT / name, directory=True)
    return data


def operator_environment(settings: dict[str, str]) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in OVERRIDES}
    env.update({key: settings[key] for key in [
        "V2_GCP_PROJECT_ID", "V2_GCP_REGION", "CLOUDSDK_CONFIG", "GH_CONFIG_DIR",
        "GIT_CONFIG_GLOBAL",
    ]})
    if settings.get("NEON_API_KEY"):
        env["NEON_API_KEY"] = settings["NEON_API_KEY"]
    if settings.get("NEON_ORG_ID"):
        env["NEON_ORG_ID"] = settings["NEON_ORG_ID"]
    # Never let gh fall back to a global keyring, including before token input is complete.
    env["GH_TOKEN"] = settings.get("GH_TOKEN") or "v2-unconfigured-token"
    env["CLOUDSDK_CORE_PROJECT"] = settings["V2_GCP_PROJECT_ID"]
    env["GH_HOST"] = "github.com"
    env["GH_PROMPT_DISABLED"] = "1"
    env["CLOUDSDK_CORE_DISABLE_USAGE_REPORTING"] = "true"
    return env


def save_settings(settings: dict[str, str]) -> None:
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=CONFIG_ROOT, delete=False) as handle:
            name = handle.name
            os.chmod(name, 0o600)
            json.dump(settings, handle)
        os.replace(name, SETTINGS_FILE)
        name = None
    finally:
        if name is not None:
            Path(name).unlink(missing_ok=True)


def capture(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, env=env, capture_output=True, text=True, timeout=90)


def api_json(url: str, token: str, payload: dict | None = None) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def check(settings: dict[str, str]) -> bool:
    env = operator_environment(settings)
    okay = True
    project = settings["V2_GCP_PROJECT_ID"]
    print("V2 GCP project:", project)
    token = capture(["gcloud", "auth", "print-access-token"], env)
    if token.returncode != 0 or not token.stdout.strip():
        print("GCP: login required in the dedicated V2 configuration")
        okay = False
    else:
        try:
            result = api_json(
                f"https://cloudresourcemanager.googleapis.com/v1/projects/{project}:testIamPermissions",
                token.stdout.strip(), {"permissions": PERMISSIONS},
            )
            missing = sorted(set(PERMISSIONS) - set(result.get("permissions", [])))
            if missing:
                print("GCP: missing bootstrap permissions:")
                for permission in missing:
                    print("  " + permission)
                okay = False
            else:
                print("GCP: requested bootstrap permissions allowed (resources not created)")
        except urllib.error.HTTPError as exc:
            print("GCP: permission/scope check failed; HTTP", exc.code)
            okay = False
        except Exception:
            print("GCP: read-only permission check failed; sensitive output suppressed")
            okay = False
    try:
        query = {"limit": "1"}
        if settings.get("NEON_ORG_ID"):
            query["org_id"] = settings["NEON_ORG_ID"]
        api_json("https://console.neon.tech/api/v2/projects?" + urllib.parse.urlencode(query),
                 settings["NEON_API_KEY"])
        print("Neon: read API accepted (project creation not yet tested)")
    except Exception:
        print("Neon: API key missing, rejected, or network unavailable")
        okay = False
    result = capture([
        settings["GH_BIN"], "api", f"repos/{REPOSITORY}",
        "--jq", ".permissions | {admin, push}",
    ], env)
    try:
        permissions = json.loads(result.stdout) if result.returncode == 0 else {}
    except Exception:
        permissions = {}
    if permissions.get("admin") and permissions.get("push"):
        print("GitHub: repository admin/push access confirmed")
    else:
        print("GitHub: repository admin/push access required; login/configuration incomplete")
        okay = False
    if settings.get("GH_TOKEN", "").startswith("github_pat_"):
        # Fine-grained tokens do not expose OAuth scopes. These reads catch common omissions;
        # actual write permission is verified by each subsequent V2-only setup operation.
        for path in ["actions/variables", "actions/secrets/public-key", "actions/workflows"]:
            result = capture([settings["GH_BIN"], "api", f"repos/{REPOSITORY}/{path}"], env)
            if result.returncode != 0:
                print("GitHub: fine-grained repository permission missing for", path)
                okay = False
        print("GitHub: fine-grained write permissions must be verified during V2 setup")
    else:
        scopes = capture([settings["GH_BIN"], "api", "--include", "user"], env)
        header = next((line for line in scopes.stdout.splitlines()
                       if line.lower().startswith("x-oauth-scopes:")), "")
        granted = {part.strip() for part in header.partition(":")[2].split(",")}
        if scopes.returncode != 0 or not {"repo", "workflow"} <= granted:
            print("GitHub: classic token requires repo/workflow scopes")
            okay = False
        else:
            print("GitHub: classic repo/workflow scopes confirmed")
    print("No resources, IAM policies, branches or deployments were changed by this check")
    return okay


def login(project: str, region: str, gh_bin: str) -> bool:
    if not sys.stdin.isatty():
        raise ValueError("Run login in a real terminal; never supply credentials through chat")
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project):
        raise ValueError("Invalid GCP project ID")
    if not re.fullmatch(r"[a-z]+-[a-z]+[0-9]", region):
        raise ValueError("Invalid GCP region")
    if not shutil.which("gcloud") or not Path(gh_bin).is_file():
        raise ValueError("gcloud and the prepared GitHub CLI are required")
    os.umask(0o077)
    CONFIG_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    private_path(CONFIG_ROOT, directory=True)
    for name in ["gcloud", "github"]:
        directory = CONFIG_ROOT / name
        directory.mkdir(mode=0o700, exist_ok=True)
        private_path(directory, directory=True)
    for path in [CONFIG_ROOT / "gitconfig", CONFIG_ROOT / "github/hosts.yml",
                 CONFIG_ROOT / "github/config.yml"]:
        if path.exists() or path.is_symlink():
            private_path(path)
    previous = load_settings() if SETTINGS_FILE.exists() else {}
    settings = {
        "V2_GCP_PROJECT_ID": project, "V2_GCP_REGION": region,
        "CLOUDSDK_CONFIG": str(CONFIG_ROOT / "gcloud"),
        "GH_CONFIG_DIR": str(CONFIG_ROOT / "github"),
        "GIT_CONFIG_GLOBAL": str(CONFIG_ROOT / "gitconfig"),
        "GH_BIN": str(Path(gh_bin).resolve()),
    }
    env = operator_environment(settings)
    print("V2 login only: default CLI credentials and V1 settings will not be changed.")
    print("Credentials are kept in the private V2 directory (0700, files 0600).")
    print("Neon/GitHub keys are stored locally, not encrypted by this helper.")
    print("1/3 Google login: choose an account allowed to configure the selected project.")
    result = subprocess.run(["gcloud", "auth", "login", "--no-launch-browser"], env=env)
    if result.returncode != 0:
        raise ValueError("Google login was not completed")
    print("2/3 GitHub: create a temporary fine-grained personal access token in the browser.")
    print("https://github.com/settings/personal-access-tokens/new")
    print("Select ONLY seothief/insurance-claim-mcp; recommended expiration: 7 days.")
    print("Repository permissions: Actions, Administration, Contents, Environments,")
    print("Secrets and Variables: read/write; Workflows: write.")
    print("Alternatively use a 7-day classic token with repo/workflow scopes.")
    prompt = "GitHub token (hidden; Enter keeps previous token): " if previous.get(
        "GH_TOKEN",
    ) else "GitHub token (hidden): "
    github_token = getpass.getpass(prompt) or previous.get("GH_TOKEN", "")
    if not github_token or len(github_token) > 4096 or any(c.isspace() for c in github_token):
        raise ValueError("A GitHub token is required")
    settings["GH_TOKEN"] = github_token
    print("3/3 Neon: create a temporary API key in https://console.neon.tech/app/settings/api-keys")
    print("Use an account key that can create a new project; never send it in chat.")
    prompt = "Neon API key (hidden; Enter keeps previous key): " if previous.get(
        "NEON_API_KEY",
    ) else "Neon API key (hidden): "
    value = getpass.getpass(prompt) or previous.get("NEON_API_KEY", "")
    if not value or len(value) > 4096 or any(char.isspace() for char in value):
        raise ValueError("A non-empty Neon API key is required")
    settings["NEON_API_KEY"] = value
    save_settings(settings)
    print("V2-only operator access saved. Checking access without creating resources...")
    return check(settings)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("login")
    setup.add_argument("--project", required=True)
    setup.add_argument("--region", default="asia-northeast3")
    setup.add_argument("--gh-bin", default=str(Path.home() / ".cache/v2-tools/gh"))
    sub.add_parser("check")
    args = parser.parse_args()
    try:
        okay = login(args.project, args.region, args.gh_bin) if args.command == "login" else check(
            load_settings(),
        )
        return 0 if okay else 1
    except (Exception, KeyboardInterrupt):
        print("V2 setup incomplete; details suppressed. Retry in your terminal.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
