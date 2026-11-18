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

import json
import re
import shutil
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

    def test_logs_outlive_the_containers_and_the_bot_starts_without_a_healthy_api(self, compose: str) -> None:
        # A deploy recreates every container, and a json-file log goes with its
        # container; the journal keeps them. The bot starting before the API is
        # healthy is handled by the bot itself.
        assert "x-logging: &logging\n  driver: journald\n" in compose
        assert "json-file" not in re.sub(r"#.*", "", compose)
        services = compose.split("\nservices:\n", 1)[1].split("\nvolumes:", 1)[0]
        names = re.findall(r"^  ([a-z_]+):$", services, re.M)
        assert len(names) == 6 and services.count("    logging: *logging\n") == len(names), names
        bot = services.split("\n  diplomacy_bot:", 1)[1].split("\n  diplomacy_web:", 1)[0]
        # Ordered after the API but never gated on its health: an unhealthy API
        # must not keep the bot (and its durable queue) from starting.
        assert "    depends_on:\n      - diplomacy_api\n" in bot
        assert "service_healthy" not in re.sub(r"#.*", "", bot)
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
    @pytest.mark.parametrize(
        "script",
        ["install.sh", "ensure_env.sh", "backup.sh", "upgrade.sh", "harden_host.sh",
         "host/deploy_hook.sh", "host/agent_shell.sh"],
    )
    def test_script_parses(self, script: str) -> None:
        path = PROJECT_ROOT / script
        assert path.exists(), f"{script} is missing"
        subprocess.run(["bash", "-n", str(path)], check=True)

    def test_host_hardening(self) -> None:
        script = _read(PROJECT_ROOT / "harden_host.sh")
        for line in ("PasswordAuthentication no", "PermitRootLogin prohibit-password", "X11Forwarding no", "MaxAuthTries 3"):
            assert line in script, line
        assert "sshd -t" in script  # validated before the reload, removed if invalid
        # Neither key GitHub holds can open a shell: each runs one toolkit script.
        assert 'force_command github-actions-deploy "$TOOLKIT/deploy_hook.sh"' in script
        assert 'force_command diplomacy-lead-agent "$TOOLKIT/agent_shell.sh"' in script
        assert 'want="restrict,command=' in script
        assert 'Automatic-Reboot "true"' in script and "[sshd]" in script
        assert "./harden_host.sh" in _read(PROJECT_ROOT / "install.sh")

    def test_containers_cannot_gain_privileges(self) -> None:
        compose = _read(PROJECT_ROOT / "docker-compose.yml")
        assert compose.count("no-new-privileges:true") == 6  # every service
        assert compose.count("cap_drop:") == 6  # every service starts from no capabilities
        assert compose.count("cap_add:") == 4  # postgres, the two nginx, caddy: named ones only
        # A runaway container must not starve the host's other projects.
        assert compose.count("mem_limit:") == 6 and compose.count("pids_limit:") == 6
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

    def test_upgrade_fills_secrets_refreshes_the_agent_role_and_fails_when_down(self) -> None:
        script = _read(PROJECT_ROOT / "upgrade.sh")
        assert '"$HERE/ensure_env.sh"' in script  # the toolkit's copy when installed
        # The backup job is installed by install.sh from the toolkit, never by a deploy:
        # a deploy must not change what root runs at night.
        assert "backup.sh --install" not in script
        assert "agent_db_role.sql" in script
        assert "/api/healthz" in script  # nginx -> API, the path a browser takes
        assert script.rstrip().endswith('[ "$api_ok" = 1 ] && [ "$web_ok" = 1 ]')


