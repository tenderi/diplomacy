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
REPO_ROOT = PROJECT_ROOT
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

    def test_caddy_is_the_https_entry_only_when_a_domain_is_set(self, compose: str) -> None:
        caddy = compose.split("\n  caddy:", 1)[1].split("\nvolumes:", 1)[0]
        assert 'profiles: ["tls"]' in caddy  # started only via COMPOSE_PROFILES=tls
        assert '"80:80"' in caddy and '"443:443"' in caddy
        assert "caddy_data:/data" in caddy  # certificates survive a restart
        caddyfile = _read(PROJECT_ROOT / "docker" / "Caddyfile")
        assert "{$DOMAIN}" in caddyfile and "reverse_proxy diplomacy_web:80" in caddyfile

    def test_nginx_takes_the_client_address_from_caddy_and_never_appends(self) -> None:
        # Behind Caddy every peer is Caddy; without real_ip all visitors share its
        # address in the per-IP rate limits. Appending to a client's own
        # X-Forwarded-For let it pick the (first) address uvicorn reads.
        conf = _read(PROJECT_ROOT / "docker" / "web-nginx.conf.template")
        assert "real_ip_header X-Forwarded-For;" in conf and "set_real_ip_from 172.16.0.0/12;" in conf
        assert "proxy_set_header X-Forwarded-For $remote_addr;" in conf
        assert "$proxy_add_x_forwarded_for" not in conf

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

    def test_logs_outlive_the_containers_and_the_bot_waits_for_the_api(self, compose: str) -> None:
        # A deploy recreates every container, and a json-file log goes with its
        # container; the journal keeps them. The bot starting before the API is
        # healthy only produced a burst of retries.
        assert "x-logging: &logging\n  driver: journald\n" in compose
        assert "json-file" not in re.sub(r"#.*", "", compose)
        services = compose.split("\nservices:\n", 1)[1].split("\nvolumes:", 1)[0]
        names = re.findall(r"^  ([a-z_]+):$", services, re.M)
        assert len(names) == 6 and services.count("    logging: *logging\n") == len(names), names
        bot = services.split("\n  diplomacy_bot:", 1)[1].split("\n  diplomacy_web:", 1)[0]
        assert "    depends_on:\n      diplomacy_api:\n        condition: service_healthy\n" in bot
        assert compose.count("- DIPLOMACY_ADMIN_TELEGRAM_ID=${DIPLOMACY_ADMIN_TELEGRAM_ID:-}") == 2  # API and bot

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
    @pytest.mark.parametrize("script", ["install.sh", "ensure_env.sh", "backup.sh", "upgrade.sh", "harden_host.sh"])
    def test_script_parses(self, script: str) -> None:
        path = PROJECT_ROOT / script
        assert path.exists(), f"{script} is missing"
        subprocess.run(["bash", "-n", str(path)], check=True)

    def test_host_hardening(self) -> None:
        script = _read(PROJECT_ROOT / "harden_host.sh")
        for line in ("PasswordAuthentication no", "PermitRootLogin prohibit-password", "X11Forwarding no", "MaxAuthTries 3"):
            assert line in script, line
        assert "sshd -t" in script  # validated before the reload, removed if invalid
        assert "restrict \\1" in script  # the deploy key: no forwarding, no pty
        assert 'Automatic-Reboot "true"' in script and "[sshd]" in script
        assert "./harden_host.sh" in _read(PROJECT_ROOT / "install.sh")

    def test_containers_cannot_gain_privileges(self) -> None:
        compose = _read(PROJECT_ROOT / "docker-compose.yml")
        assert compose.count("no-new-privileges:true") == 6  # every service
        assert compose.count("cap_drop:") == 2  # the API and the bot need no capabilities
        assert "DIPLOMACY_API_DOCS=0" in compose

    def test_the_docs_site_builds_strictly_and_is_served_only_through_caddy(self) -> None:
        compose = _read(PROJECT_ROOT / "docker-compose.yml")
        docs = compose.split("\n  diplomacy_docs:", 1)[1].split("\n  caddy:", 1)[0]
        assert "ports:" not in docs and 'profiles: ["tls"]' in docs
        assert "DOCS_DOMAIN=${DOCS_DOMAIN:-http://docs.invalid}" in compose  # never an empty site address
        assert "mkdocs build --strict" in _read(PROJECT_ROOT / "docker" / "docs.Dockerfile")
        assert "{$DOCS_DOMAIN}" in _read(PROJECT_ROOT / "docker" / "Caddyfile")

    def test_https_headers(self) -> None:
        caddyfile = _read(PROJECT_ROOT / "docker" / "Caddyfile")
        for header in ("Strict-Transport-Security", "Content-Security-Policy", "X-Content-Type-Options",
                       "X-Frame-Options", "Referrer-Policy", "-Server"):
            assert header in caddyfile, header
        assert "script-src 'self';" in caddyfile
        assert "server_tokens off;" in _read(PROJECT_ROOT / "docker" / "web-nginx.conf.template")

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
        assert "./backup.sh --install" in script
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


