"""
Tests for deployment scripts and Terraform user_data.

These tests verify the shape of the deployment artifacts:
- user_data.sh declares both systemd units, the right Nginx config, etc.
- deploy.sh and refresh-env.sh are syntactically valid and contain the
  steps we expect.
- The Terraform module pins the right versions and OIDC trust scope.

These are intentionally string-presence checks. They don't replace real
deploy-time verification (CI's `/health` probe in deploy.yml does that)
but they catch coarse regressions like "someone removed the systemd unit
for the bot" or "OIDC trust scope was widened to all branches".
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent
INFRA = PROJECT_ROOT / "infra"
TERRAFORM_DIR = INFRA / "terraform"
SCRIPTS_DIR = INFRA / "scripts"


@pytest.fixture
def user_data() -> str:
    path = TERRAFORM_DIR / "user_data.sh"
    if not path.exists():
        pytest.skip(f"{path} not found")
    return path.read_text()


@pytest.fixture
def deploy_script_path() -> Path:
    return SCRIPTS_DIR / "deploy.sh"


@pytest.fixture
def refresh_env_path() -> Path:
    return SCRIPTS_DIR / "refresh-env.sh"


# ---------------------------------------------------------------------------
# user_data.sh
# ---------------------------------------------------------------------------


class TestSystemdUnitsInUserData:
    """The bootstrap installs both diplomacy-api.service and diplomacy-bot.service."""

    def test_api_service_block_exists(self, user_data: str) -> None:
        assert "diplomacy-api.service" in user_data
        assert "Description=Diplomacy FastAPI server" in user_data

    def test_bot_service_block_exists(self, user_data: str) -> None:
        assert "diplomacy-bot.service" in user_data
        assert "Description=Diplomacy Telegram bot" in user_data

    def test_api_service_runs_uvicorn(self, user_data: str) -> None:
        match = re.search(
            r"Description=Diplomacy FastAPI server.*?ExecStart=([^\n]+)",
            user_data,
            re.DOTALL,
        )
        assert match, "Could not find API service block"
        execstart = match.group(1)
        assert "uvicorn" in execstart, f"API ExecStart should use uvicorn: {execstart}"
        assert "server._api_module:app" in execstart, (
            f"API ExecStart should reference server._api_module:app: {execstart}"
        )

    def test_bot_service_runs_python_module(self, user_data: str) -> None:
        match = re.search(
            r"Description=Diplomacy Telegram bot.*?ExecStart=([^\n]+)",
            user_data,
            re.DOTALL,
        )
        assert match, "Could not find bot service block"
        execstart = match.group(1)
        assert "-m server.telegram_bot" in execstart, (
            f"Bot ExecStart should run `python -m server.telegram_bot`: {execstart}"
        )

    def test_both_services_have_environment_file(self, user_data: str) -> None:
        # Both [Service] sections should declare an EnvironmentFile pointing
        # at the SSM-populated .env.
        assert user_data.count("EnvironmentFile=$APP_DIR/.env") == 2, (
            "Both services should set EnvironmentFile=$APP_DIR/.env"
        )

    def test_both_services_run_as_app_user(self, user_data: str) -> None:
        # APP_USER is set to `diplomacy` at the top of user_data.sh — the
        # systemd template stays in $APP_USER form so the value flows from
        # one place.
        assert user_data.count("User=$APP_USER") == 2, (
            "Both services should run as the $APP_USER (diplomacy)"
        )
        assert 'APP_USER="diplomacy"' in user_data

    def test_services_have_restart_policy(self, user_data: str) -> None:
        assert user_data.count("Restart=always") == 2
        # RestartSec values may differ between API (3s) and bot (5s).
        assert user_data.count("RestartSec=") == 2


# ---------------------------------------------------------------------------
# Nginx reverse proxy
# ---------------------------------------------------------------------------


class TestNginxConfiguration:
    """Nginx config baked into user_data.sh."""

    def test_nginx_server_block_exists(self, user_data: str) -> None:
        assert "server {" in user_data
        assert "listen 80 default_server" in user_data

    def test_nginx_proxies_to_local_api(self, user_data: str) -> None:
        # Accept either explicit-loopback form. We use 127.0.0.1 to avoid
        # DNS resolution edge cases on minimal Ubuntu images.
        assert (
            "proxy_pass http://127.0.0.1:8000" in user_data
            or "proxy_pass http://localhost:8000" in user_data
        ), "Nginx should proxy to the local uvicorn on port 8000"

    def test_nginx_does_not_expose_dashboard(self, user_data: str) -> None:
        # docs/specs/dashboard.md is design-only. The Nginx config should
        # not pretend the dashboard exists.
        assert "location /dashboard" not in user_data


# ---------------------------------------------------------------------------
# user_data.sh — overall shape
# ---------------------------------------------------------------------------


class TestUserDataScript:
    def test_user_data_uses_deadsnakes_for_python_3_14(self, user_data: str) -> None:
        assert "ppa:deadsnakes/ppa" in user_data
        assert "python3.14" in user_data

    def test_user_data_delegates_env_writing_to_refresh_script(
        self, user_data: str
    ) -> None:
        # Single source of truth: bootstrap and rotation both go through
        # refresh-env.sh.
        assert "refresh-env.sh" in user_data

    def test_user_data_syntax_valid(self) -> None:
        path = TERRAFORM_DIR / "user_data.sh"
        if not path.exists():
            pytest.skip(f"{path} not found")
        result = subprocess.run(
            ["bash", "-n", str(path)], capture_output=True, text=True
        )
        assert result.returncode == 0, f"user_data.sh has syntax errors: {result.stderr}"


# ---------------------------------------------------------------------------
# infra/scripts/deploy.sh — invoked by SSM send-command on every deploy
# ---------------------------------------------------------------------------


class TestDeployScript:
    def test_exists_and_executable(self, deploy_script_path: Path) -> None:
        assert deploy_script_path.is_file(), f"{deploy_script_path} should exist"
        assert os.access(deploy_script_path, os.X_OK), (
            f"{deploy_script_path} should be executable"
        )

    def test_has_bash_shebang(self, deploy_script_path: Path) -> None:
        assert deploy_script_path.read_text().startswith("#!/bin/bash")

    def test_performs_git_reset_to_target_ref(self, deploy_script_path: Path) -> None:
        content = deploy_script_path.read_text()
        assert "git -C" in content and "fetch" in content
        # Hard reset is intentional — we want to overwrite any drift on the
        # instance, including local edits made via SSM session.
        assert "reset --hard" in content

    def test_runs_alembic_migration(self, deploy_script_path: Path) -> None:
        content = deploy_script_path.read_text()
        assert "alembic upgrade head" in content

    def test_restarts_both_services(self, deploy_script_path: Path) -> None:
        content = deploy_script_path.read_text()
        assert "systemctl restart diplomacy-api.service" in content
        assert "systemctl restart diplomacy-bot.service" in content

    def test_syntax_valid(self, deploy_script_path: Path) -> None:
        result = subprocess.run(
            ["bash", "-n", str(deploy_script_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"deploy.sh has syntax errors: {result.stderr}"


# ---------------------------------------------------------------------------
# infra/scripts/refresh-env.sh — re-reads SSM and rewrites /opt/diplomacy/.env
# ---------------------------------------------------------------------------


class TestRefreshEnvScript:
    def test_exists_and_executable(self, refresh_env_path: Path) -> None:
        assert refresh_env_path.is_file()
        assert os.access(refresh_env_path, os.X_OK)

    def test_reads_all_expected_ssm_keys(self, refresh_env_path: Path) -> None:
        content = refresh_env_path.read_text()
        expected_keys = [
            "telegram_bot_token",
            "db_password",
            "jwt_secret",
            "admin_token",
            "bot_secret",
        ]
        for key in expected_keys:
            assert key in content, f"refresh-env.sh should fetch {key} from SSM"

    def test_writes_env_with_correct_keys(self, refresh_env_path: Path) -> None:
        content = refresh_env_path.read_text()
        # The env file must give the application what it needs.
        for var in [
            "SQLALCHEMY_DATABASE_URL",
            "TELEGRAM_BOT_TOKEN",
            "DIPLOMACY_JWT_SECRET",
            "DIPLOMACY_ADMIN_TOKEN",
            "DIPLOMACY_BOT_SECRET",
            "PYTHONPATH",
        ]:
            assert var in content, f"refresh-env.sh should write {var} to .env"

    def test_refuses_when_db_password_missing(self, refresh_env_path: Path) -> None:
        # A missing db_password is unrecoverable — the env file would be
        # broken. The script must bail loudly rather than write a half-broken
        # .env.
        content = refresh_env_path.read_text()
        assert (
            "ERROR" in content and "db_password" in content
        ), "refresh-env.sh should refuse to write .env if db_password is missing"

    def test_syntax_valid(self, refresh_env_path: Path) -> None:
        result = subprocess.run(
            ["bash", "-n", str(refresh_env_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"refresh-env.sh has syntax errors: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# Terraform module — version pins and security-sensitive policy
# ---------------------------------------------------------------------------


class TestTerraformConfiguration:
    def test_required_terraform_version_is_1_10_plus(self) -> None:
        versions = (TERRAFORM_DIR / "versions.tf").read_text()
        assert 'required_version = ">= 1.10' in versions, (
            "Terraform pin should be >= 1.10 (for S3 native locking)"
        )

    def test_aws_provider_pinned_to_v6(self) -> None:
        versions = (TERRAFORM_DIR / "versions.tf").read_text()
        assert 'version = "~> 6.0"' in versions

    def test_s3_backend_uses_native_lockfile(self) -> None:
        versions = (TERRAFORM_DIR / "versions.tf").read_text()
        assert "use_lockfile = true" in versions
        assert "encrypt      = true" in versions, "Backend state should be encrypted"

    def test_default_instance_type_is_free_tier(self) -> None:
        variables = (TERRAFORM_DIR / "variables.tf").read_text()
        # t3.micro is the free-tier and post-free-tier cheap default.
        assert 'default     = "t3.micro"' in variables

    def test_ami_filter_targets_ubuntu_24_04(self) -> None:
        instance = (TERRAFORM_DIR / "instance.tf").read_text()
        assert "ubuntu-noble-24.04-amd64-server" in instance

    def test_imdsv2_required(self) -> None:
        instance = (TERRAFORM_DIR / "instance.tf").read_text()
        assert 'http_tokens                 = "required"' in instance, (
            "Instance should require IMDSv2"
        )

    def test_oidc_trust_scoped_to_specific_repo_branches(self) -> None:
        iam = (TERRAFORM_DIR / "iam.tf").read_text()
        # The trust policy must not be wide-open. It should restrict to the
        # specific repo:branch combinations declared in variables.
        assert "github_deploy_branches" in iam
        assert "refs/heads/" in iam
        assert "token.actions.githubusercontent.com:sub" in iam

    def test_oidc_audience_locked_to_sts(self) -> None:
        iam = (TERRAFORM_DIR / "iam.tf").read_text()
        assert "token.actions.githubusercontent.com:aud" in iam
        assert '"sts.amazonaws.com"' in iam

    def test_deploy_role_can_only_send_command_to_diplomacy_instance(self) -> None:
        iam = (TERRAFORM_DIR / "iam.tf").read_text()
        # The send-command action must be resource-scoped to the instance,
        # not "*". Allowing "*" would let the deploy workflow target any
        # EC2 instance in the account.
        send_block = re.search(
            r'sid\s*=\s*"SendCommandToDiplomacyInstance".*?resources\s*=\s*\[(.*?)\]',
            iam,
            re.DOTALL,
        )
        assert send_block, "Could not find SendCommandToDiplomacyInstance statement"
        resources = send_block.group(1)
        assert "aws_instance.diplomacy.arn" in resources
        assert '"*"' not in resources, (
            "ssm:SendCommand resource should not be '*' — scope it to the instance"
        )


# ---------------------------------------------------------------------------
# Deploy workflow
# ---------------------------------------------------------------------------


class TestDeployWorkflow:
    @pytest.fixture
    def deploy_yml(self) -> str:
        path = PROJECT_ROOT.parent / ".github" / "workflows" / "deploy.yml"
        if not path.exists():
            pytest.skip(f"{path} not found")
        return path.read_text()

    def test_uses_oidc_id_token_permission(self, deploy_yml: str) -> None:
        assert "id-token: write" in deploy_yml

    def test_only_runs_after_test_suite_passes(self, deploy_yml: str) -> None:
        assert 'workflows: ["Test Suite"]' in deploy_yml
        assert "workflow_run.conclusion == 'success'" in deploy_yml

    def test_invokes_deploy_script_with_target_sha(self, deploy_yml: str) -> None:
        assert "/opt/diplomacy/new_implementation/infra/scripts/deploy.sh" in deploy_yml

    def test_concurrency_prevents_overlap(self, deploy_yml: str) -> None:
        assert "concurrency:" in deploy_yml
        assert "deploy-prod" in deploy_yml
