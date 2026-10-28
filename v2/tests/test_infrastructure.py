import importlib.util
import json
import os
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "v2"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, V2 / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workflow(name: str) -> dict:
    # YAML 1.1 safe_load treats the GitHub key `on` as a boolean.
    return yaml.load((ROOT / ".github" / "workflows" / name).read_text(), Loader=yaml.BaseLoader)


def test_release_is_branch_and_environment_isolated() -> None:
    release = workflow("deploy-v2.yml")
    assert release["on"]["push"]["branches"] == ["v2"]
    assert "workflow_run" not in release["on"]
    assert release["concurrency"]["cancel-in-progress"] == "false"
    assert release["jobs"]["deploy"]["environment"] == "v2-production"
    assert release["jobs"]["deploy"]["needs"] == "ci"
    for name in ["ci", "deploy"]:
        assert release["jobs"][name]["if"] == "github.ref == 'refs/heads/v2'"
    raw = (ROOT / ".github/workflows/deploy-v2.yml").read_text()
    assert "${{ vars.GCP_" not in raw
    assert "${{ secrets.GCP_" not in raw
    assert "docker build -f v2/Dockerfile" in raw


def test_v2_container_compose_and_source_are_independent() -> None:
    compose = yaml.load((V2 / "compose.yml").read_text(), Loader=yaml.BaseLoader)
    assert compose["name"] == "insurance-claim-v2"
    assert "pgdata-v2" in compose["volumes"]
    assert "pgdata" not in compose["volumes"]
    assert compose["services"]["app-v2"]["ports"] == ["127.0.0.1:${V2_PORT:-8082}:8080"]
    docker = (V2 / "Dockerfile").read_text()
    assert "claim_mcp_v2.main:app" in docker and "claim_service.main" not in docker
    for source in (V2 / "src").rglob("*.py"):
        assert "from claim_service" not in source.read_text()
        assert "import claim_service" not in source.read_text()
    bootstrap = (V2 / "scripts/bootstrap-gcp.sh").read_text()
    assert "projects add-iam-policy-binding" not in bootstrap
    assert "refs/heads/v2" in bootstrap and "environment:v2-production" in bootstrap


def test_neon_uri_requires_v2_and_certificate_verification() -> None:
    script = load_script("provision_neon")
    result = script.verified_uri(
        "postgresql://user:secret@ep-example.region.aws.neon.tech/insurance_claim_v2?sslmode=require",
    )
    assert "sslmode=verify-full" in result and "ca-certificates.crt" in result
    for bad in [
        "postgresql://user:secret@ep-example.region.aws.neon.tech/neondb",
        "postgresql://user:secret@example.com/insurance_claim_v2",
    ]:
        with pytest.raises(ValueError):
            script.verified_uri(bad)


def test_neon_never_auto_creates_without_operator_flag(tmp_path: Path) -> None:
    script = load_script("provision_neon")

    class NeverCalled:
        def request(self, *args):
            raise AssertionError("Cloud API must not be called")

    with pytest.raises(ValueError, match="requires --create-project"):
        script.provision(NeverCalled(), tmp_path / "state.json", "project-v2", "region", False)


def test_neon_creation_records_private_resume_state_and_organization(tmp_path: Path) -> None:
    script = load_script("provision_neon")
    calls = []

    class StopAfterState(Exception):
        pass

    class FakeNeon:
        def request(self, method, path, body=None):
            calls.append((method, path, body))
            if method == "POST" and path == "/projects":
                return {"project": {"id": "new-v2-project", "name": script.PROJECT_NAME}}
            raise StopAfterState()

    state = tmp_path / "state.json"
    with pytest.raises(StopAfterState):
        script.provision(FakeNeon(), state, "project-v2", "region", True, "org-example-123")
    assert calls[0][2]["project"]["org_id"] == "org-example-123"
    assert json.loads(state.read_text())["project_id"] == "new-v2-project"
    assert state.stat().st_mode & 0o077 == 0


def test_neon_does_not_retry_project_creation_on_locked_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("provision_neon")
    calls = []

    def locked(request, **kwargs):
        calls.append(request)
        raise urllib.error.HTTPError(request.full_url, 423, "Locked", {}, None)

    monkeypatch.setattr(script.urllib.request, "urlopen", locked)
    with pytest.raises(urllib.error.HTTPError):
        script.Neon("synthetic-key").request("POST", "/projects", {"project": {}})
    assert len(calls) == 1


def test_neon_secret_is_sent_only_via_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script("provision_neon")
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "projects/p/secrets/s/versions/12\n", "")

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    uri = "postgresql://app:private@ep-v2.neon.tech/insurance_claim_v2"
    assert script.store_secret("project-v2", "insurance-claim-v2-database-url", uri) == "12"
    assert calls[0][1]["input"] == uri
    assert uri not in " ".join(calls[0][0])