class TestEnsureEnvDomain:
    """Setting DOMAIN turns HTTPS on; clearing it turns it off."""

    @pytest.fixture
    def workdir(self, tmp_path: Path) -> Path:
        for name in ("ensure_env.sh", ".env.example"):
            (tmp_path / name).write_bytes((PROJECT_ROOT / name).read_bytes())
        return tmp_path

    def _run(self, workdir: Path) -> dict[str, str]:
        subprocess.run(["bash", str(workdir / "ensure_env.sh")], capture_output=True, text=True, check=True)
        return _env_dict((workdir / ".env").read_text())

    def test_a_domain_turns_on_caddy_and_moves_nginx_off_the_public_ports(self, workdir: Path) -> None:
        self._run(workdir)
        (workdir / ".env").write_text((workdir / ".env").read_text().replace("DOMAIN=\n", "DOMAIN=play.example.com\n"))
        env = self._run(workdir)
        assert env["COMPOSE_PROFILES"] == "tls"
        assert env["WEB_BIND"] == "127.0.0.1" and env["WEB_PORT"] == "8080"
        assert env["DIPLOMACY_PASSWORD_RESET_BASE_URL"] == "https://play.example.com"

    def test_an_existing_https_reset_url_is_kept(self, workdir: Path) -> None:
        (workdir / ".env").write_text("DOMAIN=play.example.com\nDIPLOMACY_PASSWORD_RESET_BASE_URL=https://other.example.com\n")
        assert self._run(workdir)["DIPLOMACY_PASSWORD_RESET_BASE_URL"] == "https://other.example.com"

    def test_clearing_the_domain_turns_https_off(self, workdir: Path) -> None:
        (workdir / ".env").write_text("DOMAIN=play.example.com\n")
        self._run(workdir)
        text = (workdir / ".env").read_text().replace("DOMAIN=play.example.com", "DOMAIN=")
        (workdir / ".env").write_text(text)
        env = self._run(workdir)
        assert env["COMPOSE_PROFILES"] == ""
        assert env["WEB_BIND"] == "127.0.0.1"  # stays private; opening it is a choice

    def test_no_domain_changes_nothing(self, workdir: Path) -> None:
        env = self._run(workdir)
        assert env.get("COMPOSE_PROFILES", "") == "" and env["WEB_PORT"] == "80"