class TestComposeImages:
    @pytest.mark.parametrize("svc", ["api", "bot", "web", "docs"])
    def test_own_images_come_from_ghcr_and_can_still_be_built(self, svc: str) -> None:
        compose = _read(PROJECT_ROOT / "docker-compose.yml")
        assert (
            f"    image: ghcr.io/tenderi/diplomacy-{svc}:${{DIPLOMACY_IMAGE_TAG:-local}}\n"
            f"    build:\n      context: .\n      dockerfile: docker/{svc}.Dockerfile\n"
            # The label upgrade.sh prunes by: a host build must carry it as the GHCR
            # images do, or its SHA-tagged images are never removed.
            "      labels:\n        - org.opencontainers.image.source=https://github.com/tenderi/diplomacy\n"
        ) in compose

    def test_the_resolved_build_config_carries_the_prune_label(self) -> None:
        """What Compose actually hands the builder, not just the file's text."""
        docker = shutil.which("docker")
        if docker is None or subprocess.run([docker, "compose", "version"], capture_output=True).returncode != 0:
            pytest.skip("docker compose not installed")
        env = {k: "x" for k in (*GENERATED_SECRETS, "TELEGRAM_BOT_TOKEN")}
        result = subprocess.run(
            [docker, "compose", "-f", str(PROJECT_ROOT / "docker-compose.yml"), "--profile", "tls",
             "config", "--format", "json", "--no-path-resolution"],
            env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", **env},
            capture_output=True, text=True, check=True,
        )
        services = json.loads(result.stdout)["services"]
        built = {name for name, svc in services.items() if "build" in svc}
        assert built == {"diplomacy_api", "diplomacy_bot", "diplomacy_web", "diplomacy_docs"}
        for name in built:
            assert services[name]["build"]["labels"] == {
                "org.opencontainers.image.source": "https://github.com/tenderi/diplomacy"
            }, name


