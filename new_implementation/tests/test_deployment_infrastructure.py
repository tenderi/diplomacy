"""Shape checks on the split deployment (VPS control layer + home game layer).

Intentionally string-presence checks on the compose files, env templates,
host scripts and the deploy workflow. They do not replace running the stacks
(F3 in ``fix_plan.md`` is that), but they catch the coarse regressions that
matter here:

- a game-layer secret (database URL, JWT secret, admin token) creeping into the
  VPS env template -- the whole point of the split is that the public host
  holds as little as possible;
- the API being published on a bare ``8000:8000`` (every interface) instead of
  loopback + the tunnel address;
- the bot image growing dependencies beyond ``requirements-bot.txt``;
- the deploy workflow losing its gate, running on a red Test Suite, or passing
  secrets on a remote command line where ``ps`` would show them.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
REPO_ROOT = PROJECT_ROOT.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


def _read(path: Path) -> str:
    assert path.exists(), f"{path} is missing"
    return path.read_text()


# ---------------------------------------------------------------------------
# Env templates: what each host is allowed to know
# ---------------------------------------------------------------------------


class TestEnvTemplates:
    GAME_LAYER_ONLY = ("SQLALCHEMY_DATABASE_URL", "POSTGRES_PASSWORD", "DIPLOMACY_JWT_SECRET", "DIPLOMACY_ADMIN_TOKEN")

    def test_control_template_holds_no_game_layer_secret(self) -> None:
        control = _read(PROJECT_ROOT / ".env.control.example")
        keys = {line.split("=", 1)[0] for line in control.splitlines() if "=" in line and not line.startswith("#")}
        leaked = [k for k in self.GAME_LAYER_ONLY if k in keys]
        assert not leaked, f"game-layer secret(s) in the VPS env template: {leaked}"

    def test_control_template_has_exactly_the_bot_secrets(self) -> None:
        control = _read(PROJECT_ROOT / ".env.control.example")
        assert re.search(r"^TELEGRAM_BOT_TOKEN=", control, re.M)
        assert re.search(r"^DIPLOMACY_BOT_SECRET=", control, re.M)

    def test_home_template_has_the_matching_bot_secret(self) -> None:
        home = _read(PROJECT_ROOT / ".env.example")
        assert re.search(r"^DIPLOMACY_BOT_SECRET=", home, re.M)
        assert re.search(r"^DIPLOMACY_JWT_SECRET=", home, re.M)


# ---------------------------------------------------------------------------
# Compose files
# ---------------------------------------------------------------------------


class TestComposeFiles:
    def test_api_is_never_published_on_every_interface(self) -> None:
        home = _read(PROJECT_ROOT / "docker-compose.yml")
        assert not re.search(r'^\s*-\s*"?8000:8000"?\s*$', home, re.M), "bare 8000:8000 publishes the API to the world"
        assert "127.0.0.1:8000:8000" in home
        assert "${WG_IP:-10.8.0.2}:8000:8000" in home

    def test_control_stack_is_bot_and_web_only(self) -> None:
        control = _read(PROJECT_ROOT / "docker-compose.control.yml")
        assert "docker/bot.Dockerfile" in control
        assert "docker/web.Dockerfile" in control
        assert "postgres" not in control.lower().replace("postgres_password", "")
        assert "TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:?" in control
        assert "DIPLOMACY_BOT_SECRET=${DIPLOMACY_BOT_SECRET:?" in control
        assert "bot_data:/data" in control  # the durable queue survives rebuilds

    def test_bot_image_installs_only_the_bot_requirements(self) -> None:
        dockerfile = _read(PROJECT_ROOT / "docker" / "bot.Dockerfile")
        assert "requirements-bot.txt" in dockerfile
        assert not re.search(r"pip install .*\brequirements\.txt", dockerfile), "the bot image must not pull the API's deps"


# ---------------------------------------------------------------------------
# Host scripts
# ---------------------------------------------------------------------------


class TestHostScripts:
    @pytest.mark.parametrize("script", ["install_home.sh", "install_vps.sh", "upgrade.sh", "upgrade_control.sh"])
    def test_script_parses(self, script: str) -> None:
        path = PROJECT_ROOT / script
        assert path.exists(), f"{script} is missing"
        subprocess.run(["bash", "-n", str(path)], check=True)

    def test_upgrade_control_tolerates_a_detached_head(self) -> None:
        """The deploy workflow checks out the exact SHA the Test Suite passed on
        (a detached HEAD) before calling this script; a bare ``git pull`` there
        fails with "not on a branch" and, under ``set -e``, aborts the deploy."""
        script = _read(PROJECT_ROOT / "upgrade_control.sh")
        assert "git symbolic-ref -q HEAD" in script
        assert "git pull --ff-only" in script


# ---------------------------------------------------------------------------
# Deploy workflow (VPS control layer)
# ---------------------------------------------------------------------------


class TestDeployControlWorkflow:
    @pytest.fixture
    def workflow(self) -> str:
        return _read(WORKFLOWS / "deploy-control.yml")

    def test_only_runs_after_test_suite_passes_and_when_enabled(self, workflow: str) -> None:
        assert 'workflows: ["Test Suite"]' in workflow
        assert "workflow_run.conclusion == 'success'" in workflow
        assert "vars.DEPLOY_CONTROL_ENABLED == 'true'" in workflow

    def test_injects_both_bot_secrets_from_github_secrets(self, workflow: str) -> None:
        assert "${{ secrets.TELEGRAM_BOT_TOKEN }}" in workflow
        assert "${{ secrets.DIPLOMACY_BOT_SECRET }}" in workflow
        assert "set_var TELEGRAM_BOT_TOKEN" in workflow
        assert "set_var DIPLOMACY_BOT_SECRET" in workflow

    def test_secrets_travel_on_stdin_not_the_remote_command_line(self, workflow: str) -> None:
        # The remote script reads them with `read`; the ssh argument list only
        # carries the SHA and the repo dir.
        assert "bash -s" in workflow
        assert "IFS= read -r TELEGRAM_BOT_TOKEN" in workflow
        assert not re.search(r'ssh .*TELEGRAM_BOT_TOKEN=', workflow)

    def test_pins_the_host_key_instead_of_scanning(self, workflow: str) -> None:
        assert "${{ secrets.VPS_HOST_KEY }}" in workflow
        assert "ssh-keyscan" not in re.sub(r"#.*", "", workflow)  # allowed only in the comment

    def test_deploys_the_tested_sha_and_runs_the_upgrade_script(self, workflow: str) -> None:
        assert "git checkout --quiet --detach" in workflow
        assert "./upgrade_control.sh" in workflow
        assert "concurrency:" in workflow

    def test_no_aws_remains(self) -> None:
        assert not (WORKFLOWS / "deploy.yml").exists(), "the AWS deploy workflow was removed in v2.7.80"
        assert not (PROJECT_ROOT / "infra" / "terraform").exists()
        for path in WORKFLOWS.glob("*.yml"):
            assert "aws-actions" not in path.read_text(), path
