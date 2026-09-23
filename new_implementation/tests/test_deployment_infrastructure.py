"""Checks on the single-host deployment (docker-compose.yml on the VPS).

Mostly string-presence checks on the compose file, env template, host scripts
and the deploy workflow, plus two that *execute* shell: ensure_env.sh, and the
deploy workflow's remote step against a fake ssh. They do not replace running
the stack (F3 in ``fix_plan.md``), but they catch the regressions that matter:

- the API or Postgres being published on a public interface -- only nginx is;
- the bot or nginx being pointed anywhere but the API container (a leftover
  ``.env`` value from the old two-host layout must not win);
- the bot image growing dependencies beyond ``requirements-bot.txt``;
- host secrets leaving the host: GitHub holds only the Telegram token;
- the deploy workflow losing its gate, running on a red Test Suite, or passing
  a secret on a remote command line where ``ps`` would show it.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
REPO_ROOT = PROJECT_ROOT.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
GENERATED_SECRETS = ("POSTGRES_PASSWORD", "DIPLOMACY_JWT_SECRET", "DIPLOMACY_ADMIN_TOKEN", "DIPLOMACY_BOT_SECRET")


def _read(path: Path) -> str:
    assert path.exists(), f"{path} is missing"
    return path.read_text()


def _env_dict(text: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line and not line.startswith("#"))


# ---------------------------------------------------------------------------
# Env template
# ---------------------------------------------------------------------------


class TestEnvTemplate:
    def test_every_generated_secret_is_present_and_blank(self) -> None:
        env = _env_dict(_read(PROJECT_ROOT / ".env.example"))
        for key in (*GENERATED_SECRETS, "TELEGRAM_BOT_TOKEN"):
            assert key in env, key
            assert env[key] == "", f"{key} has a committed value"

    def test_no_two_host_leftovers(self) -> None:
        env = _env_dict(_read(PROJECT_ROOT / ".env.example"))
        for key in ("DIPLOMACY_API_URL", "DIPLOMACY_API_UPSTREAM", "WG_IP"):
            assert key not in env, key
        assert not (PROJECT_ROOT / ".env.control.example").exists()


# ---------------------------------------------------------------------------
# Compose file and images
# ---------------------------------------------------------------------------


class TestCompose:
    @pytest.fixture
    def compose(self) -> str:
        return _read(PROJECT_ROOT / "docker-compose.yml")

    def test_whole_stack_in_one_file(self, compose: str) -> None:
        for service in ("postgres:", "diplomacy_api:", "diplomacy_bot:", "diplomacy_web:"):
            assert f"\n  {service}" in compose, service
        assert not (PROJECT_ROOT / "docker-compose.control.yml").exists()

    def test_only_nginx_is_public(self, compose: str) -> None:
        assert not re.search(r'^\s*-\s*"?8000:8000"?\s*$', compose, re.M), "bare 8000:8000 publishes the API to the world"
        assert "127.0.0.1:8000:8000" in compose
        code = re.sub(r"#.*", "", compose)
        assert "10.8.0" not in code and "WG_IP" not in code
        assert "5432:" not in compose, "Postgres must not be published at all"
        assert "${WEB_BIND:-0.0.0.0}:${WEB_PORT:-80}:80" in compose

    def test_bot_and_nginx_reach_the_api_container_not_an_env_value(self, compose: str) -> None:
        assert "- DIPLOMACY_API_URL=http://diplomacy_api:8000" in compose
        assert "- DIPLOMACY_API_UPSTREAM=diplomacy_api:8000" in compose

    def test_durable_state_is_in_named_volumes(self, compose: str) -> None:
        assert "pg_data:/var/lib/postgresql/data" in compose
        assert "bot_data:/data" in compose  # the bot's queue survives rebuilds

    def test_api_trusts_forwarded_headers_from_nginx(self, compose: str) -> None:
        # Otherwise every browser request comes from nginx's address and the
        # per-IP login/register rate limits pool all users together.
        assert "FORWARDED_ALLOW_IPS=*" in compose

    def test_nginx_resolves_the_api_per_request(self) -> None:
        # A start-time `upstream` block pins the API container's old address
        # after `docker compose up -d` recreates it: 502 until nginx restarts.
        template = _read(PROJECT_ROOT / "docker" / "web-nginx.conf.template")
        assert "resolver 127.0.0.11" in template
        assert not re.search(r"^\s*upstream\s", template, re.M)
        assert "rewrite ^/api/(.*)$ /$1 break;" in template

    def test_bot_image_installs_only_the_bot_requirements(self) -> None:
        dockerfile = _read(PROJECT_ROOT / "docker" / "bot.Dockerfile")
        assert "requirements-bot.txt" in dockerfile
        assert not re.search(r"pip install .*\brequirements\.txt", dockerfile), "the bot image must not pull the API's deps"


# ---------------------------------------------------------------------------
# Host scripts
# ---------------------------------------------------------------------------


class TestHostScripts:
    @pytest.mark.parametrize("script", ["install.sh", "ensure_env.sh", "backup.sh", "upgrade.sh"])
    def test_script_parses(self, script: str) -> None:
        path = PROJECT_ROOT / script
        assert path.exists(), f"{script} is missing"
        subprocess.run(["bash", "-n", str(path)], check=True)

    @pytest.mark.parametrize("script", ["install_home.sh", "install_vps.sh", "upgrade_control.sh"])
    def test_two_host_scripts_are_gone(self, script: str) -> None:
        assert not (PROJECT_ROOT / script).exists()

    def test_upgrade_tolerates_a_detached_head(self) -> None:
        """The deploy workflow checks out the exact SHA the Test Suite passed on
        (a detached HEAD) before calling this script; a bare ``git pull`` there
        fails with "not on a branch" and, under ``set -e``, aborts the deploy."""
        script = _read(PROJECT_ROOT / "upgrade.sh")
        assert "git symbolic-ref -q HEAD" in script
        assert "git pull --ff-only" in script

    def test_upgrade_fills_secrets_schedules_backup_and_fails_when_down(self) -> None:
        script = _read(PROJECT_ROOT / "upgrade.sh")
        assert "./ensure_env.sh" in script
        assert "./backup.sh --install-cron" in script
        assert "/api/healthz" in script  # nginx -> API, the path a browser takes
        assert script.rstrip().endswith('[ "$api_ok" = 1 ] && [ "$web_ok" = 1 ]')


class TestEnsureEnv:
    """Run the real ensure_env.sh in a scratch directory."""

    @pytest.fixture
    def workdir(self, tmp_path: Path) -> Path:
        for name in ("ensure_env.sh", ".env.example"):
            (tmp_path / name).write_bytes((PROJECT_ROOT / name).read_bytes())
        (tmp_path / "ensure_env.sh").chmod(0o755)
        return tmp_path

    def _run(self, workdir: Path) -> str:
        result = subprocess.run(["bash", str(workdir / "ensure_env.sh")], capture_output=True, text=True, check=True)
        return result.stdout + result.stderr

    def test_creates_env_with_every_secret_and_never_prints_one(self, workdir: Path) -> None:
        out = self._run(workdir)
        env = _env_dict((workdir / ".env").read_text())
        for key in GENERATED_SECRETS:
            assert re.fullmatch(r"[0-9a-f]{64}", env[key]), key
            assert env[key] not in out
        assert len({env[k] for k in GENERATED_SECRETS}) == len(GENERATED_SECRETS)
        assert (workdir / ".env").stat().st_mode & 0o777 == 0o600

    def test_is_idempotent(self, workdir: Path) -> None:
        self._run(workdir)
        first = (workdir / ".env").read_text()
        assert self._run(workdir).strip() == "==> NOTE: TELEGRAM_BOT_TOKEN is empty; the bot will not start until it is set."
        assert (workdir / ".env").read_text() == first

    def test_migrates_a_two_host_env(self, workdir: Path) -> None:
        # The VPS .env as it was on 2026-09-23: tunnel URLs, and the bot secret
        # accidentally set to the Telegram token.
        (workdir / ".env").write_text(
            "TELEGRAM_BOT_TOKEN=123:abc\n"
            "DIPLOMACY_API_URL=http://10.8.0.2:8000\n"
            "DIPLOMACY_API_UPSTREAM=10.8.0.2:8000\n"
            "DIPLOMACY_BOT_SECRET=123:abc\n"
            "WEB_BIND=0.0.0.0\n"
        )
        self._run(workdir)
        env = _env_dict((workdir / ".env").read_text())
        assert env["TELEGRAM_BOT_TOKEN"] == "123:abc"
        assert env["WEB_BIND"] == "0.0.0.0"
        assert env["DIPLOMACY_BOT_SECRET"] not in ("", "123:abc")
        assert "DIPLOMACY_API_URL" not in env and "DIPLOMACY_API_UPSTREAM" not in env
        for key in GENERATED_SECRETS:
            assert env[key], key


# ---------------------------------------------------------------------------
# Deploy workflow
# ---------------------------------------------------------------------------


class TestDeployWorkflow:
    @pytest.fixture
    def workflow(self) -> str:
        return _read(WORKFLOWS / "deploy.yml")

    def test_only_runs_after_test_suite_passes_and_when_enabled(self, workflow: str) -> None:
        assert 'workflows: ["Test Suite"]' in workflow
        assert "workflow_run.conclusion == 'success'" in workflow
        assert "vars.DEPLOY_CONTROL_ENABLED == 'true'" in workflow

    def test_github_holds_only_the_telegram_token(self, workflow: str) -> None:
        secrets = set(re.findall(r"secrets\.([A-Z_]+)", workflow))
        assert secrets == {"TELEGRAM_BOT_TOKEN", "VPS_SSH_KEY", "VPS_HOST_KEY"}

    def test_secrets_travel_on_stdin_not_the_remote_command_line(self, workflow: str) -> None:
        # Prepended to the script stream as a %q assignment; the ssh argument list
        # only carries the SHA and the repo dir. (A remote `read` cannot work: stdin
        # *is* the script -- see TestDeployStepRuns.)
        assert "bash -s" in workflow
        assert "printf 'TELEGRAM_BOT_TOKEN=%q\\n'" in workflow
        assert "read -r TELEGRAM_BOT_TOKEN" not in workflow
        assert not re.search(r"ssh .*TELEGRAM_BOT_TOKEN=", workflow)

    def test_pins_the_host_key_instead_of_scanning(self, workflow: str) -> None:
        assert "${{ secrets.VPS_HOST_KEY }}" in workflow
        assert "ssh-keyscan" not in re.sub(r"#.*", "", workflow)  # allowed only in the comment

    def test_deploys_the_tested_sha_and_runs_the_upgrade_script(self, workflow: str) -> None:
        assert "git checkout --quiet --detach" in workflow
        assert "./upgrade.sh" in workflow
        assert "concurrency:" in workflow

    def test_manual_run_resolves_a_commit_not_a_branch_name(self, workflow: str) -> None:
        # The VPS checkout has no local `main` branch; `git checkout --detach main` fails there.
        assert 'sha="main"' not in workflow
        assert "${{ github.sha }}" in workflow

    def test_fetches_the_target_itself(self, workflow: str) -> None:
        # The VPS clone is single-branch (vps-split); a bare `git fetch origin` never brings
        # main's commits, and the checkout died with "unable to read tree".
        assert 'git fetch --quiet origin "$SHA"' in workflow
        assert "git checkout --quiet --detach FETCH_HEAD" in workflow

    def test_no_aws_and_no_split_era_workflow(self) -> None:
        assert not (WORKFLOWS / "deploy-control.yml").exists()
        assert not (PROJECT_ROOT / "infra" / "terraform").exists()
        for path in WORKFLOWS.glob("*.yml"):
            assert "aws-actions" not in path.read_text(), path


# ---------------------------------------------------------------------------
# The Deploy step, executed: fake ssh, a local git remote, a single-branch clone
# ---------------------------------------------------------------------------


def _deploy_step_script(workflow: str) -> str:
    """The `run: |` body of the Deploy step, de-indented as Actions would."""
    lines = workflow.splitlines()
    start = lines.index("      - name: Deploy")
    run_at = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
    body: list[str] = []
    for line in lines[run_at + 1 :]:
        if line.strip() and not line.startswith(" " * 10):
            break
        body.append(line[10:])
    return "\n".join(body) + "\n"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


class TestDeployStepRuns:
    """Run the real step script end to end. v2.7.83's version piped the secrets into
    ssh *and* gave it a heredoc; the heredoc won, the remote `read`s swallowed script
    lines, and the VPS .env got `TELEGRAM_BOT_TOKEN=IFS= read -r ...`. String checks
    could not see that; only running it can."""

    def test_writes_the_token_verbatim_keeps_host_secrets_and_runs_the_upgrade(self, tmp_path: Path) -> None:
        origin = tmp_path / "origin"
        (origin / "new_implementation").mkdir(parents=True)
        _git(origin, "init", "-q", "-b", "main")
        app = origin / "new_implementation"
        (app / ".env.example").write_text("TELEGRAM_BOT_TOKEN=\nDIPLOMACY_BOT_SECRET=\nWEB_BIND=127.0.0.1\n")
        (app / "upgrade.sh").write_text("#!/bin/sh\ntouch upgraded\n")
        (app / "upgrade.sh").chmod(0o755)
        _git(origin, "add", "-A")
        _git(origin, "commit", "-qm", "base")
        _git(origin, "branch", "vps-split")
        (app / "marker").write_text("main\n")
        _git(origin, "add", "-A")
        _git(origin, "commit", "-qm", "main only")
        sha = _git(origin, "rev-parse", "HEAD")

        # Like the VPS: cloned single-branch on vps-split, .env already holding
        # an old token and a host-generated secret that must survive untouched.
        clone = tmp_path / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--single-branch", "-b", "vps-split", str(origin), str(clone)],
            check=True,
        )
        (clone / "new_implementation" / ".env").write_text(
            "TELEGRAM_BOT_TOKEN=old\nDIPLOMACY_BOT_SECRET=host-only\nWEB_BIND=10.0.0.1\n"
        )

        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "ssh").write_text('#!/bin/bash\nexec bash -c "${@: -1}"\n')  # run the remote command locally
        (bin_dir / "ssh").chmod(0o755)

        token = "123456:AAH-x_Y'z $b \"c\" `d`"
        script = _deploy_step_script(_read(WORKFLOWS / "deploy.yml"))
        result = subprocess.run(
            ["bash", "-e", "-c", script],
            env={
                "PATH": f"{bin_dir}:/usr/bin:/bin",
                "HOME": str(tmp_path),
                "TELEGRAM_BOT_TOKEN": token,
                "SHA": sha,
                "REPO_DIR": str(clone / "new_implementation"),
                "TARGET": "root@vps",
            },
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

        deployed = clone / "new_implementation"
        assert _git(clone, "rev-parse", "HEAD") == sha
        assert (deployed / "upgraded").exists()
        assert (deployed / ".env").read_text().splitlines() == [
            f"TELEGRAM_BOT_TOKEN={token}",
            "DIPLOMACY_BOT_SECRET=host-only",
            "WEB_BIND=10.0.0.1",
        ]
        assert token not in result.stdout + result.stderr