class TestUpgradeRuns:
    """Run the real upgrade.sh against a fake `docker` that logs its calls."""

    OWN = ["diplomacy_api", "diplomacy_bot", "diplomacy_web", "diplomacy_docs"]

    def _run(
        self, tmp_path: Path, *args: str, pull_rc: int = 0, env_text: str = "A=1\n"
    ) -> tuple[list[str], str, subprocess.CompletedProcess[str]]:
        work = tmp_path / "work"
        work.mkdir()
        (work / "upgrade.sh").write_bytes((PROJECT_ROOT / "upgrade.sh").read_bytes())
        for stub in ("ensure_env.sh", "backup.sh"):
            (work / stub).write_text("#!/bin/sh\n")
        for name in ("upgrade.sh", "ensure_env.sh", "backup.sh"):
            (work / name).chmod(0o755)
        (work / ".env").write_text(env_text)
        (work / ".env").chmod(0o600)
        _git(work, "init", "-q")
        _git(work, "add", "upgrade.sh")
        _git(work, "commit", "-qm", "x")
        sha = _git(work, "rev-parse", "HEAD")
        _git(work, "checkout", "-q", "--detach")  # as the deploy leaves it: no `git pull`

        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        log = tmp_path / "docker.log"
        (bin_dir / "docker").write_text(
            "#!/bin/bash\n"
            f'echo "TAG=$DIPLOMACY_IMAGE_TAG $*" >> {log}\n'
            'case "$*" in\n'
            f'  "compose config --services") printf "%s\\n" postgres {" ".join(self.OWN)} caddy ;;\n'
            f'  "compose pull"*) exit {pull_rc} ;;\n'
            '  "system df") printf "TYPE\\nBuild Cache 0B\\n" ;;\n'
            "esac\n"
        )
        (bin_dir / "curl").write_text("#!/bin/sh\n")
        for name in ("docker", "curl"):
            (bin_dir / name).chmod(0o755)
        result = subprocess.run(
            ["bash", str(work / "upgrade.sh"), *args],
            env={"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path)},
            capture_output=True, text=True,
        )
        calls = log.read_text().splitlines() if log.exists() else []
        self.env_after = (work / ".env").read_text()
        return calls, sha, result

    def test_pulls_this_commits_images_and_never_builds(self, tmp_path: Path) -> None:
        calls, sha, result = self._run(tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        assert f"TAG={sha} compose pull --quiet {' '.join(self.OWN)}" in calls
        assert not any(" build" in c for c in calls)
        assert not any("builder prune" in c for c in calls)  # nothing was built here
        assert f"TAG={sha} compose up -d --no-build --remove-orphans" in calls
        assert self.env_after == f"A=1\nDIPLOMACY_IMAGE_TAG={sha}\n"

    def test_a_failed_pull_builds_on_the_host_with_a_warning(self, tmp_path: Path) -> None:
        calls, sha, result = self._run(tmp_path, pull_rc=1)
        assert result.returncode == 0, result.stdout + result.stderr
        assert f"::warning::Could not pull ghcr.io/tenderi/diplomacy-*:{sha}" in result.stdout
        pull = calls.index(f"TAG={sha} compose pull --quiet {' '.join(self.OWN)}")
        assert calls[pull + 1] == f"TAG={sha} compose build"
        assert f"TAG={sha} builder prune -af" in calls  # v3.0.116: the cache a host build leaves

    def test_build_flag_skips_the_pull(self, tmp_path: Path) -> None:
        calls, sha, result = self._run(tmp_path, "--build", env_text="DIPLOMACY_IMAGE_TAG=old\nA=1\n")
        assert result.returncode == 0, result.stdout + result.stderr
        assert f"TAG={sha} compose build" in calls
        assert not any("compose pull" in c for c in calls)
        assert f"TAG={sha} builder prune -af" in calls
        assert self.env_after == f"DIPLOMACY_IMAGE_TAG={sha}\nA=1\n"

    def test_prunes_only_our_own_unused_images(self, tmp_path: Path) -> None:
        """The host runs other projects; a bare `image prune -a` would delete their images."""
        calls, _, _ = self._run(tmp_path)
        prunes = [c.split(" ", 1)[1] for c in calls if "image prune" in c]
        assert prunes == [
            "image prune -af --filter label=org.opencontainers.image.source=https://github.com/tenderi/diplomacy",
            "image prune -f",
        ]

    def test_rejects_an_unknown_argument(self, tmp_path: Path) -> None:
        calls, _, result = self._run(tmp_path, "--bild")
        assert result.returncode == 2
        assert "unknown argument: --bild" in result.stderr
        assert calls == []


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
        # GITHUB_TOKEN is the run's own token (pushing to GHCR), not a stored secret.
        secrets = set(re.findall(r"secrets\.([A-Z_]+)", workflow))
        # VPS_HOST is the address (a secret only so the public logs mask it).
        assert secrets == {"TELEGRAM_BOT_TOKEN", "VPS_HOST", "VPS_SSH_KEY", "VPS_HOST_KEY", "GITHUB_TOKEN"}
        assert "VPS_AGENT_KEY" not in workflow  # the lead agent's key never deploys
        assert workflow.count("secrets.GITHUB_TOKEN") == 1
        assert "password: ${{ secrets.GITHUB_TOKEN }}" in workflow  # the GHCR login only

    def test_secrets_travel_on_stdin_not_the_remote_command_line(self, workflow: str) -> None:
        # The ssh argument list carries only "deploy <sha>": the deploy key's forced
        # command (host/deploy_hook.sh) reads the token from stdin.
        assert "printf 'TELEGRAM_BOT_TOKEN=%s\\n' \"$TELEGRAM_BOT_TOKEN\"" in workflow
        assert '"$TARGET" "deploy $SHA"' in workflow
        assert "bash -s" not in workflow  # no script is sent: the host runs its own
        assert not re.search(r"ssh .*TELEGRAM_BOT_TOKEN=", workflow)

    def test_pins_the_host_key_instead_of_scanning(self, workflow: str) -> None:
        assert "${{ secrets.VPS_HOST_KEY }}" in workflow
        assert "ssh-keyscan" not in re.sub(r"#.*", "", workflow)  # allowed only in the comment

    def test_deploys_the_tested_sha_through_the_host_hook(self, workflow: str) -> None:
        hook = _read(PROJECT_ROOT / "host" / "deploy_hook.sh")
        assert 'git checkout --quiet --detach "$sha"' in hook
        assert 'DIPLOMACY_IMAGE_TAG="$sha" exec "$HERE/upgrade.sh"' in hook  # the toolkit's copy
        assert "concurrency:" in workflow

    def test_manual_run_resolves_a_commit_not_a_branch_name(self, workflow: str) -> None:
        # The VPS checkout has no local `main` branch; `git checkout --detach main` fails there.
        assert 'sha="main"' not in workflow
        assert "REF: ${{ inputs.ref || github.event.workflow_run.head_sha || github.sha }}" in workflow
        # A tag or short SHA becomes the full SHA that both tags the images and is checked out.
        # actions/checkout's `ref:` takes no short SHA, so it fetches everything and git resolves.
        assert "fetch-depth: 0" in workflow
        assert 'sha=$(git rev-parse --verify --end-of-options "$REF^{commit}")' in workflow
        assert 'git checkout --quiet --detach "$sha"' in workflow
        assert 'sha="${{ needs.images.outputs.sha }}"' in workflow

    def test_builds_the_images_in_actions_and_the_host_pulls_them(self, workflow: str) -> None:
        """Issue #224: nothing is built on the 1-vCPU VPS. The images job pushes
        ghcr.io/tenderi/diplomacy-<service>:<sha>; the deploy job needs it and hands
        upgrade.sh that tag."""
        assert "service: [api, bot, web, docs]" in workflow
        assert "packages: write" in workflow
        assert "image=ghcr.io/tenderi/diplomacy-${{ matrix.service }}:$sha" in workflow
        assert "file: docker/${{ matrix.service }}.Dockerfile" in workflow
        assert "org.opencontainers.image.source=https://github.com/${{ github.repository }}" in workflow
        assert "cache-from: type=gha,scope=${{ matrix.service }}" in workflow
        assert "if: steps.exists.outputs.found != 'true'" in workflow  # a rollback reuses its images
        assert "needs: images" in workflow

    def test_fetches_the_target_itself(self) -> None:
        # The VPS clone is single-branch (vps-split); a bare `git fetch origin` never brings
        # main's commits, and the checkout died with "unable to read tree".
        hook = _read(PROJECT_ROOT / "host" / "deploy_hook.sh")
        assert 'git fetch --quiet origin "+refs/heads/main:refs/remotes/origin/main" "$sha"' in hook

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
    """Run the real Deploy step end to end: the workflow's `run:` body, a fake `ssh`
    that hands the request to the real host/deploy_hook.sh as its forced command
    would (SSH_ORIGINAL_COMMAND, stdin), a local origin and a single-branch clone
    like the VPS one, and a host toolkit directory with a stub upgrade.sh."""

    TOKEN = "123456:AAH-x_Yz9"

    def _setup(self, tmp_path: Path) -> dict[str, Path | str]:
        origin = tmp_path / "origin"
        (origin / "docker").mkdir(parents=True)
        _git(origin, "init", "-q", "-b", "main")
        (origin / "docker-compose.yml").write_text("services: {}\n")
        (origin / "docker" / "Caddyfile").write_text("{$DOMAIN} {}\n")
        (origin / ".env.example").write_text("TELEGRAM_BOT_TOKEN=\nDIPLOMACY_BOT_SECRET=\n")
        _git(origin, "add", "-A")
        _git(origin, "commit", "-qm", "base")
        _git(origin, "branch", "vps-split")
        (origin / "README").write_text("main moved on\n")
        _git(origin, "add", "-A")
        _git(origin, "commit", "-qm", "main")
        sha = _git(origin, "rev-parse", "HEAD")

        clone = tmp_path / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--single-branch", "-b", "vps-split", str(origin), str(clone)], check=True
        )
        (clone / ".env").write_text("TELEGRAM_BOT_TOKEN=old\nDIPLOMACY_BOT_SECRET=host-only\n")

        toolkit = tmp_path / "toolkit"
        toolkit.mkdir()
        (toolkit / "deploy_hook.sh").write_bytes((PROJECT_ROOT / "host" / "deploy_hook.sh").read_bytes())
        (toolkit / "upgrade.sh").write_text(
            '#!/bin/sh\nprintf %s "$DIPLOMACY_IMAGE_TAG" > upgraded\n'
        )
        for name in ("deploy_hook.sh", "upgrade.sh"):
            (toolkit / name).chmod(0o755)
        (toolkit / "toolkit.env").write_text(f"DIPLOMACY_DIR={clone}\n")
        reviewed = subprocess.run(
            ["sha256sum", "docker-compose.yml", "docker/Caddyfile"],
            cwd=origin, check=True, capture_output=True, text=True,
        ).stdout
        (toolkit / "reviewed.sha256").write_text(reviewed)
        (toolkit / "installed-from").write_text(sha + "\n")

        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        # A forced command: whatever the client asks, sshd runs the hook with the
        # request in SSH_ORIGINAL_COMMAND and the client's stdin.
        (bin_dir / "ssh").write_text(f'#!/bin/bash\nSSH_ORIGINAL_COMMAND="${{@: -1}}" exec {toolkit}/deploy_hook.sh\n')
        (bin_dir / "ssh").chmod(0o755)
        return {"origin": origin, "clone": clone, "toolkit": toolkit, "bin": bin_dir, "sha": sha}

    def _run_step(
        self, t: dict[str, Path | str], sha: str, token: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        script = _deploy_step_script(_read(WORKFLOWS / "deploy.yml"))
        return subprocess.run(
            ["bash", "-e", "-c", script],
            env={
                "PATH": f"{t['bin']}:/usr/bin:/bin",
                "HOME": str(t["clone"]),
                "TELEGRAM_BOT_TOKEN": token or self.TOKEN,
                "SHA": sha,
                "TARGET": "root@vps",
            },
            capture_output=True, text=True,
        )

    def test_deploys_main_writes_the_token_and_keeps_host_secrets(self, tmp_path: Path) -> None:
        t = self._setup(tmp_path)
        result = self._run_step(t, str(t["sha"]))
        assert result.returncode == 0, result.stderr
        clone = Path(t["clone"])
        assert _git(clone, "rev-parse", "HEAD") == t["sha"]
        assert (clone / "upgraded").read_text() == t["sha"]  # the image tag upgrade.sh pulls
        assert (clone / ".env").read_text().splitlines() == [
            f"TELEGRAM_BOT_TOKEN={self.TOKEN}",
            "DIPLOMACY_BOT_SECRET=host-only",
        ]
        assert self.TOKEN not in result.stdout + result.stderr

    def test_refuses_a_commit_that_is_not_on_main(self, tmp_path: Path) -> None:
        """GitHub serves any commit of the repository network by SHA, forks' and
        pull requests' included; only main's may reach production."""
        t = self._setup(tmp_path)
        origin = Path(t["origin"])
        _git(origin, "checkout", "-q", "-b", "evil")
        (origin / "README").write_text("not reviewed\n")
        _git(origin, "commit", "-qam", "evil")
        evil = _git(origin, "rev-parse", "HEAD")
        _git(origin, "checkout", "-q", "main")
        before = _git(Path(t["clone"]), "rev-parse", "HEAD")
        result = self._run_step(t, evil)
        assert result.returncode == 1
        assert f"{evil} is not on origin/main" in result.stderr
        assert _git(Path(t["clone"]), "rev-parse", "HEAD") == before
        assert not (Path(t["clone"]) / "upgraded").exists()

    @pytest.mark.parametrize("path", ["docker-compose.yml", "docker/Caddyfile"])
    def test_refuses_an_unreviewed_change_to_what_reaches_the_host(self, tmp_path: Path, path: str) -> None:
        t = self._setup(tmp_path)
        origin = Path(t["origin"])
        (origin / path).write_text("volumes: ['/root:/host']\n")
        _git(origin, "commit", "-qam", "widen the mounts")
        sha = _git(origin, "rev-parse", "HEAD")
        result = self._run_step(t, sha)
        assert result.returncode == 3
        assert f"::error::Not deploying {sha}: it changes {path}" in result.stderr
        assert "sudo ./install.sh --toolkit" in result.stderr
        assert not (Path(t["clone"]) / "upgraded").exists()

    def test_refuses_a_reviewed_path_turned_into_a_symlink(self, tmp_path: Path) -> None:
        t = self._setup(tmp_path)
        origin = Path(t["origin"])
        (origin / "docker" / "Caddyfile").unlink()
        (origin / "docker" / "Caddyfile").symlink_to("/root/caddy/Caddyfile")
        _git(origin, "add", "-A")
        _git(origin, "commit", "-qm", "link")
        result = self._run_step(t, _git(origin, "rev-parse", "HEAD"))
        assert result.returncode == 3
        assert "docker/Caddyfile (not a regular file" in result.stderr

    @pytest.mark.parametrize("request_line", ["bash", "deploy", "deploy abc123", "deploy $(id)", "id; deploy x"])
    def test_runs_nothing_but_a_deploy(self, tmp_path: Path, request_line: str) -> None:
        t = self._setup(tmp_path)
        result = subprocess.run(
            [str(Path(t["toolkit"]) / "deploy_hook.sh")],
            input=f"TELEGRAM_BOT_TOKEN={self.TOKEN}\n",
            env={"PATH": "/usr/bin:/bin", "SSH_ORIGINAL_COMMAND": request_line},
            capture_output=True, text=True,
        )
        assert result.returncode == 1
        assert "the only command is: deploy <full 40-hex commit sha>" in result.stderr

    def test_refuses_a_token_that_is_not_a_bot_token(self, tmp_path: Path) -> None:
        t = self._setup(tmp_path)
        result = self._run_step(t, str(t["sha"]), token="x\nDIPLOMACY_BOT_SECRET=mine")
        assert result.returncode == 1
        assert "is not a Telegram bot token" in result.stderr
        assert "TELEGRAM_BOT_TOKEN=old" in (Path(t["clone"]) / ".env").read_text()

    def test_warns_when_the_checkout_changes_the_toolkit(self, tmp_path: Path) -> None:
        t = self._setup(tmp_path)
        origin = Path(t["origin"])
        (origin / "upgrade.sh").write_text("#!/bin/sh\necho changed\n")
        _git(origin, "add", "-A")
        _git(origin, "commit", "-qm", "change upgrade.sh")
        result = self._run_step(t, _git(origin, "rev-parse", "HEAD"))
        assert result.returncode == 0, result.stderr
        assert "::warning::upgrade.sh differs from the installed host toolkit" in result.stdout
        # ...and the installed copy is what ran, not the checkout's.
        assert (Path(t["clone"]) / "upgraded").exists()


class TestAgentShell:
    """Run the real host/agent_shell.sh (the lead agent key's forced command) with
    fake docker, journalctl and curl that log their calls."""

    def _run(self, tmp_path: Path, request: str, stdin: str = "") -> tuple[subprocess.CompletedProcess[str], list[str]]:
        work = tmp_path / "work"
        work.mkdir(exist_ok=True)
        _git(work, "init", "-q")
        toolkit = tmp_path / "toolkit"
        toolkit.mkdir(exist_ok=True)
        (toolkit / "agent_shell.sh").write_bytes((PROJECT_ROOT / "host" / "agent_shell.sh").read_bytes())
        (toolkit / "agent_shell.sh").chmod(0o755)
        (toolkit / "toolkit.env").write_text(f"DIPLOMACY_DIR={work}\n")
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        log = tmp_path / "calls.log"
        for tool in ("docker", "journalctl", "curl"):
            (bin_dir / tool).write_text(f'#!/bin/bash\necho "{tool} $*" >> {log}\n')
            (bin_dir / tool).chmod(0o755)
        result = subprocess.run(
            [str(toolkit / "agent_shell.sh")],
            input=stdin,
            env={"PATH": f"{bin_dir}:/usr/bin:/bin", "SSH_ORIGINAL_COMMAND": request},
            capture_output=True, text=True,
        )
        calls = log.read_text().splitlines() if log.exists() else []
        return result, calls

    def test_sql_runs_as_the_read_only_role_without_meta_commands(self, tmp_path: Path) -> None:
        result, calls = self._run(tmp_path, "sql -tA", stdin="select count(*) from games;\n")
        assert result.returncode == 0, result.stderr
        assert calls == [
            "docker compose exec -T --user postgres postgres psql -X -q -v ON_ERROR_STOP=1 -P pager=off"
            " -t -A -F \t -U diplomacy_agent -d diplomacy_db -c select count(*) from games;"
        ]

    @pytest.mark.parametrize("query", ["\\! id", "select 1; \\copy users to program 'sh'", ""])
    def test_sql_refuses_meta_commands_and_empty_input(self, tmp_path: Path, query: str) -> None:
        result, calls = self._run(tmp_path, "sql", stdin=query)
        assert result.returncode == 2
        assert calls == []

    def test_logs_and_journal_of_this_stack_only(self, tmp_path: Path) -> None:
        result, calls = self._run(tmp_path, "logs diplomacy_api 6h")
        assert result.returncode == 0, result.stderr
        assert calls == ["docker compose logs --no-color --since 6h diplomacy_api"]
        result, calls = self._run(tmp_path, "journal postgres 2d")
        assert result.returncode == 0, result.stderr
        assert calls[-1] == "journalctl --no-pager -o short-iso --since -2d CONTAINER_NAME=diplomacy-postgres-1"

    @pytest.mark.parametrize(
        "request_line",
        ["bash", "logs p2p-downloader_bot", "logs diplomacy_api 1h;id", "logs diplomacy_api $(id)",
         "journal heimot-kampanja", "status now", "sql --set=x", "logs diplomacy_api 1h extra"],
    )
    def test_refuses_everything_else(self, tmp_path: Path, request_line: str) -> None:
        result, calls = self._run(tmp_path, request_line)
        assert result.returncode == 2
        assert result.stderr.startswith("agent_shell: ") or "agent_shell: " in result.stderr
        assert calls == []

    def test_help_lists_the_commands(self, tmp_path: Path) -> None:
        result, _ = self._run(tmp_path, "")
        assert result.returncode == 0
        for cmd in ("status", "health", "logs <service>", "journal <service>", "sql [-tA]", "backup-status"):
            assert cmd in result.stdout, cmd


class TestAgentDbRole:
    """Apply host/agent_db_role.sql to the test database inside a transaction that is
    rolled back, then query as the role. Needs a role that may CREATE ROLE (CI's
    superuser test role)."""

    def test_reads_game_data_but_no_personal_secret_and_writes_nothing(self, temp_db) -> None:
        from sqlalchemy import exc, text

        with temp_db.connect() as conn:
            can = conn.execute(
                text("select rolsuper or rolcreaterole from pg_roles where rolname = current_user")
            ).scalar()
            if not can:
                pytest.skip("the test database role may not CREATE ROLE (CI's may)")
            conn.rollback()  # end the query's autobegun transaction
            trans = conn.begin()
            try:
                conn.exec_driver_sql((PROJECT_ROOT / "host" / "agent_db_role.sql").read_text())
                conn.exec_driver_sql("SET ROLE diplomacy_agent")
                assert conn.execute(text("select count(nickname) >= 0 from users")).scalar() is True
                assert conn.execute(text("select count(*) >= 0 from games")).scalar() is True
                denied = [
                    "select email from users",
                    "select password_hash from users",
                    "select * from password_reset_tokens",
                    "select code from link_codes",
                    "select join_password_hash from games",
                    "select text from messages",
                    "select payload from bot_outbox",
                    "select response_json from idempotency_keys",
                    "delete from feedback",
                ]
                for statement in denied:
                    nested = conn.begin_nested()
                    with pytest.raises(exc.ProgrammingError, match="permission denied"):
                        conn.execute(text(statement))
                    nested.rollback()
            finally:
                trans.rollback()


class TestHostToolkitInstall:
    def test_install_records_the_reviewed_files_and_installs_the_root_scripts(self) -> None:
        script = _read(PROJECT_ROOT / "install.sh")
        assert "TOOLKIT=/usr/local/lib/diplomacy" in script
        assert "sha256sum docker-compose.yml docker/Caddyfile" in script
        assert "host/deploy_hook.sh host/agent_shell.sh" in script
        assert '$SUDO "$TOOLKIT/backup.sh" --install' in script  # the job runs the toolkit's copy
        assert "--toolkit) mode=toolkit" in script
        # Every script the deploy hook warns about is one install.sh installs.
        hook = _read(PROJECT_ROOT / "host" / "deploy_hook.sh")
        for name in ("upgrade.sh", "ensure_env.sh", "backup.sh", "host/agent_db_role.sql"):
            assert name in hook and name in script, name


class TestNoHostDetailsInTheRepository:
    """The production host's address lives in the VPS_HOST secret and the maintainer's
    git-ignored CLAUDE.local.md, never in a tracked file: a clone must not learn it."""

    def test_no_tracked_file_names_a_public_ipv4_address(self) -> None:
        tracked = subprocess.run(
            ["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.split("\0")
        ipv4 = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.])")
        found = []
        for name in tracked:
            path = REPO_ROOT / name
            # Docs, scripts, workflows and config; code and tests use made-up addresses.
            if not name or name.startswith(("src/", "tests/", "frontend/src/")) or not path.is_file():
                continue
            if name.endswith(("package-lock.json", ".svg", ".png", ".pdf")):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for m in ipv4.finditer(text):
                a, b = int(m.group(1)), int(m.group(2))
                octets = [int(g) for g in m.groups()]
                if max(octets) > 255 or a in (0, 10, 127) or (a == 192 and b == 168):
                    continue
                if (a == 172 and 16 <= b <= 31) or (a == 169 and b == 254):
                    continue
                if a == 203 and b == 0:  # TEST-NET-3 documentation range
                    continue
                found.append(f"{name}: {m.group(0)}")
        assert found == []

    def test_claude_local_md_is_git_ignored(self) -> None:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "CLAUDE.local.md"], cwd=REPO_ROOT, check=False
        )
        assert result.returncode == 0