class TestBackup:
    """Run the real backup.sh with fake `docker` and `rclone` on PATH."""

    FAKE_RCLONE = """#!/bin/bash
echo "$*" >> "$FAKE_LOG"
case "$1" in
  version) echo "rclone ${FAKE_RCLONE_VERSION:-v1.75.1}" ;;
  listremotes) printf '%s\\n' $FAKE_REMOTES ;;
  copy) [ -z "${FAKE_COPY_FAIL:-}" ] ;;
esac
"""

    @pytest.fixture
    def env(self, tmp_path: Path) -> dict[str, str]:
        work = tmp_path / "work"
        work.mkdir()
        (work / "backup.sh").write_bytes((PROJECT_ROOT / "backup.sh").read_bytes())
        (work / "backup.sh").chmod(0o755)
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "docker").write_text("#!/bin/sh\necho '-- fake dump'\n")
        (bin_dir / "rclone").write_text(self.FAKE_RCLONE)
        for tool in ("docker", "rclone"):
            (bin_dir / tool).chmod(0o755)
        return {
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "BACKUP_DIR": str(tmp_path / "backups"),
            "FAKE_LOG": str(tmp_path / "rclone.log"),
            "FAKE_REMOTES": "",
            "WORK": str(work),
        }

    def _run(self, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["bash", f"{env['WORK']}/backup.sh"], env=env, capture_output=True, text=True)

    def _calls(self, env: dict[str, str]) -> list[str]:
        log = Path(env["FAKE_LOG"])
        return log.read_text().splitlines() if log.exists() else []

    def _dumps(self, env: dict[str, str]) -> list[Path]:
        return sorted(Path(env["BACKUP_DIR"]).glob("diplomacy-*.sql.gz"))

    def test_without_a_configured_remote_the_local_backup_still_happens(self, env: dict[str, str]) -> None:
        result = self._run(env)
        assert result.returncode == 0, result.stderr
        assert len(self._dumps(env)) == 1
        assert "off-host copy skipped: rclone remote 'proton:' not configured" in result.stdout
        assert not any(c.startswith("copy") for c in self._calls(env))

    def test_copies_to_proton_and_prunes_old_remote_copies(self, env: dict[str, str]) -> None:
        env["FAKE_REMOTES"] = "proton:"
        result = self._run(env)
        assert result.returncode == 0, result.stderr
        calls = self._calls(env)
        assert f"copy {env['BACKUP_DIR']} proton:diplomacy-backups --include diplomacy-*.sql.gz" in calls
        assert "delete proton:diplomacy-backups --include diplomacy-*.sql.gz --min-age 60d" in calls
        assert "off-host copy done: proton:diplomacy-backups" in result.stdout

    def test_a_failed_upload_fails_the_run_and_keeps_the_local_file(self, env: dict[str, str]) -> None:
        env["FAKE_REMOTES"] = "proton:"
        env["FAKE_COPY_FAIL"] = "1"
        result = self._run(env)
        assert result.returncode == 1
        assert "ERROR: off-host copy to proton:diplomacy-backups failed" in result.stderr
        assert len(self._dumps(env)) == 1
        assert not any(c.startswith("delete") for c in self._calls(env))

    def test_an_rclone_without_protondrive_is_not_used(self, env: dict[str, str]) -> None:
        env["FAKE_REMOTES"] = "proton:"
        env["FAKE_RCLONE_VERSION"] = "v1.60.1-DEV"  # Ubuntu's package
        result = self._run(env)
        assert result.returncode == 0, result.stderr
        assert "rclone >= 1.64 not installed" in result.stdout
        assert not any(c.startswith("copy") for c in self._calls(env))

    def test_remote_can_be_set_in_env_file(self, env: dict[str, str]) -> None:
        env["FAKE_REMOTES"] = "other:"
        (Path(env["WORK"]) / ".env").write_text("BACKUP_RCLONE_REMOTE=other:dip\n")
        result = self._run(env)
        assert result.returncode == 0, result.stderr
        assert any(c.startswith("copy ") and c.split()[2] == "other:dip" for c in self._calls(env))


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

    def _deploy(self, tmp_path: Path, *, env_in: str) -> tuple[Path, str, subprocess.CompletedProcess[str]]:
        """Deploy origin's main (flat layout) into a clone like the VPS one:
        single-branch on vps-split, whose tip still has the old
        new_implementation/ layout, with the host's .env at ``env_in``."""
        origin = tmp_path / "origin"
        (origin / "new_implementation").mkdir(parents=True)
        _git(origin, "init", "-q", "-b", "main")
        (origin / "new_implementation" / ".env.example").write_text("TELEGRAM_BOT_TOKEN=\n")
        _git(origin, "add", "-A")
        _git(origin, "commit", "-qm", "base (old layout)")
        _git(origin, "branch", "vps-split")
        _git(origin, "rm", "-rq", "new_implementation")
        (origin / ".env.example").write_text("TELEGRAM_BOT_TOKEN=\nDIPLOMACY_BOT_SECRET=\nWEB_BIND=127.0.0.1\n")
        (origin / "upgrade.sh").write_text("#!/bin/sh\ntouch upgraded\n")
        (origin / "upgrade.sh").chmod(0o755)
        _git(origin, "add", "-A")
        _git(origin, "commit", "-qm", "main (flat layout)")
        sha = _git(origin, "rev-parse", "HEAD")

        clone = tmp_path / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--single-branch", "-b", "vps-split", str(origin), str(clone)],
            check=True,
        )
        # An old token and a host-generated secret that must survive untouched.
        (clone / env_in).write_text("TELEGRAM_BOT_TOKEN=old\nDIPLOMACY_BOT_SECRET=host-only\nWEB_BIND=10.0.0.1\n")

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
                "REPO_DIR": str(clone),
                "TARGET": "root@vps",
            },
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        assert _git(clone, "rev-parse", "HEAD") == sha
        assert (clone / "upgraded").exists()
        assert token not in result.stdout + result.stderr
        return clone, token, result

    def test_writes_the_token_verbatim_keeps_host_secrets_and_runs_the_upgrade(self, tmp_path: Path) -> None:
        clone, token, _ = self._deploy(tmp_path, env_in=".env")
        assert (clone / ".env").read_text().splitlines() == [
            f"TELEGRAM_BOT_TOKEN={token}",
            "DIPLOMACY_BOT_SECRET=host-only",
            "WEB_BIND=10.0.0.1",
        ]

    def test_the_first_flat_deploy_moves_the_host_env_up_instead_of_making_a_new_one(self, tmp_path: Path) -> None:
        """The VPS's .env is untracked in new_implementation/; the checkout that
        removes that directory leaves it there. A fresh root .env would get a new
        POSTGRES_PASSWORD the existing database doesn't know."""
        clone, token, result = self._deploy(tmp_path, env_in="new_implementation/.env")
        assert "Moved .env up" in result.stdout
        assert not (clone / "new_implementation" / ".env").exists()
        assert (clone / ".env").read_text().splitlines() == [
            f"TELEGRAM_BOT_TOKEN={token}",
            "DIPLOMACY_BOT_SECRET=host-only",
            "WEB_BIND=10.0.0.1",
        ]
