"""The probes ``upgrade.sh``, nginx and the web container's healthcheck rely on, and
``/version``, which must agree with ``pyproject.toml`` and ``frontend/package.json``."""
from __future__ import annotations

import json
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api.shared import db_service

ROOT = Path(__file__).parent.parent

pytestmark = pytest.mark.unit


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize("path", ["/health", "/healthz"])
def test_probes_check_the_database(client: TestClient, path: str) -> None:
    with patch.object(db_service, "execute_query", return_value=None) as query:
        assert client.get(path).json() == {"status": "ok"}
    query.assert_called_once_with("SELECT 1")
    with patch.object(db_service, "execute_query", side_effect=RuntimeError("db down")):
        assert client.get(path).status_code == 500


def test_no_anonymous_environment_dump(client: TestClient) -> None:
    """``/health/environment`` told anyone the interpreter path, working directory and
    which secrets were set (and always said "error": its database import was broken)."""
    assert client.get("/health/environment").status_code == 404


def test_the_root_says_where_to_look_and_there_is_no_dashboard(client: TestClient) -> None:
    """The systemd-era admin page (``/dashboard``) could not authenticate and drove
    ``systemctl``/``journalctl``, which the containers do not have; it is gone."""
    root = client.get("/", follow_redirects=False)
    assert root.status_code == 200 and "Diplomacy Game Server API" in root.text
    for path in ("/dashboard", "/dashboard/api/services/status", "/dashboard/static/dashboard.js"):
        assert client.get(path, headers={"X-Admin-Token": "x"}).status_code == 404, path


def test_the_three_version_numbers_agree(client: TestClient) -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    package = json.loads((ROOT / "frontend" / "package.json").read_text())["version"]
    assert client.get("/version").json() == {"version": pyproject}
    assert package == pyproject