def test_shell_scripts_parse_and_wrong_branch_never_calls_cloud(tmp_path: Path) -> None:
    for name in ["deploy.sh", "bootstrap-gcp.sh"]:
        subprocess.run(["bash", "-n", str(V2 / "scripts" / name)], check=True)
    env = {**os.environ, "GITHUB_REF": "refs/heads/main", "PATH": str(tmp_path)}
    result = subprocess.run(["/bin/bash", str(V2 / "scripts/deploy.sh")], env=env,
                            capture_output=True, text=True)
    assert result.returncode != 0


def fake_cloud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail: str = "") -> Path:
    """Offline gcloud/python wrappers exercise the real release shell control flow."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.jsonl"
    gcloud = bin_dir / "gcloud"
    gcloud.write_text(f"#!{sys.executable}\n" + '''
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_CLOUD_LOG"], "a") as f:
    f.write(json.dumps(args) + "\\n")
if args[:3] == ["run", "services", "describe"]:
    if "--format=value(status.url)" in args:
        print("https://v2.example.test")
    else:
        print(json.dumps({"status": {"traffic": [
            {"revisionName": "insurance-claim-mcp-v2-old", "percent": 100},
            {"tag": "candidate-" + os.environ["GITHUB_RUN_ID"] + "-1",
             "url": "https://candidate.example.test"}
        ]}}))
if args[:3] == ["secrets", "versions", "access"]:
    print("icv2_" + "nonsecret-fake-probe-value"*2)
if args[:3] == ["run", "jobs", "execute"] and os.environ.get("FAKE_FAIL") == "migration":
    sys.exit(1)
''')
    wrapper = bin_dir / "python3"
    wrapper.write_text(f"#!{sys.executable}\n" + '''
import json, os, sys
if sys.argv[1].endswith("smoke.py"):
    with open(os.environ["FAKE_CLOUD_LOG"], "a") as f:
        f.write(json.dumps(["smoke"] + sys.argv[1:]) + "\\n")
    canonical = "https://v2.example.test" in sys.argv
    fail = os.environ.get("FAKE_FAIL")
    sys.exit(1 if (fail == "candidate" and not canonical) or
             (fail == "canonical" and canonical) else 0)
os.execv(sys.executable, [sys.executable] + sys.argv[1:])
''')
    gcloud.chmod(0o755)
    wrapper.chmod(0o755)
    env = {
        "PATH": str(bin_dir) + ":" + os.environ["PATH"], "FAKE_CLOUD_LOG": str(log),
        "FAKE_FAIL": fail, "GITHUB_REF": "refs/heads/v2", "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "100200", "GITHUB_RUN_ATTEMPT": "1",
        "V2_GCP_PROJECT_ID": "test-v2-project",
        "V2_GCP_REGION": "asia-northeast3", "V2_NEON_PROJECT_ID": "neon-v2-only",
        "V2_DATABASE_SECRET_VERSION": "1", "V2_MIGRATION_SECRET_VERSION": "2",
        "V2_SMOKE_SECRET_VERSION": "3",
        "V2_IMAGE": "asia-northeast3-docker.pkg.dev/test-v2-project/"
                    "insurance-claim-v2/server@sha256:" + "b" * 64,
    }
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return log


@pytest.mark.parametrize("failure", ["", "migration", "candidate", "canonical"])
def test_release_promotes_only_verified_v2_and_restores_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    log = fake_cloud(tmp_path, monkeypatch, failure)
    result = subprocess.run(["bash", str(V2 / "scripts/deploy.sh")], capture_output=True, text=True)
    assert result.returncode == (0 if not failure else 1), result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert all("insurance-claim-mcp" not in args for args in calls)
    for args in calls:
        if args[0] == "smoke":
            assert "--key-env" in args and "--expected-workspace" in args
            assert "nonsecret-fake-probe-value" not in " ".join(args)
    releases = [args for args in calls if args[:3] == ["run", "services", "update-traffic"]]
    if failure in {"migration", "candidate"}:
        assert not releases
    else:
        assert releases
    if failure == "canonical":
        assert "insurance-claim-mcp-v2-old=100" in releases[-1]
    deployments = [args for args in calls if args[:2] == ["run", "deploy"]]
    if deployments:
        assert "--no-traffic" in deployments[0]
        assert "insurance-claim-v2-database-url:1" in deployments[0][
            deployments[0].index("--set-secrets") + 1
        ]


def test_new_runs_of_same_commit_use_distinct_revisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    revisions = []
    for run_id in ["100201", "100202"]:
        directory = tmp_path / run_id
        directory.mkdir()
        log = fake_cloud(directory, monkeypatch)
        monkeypatch.setenv("GITHUB_RUN_ID", run_id)
        result = subprocess.run(["bash", str(V2 / "scripts/deploy.sh")], capture_output=True)
        assert result.returncode == 0, result.stderr
        for args in map(json.loads, log.read_text().splitlines()):
            if args[:2] == ["run", "deploy"]:
                revisions.append(args[args.index("--revision-suffix") + 1])
    assert len(revisions) == 2 and revisions[0] != revisions[1]


def test_operator_environment_isolates_credentials_and_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("operator_access")
    monkeypatch.setenv("GH_TOKEN", "do-not-reuse-existing-github-token")
    monkeypatch.setenv("CLOUDSDK_AUTH_ACCESS_TOKEN", "do-not-reuse-vm-access-token")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/original/adc.json")
    monkeypatch.setenv("GH_DEBUG", "api")
    settings = {
        "V2_GCP_PROJECT_ID": "v2-project-only", "V2_GCP_REGION": "asia-northeast3",
        "CLOUDSDK_CONFIG": str(tmp_path / "gcloud"),
        "GH_CONFIG_DIR": str(tmp_path / "github"), "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"),
        "NEON_API_KEY": "synthetic-neon-test-key",
        "GH_TOKEN": "synthetic-v2-only-token",
    }
    env = script.operator_environment(settings)
    for key in [
        "CLOUDSDK_AUTH_ACCESS_TOKEN", "GOOGLE_APPLICATION_CREDENTIALS", "GH_DEBUG",
    ]:
        assert key not in env
    assert env["CLOUDSDK_CONFIG"] == str(tmp_path / "gcloud")
    assert env["GIT_CONFIG_GLOBAL"] == str(tmp_path / "gitconfig")
    assert env["NEON_API_KEY"] == "synthetic-neon-test-key"
    assert env["GH_TOKEN"] == "synthetic-v2-only-token"
    assert os.environ["GH_TOKEN"] == "do-not-reuse-existing-github-token"


def test_operator_never_falls_back_to_github_keyring() -> None:
    script = load_script("operator_access")
    settings = {
        "V2_GCP_PROJECT_ID": "v2-project-only", "V2_GCP_REGION": "asia-northeast3",
        "CLOUDSDK_CONFIG": "/private/gcloud", "GH_CONFIG_DIR": "/private/github",
        "GIT_CONFIG_GLOBAL": "/private/gitconfig",
    }
    assert script.operator_environment(settings)["GH_TOKEN"] == "v2-unconfigured-token"


def test_operator_login_does_not_invoke_github_login_or_change_existing_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("operator_access")
    root = tmp_path / "v2-access"
    monkeypatch.setattr(script, "CONFIG_ROOT", root)
    monkeypatch.setattr(script, "SETTINGS_FILE", root / "operator-access.json")
    monkeypatch.setattr(script.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(script.shutil, "which", lambda name: "/fake/gcloud")
    existing = tmp_path / "existing-keyring"
    existing.write_text("synthetic-existing-keyring-token")
    gh_bin = tmp_path / "gh"
    gh_bin.touch()
    answers = iter(["github_pat_synthetic_v2_only", "synthetic-neon-key"])
    monkeypatch.setattr(script.getpass, "getpass", lambda prompt: next(answers))
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        assert kwargs["env"]["CLOUDSDK_CONFIG"] == str(root / "gcloud")
        assert kwargs["env"]["GIT_CONFIG_GLOBAL"] == str(root / "gitconfig")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    monkeypatch.setattr(script, "check", lambda settings: (
        script.operator_environment(settings)["GH_TOKEN"] == "github_pat_synthetic_v2_only"
    ))
    assert script.login("v2-project-only", "asia-northeast3", str(gh_bin))
    assert calls == [["gcloud", "auth", "login", "--no-launch-browser"]]
    assert existing.read_text() == "synthetic-existing-keyring-token"
    assert script.load_settings()["GH_TOKEN"] == "github_pat_synthetic_v2_only"


def test_operator_settings_are_private_and_no_default_config_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("operator_access")
    root = tmp_path / "v2-access"
    root.mkdir(mode=0o700)
    for name in ["gcloud", "github"]:
        (root / name).mkdir(mode=0o700)
    monkeypatch.setattr(script, "CONFIG_ROOT", root)
    monkeypatch.setattr(script, "SETTINGS_FILE", root / "operator-access.json")
    settings = {
        "V2_GCP_PROJECT_ID": "v2-project-only", "V2_GCP_REGION": "asia-northeast3",
        "CLOUDSDK_CONFIG": str(root / "gcloud"), "GH_CONFIG_DIR": str(root / "github"),
        "GIT_CONFIG_GLOBAL": str(root / "gitconfig"), "NEON_API_KEY": "synthetic-key",
    }
    script.save_settings(settings)
    assert script.SETTINGS_FILE.stat().st_mode & 0o077 == 0
    assert script.load_settings()["NEON_API_KEY"] == "synthetic-key"
    script.SETTINGS_FILE.chmod(0o644)
    with pytest.raises(ValueError, match="private"):
        script.load_settings()
    script.SETTINGS_FILE.chmod(0o600)
    script.save_settings({**settings, "CLOUDSDK_CONFIG": str(Path.home() / ".config/gcloud")})
    with pytest.raises(ValueError, match="Default GCP"):
        script.load_settings()


def test_operator_login_requires_real_terminal_before_any_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script("operator_access")
    monkeypatch.setattr(script.sys.stdin, "isatty", lambda: False)
    with pytest.raises(ValueError, match="real terminal"):
        script.login("v2-project-only", "asia-northeast3", "/not-used/gh")
