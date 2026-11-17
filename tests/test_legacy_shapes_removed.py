"""#464: the legacy API and bot shapes 4.0.0 removed stay removed.

The ``bot_secret`` body field and the replay of writes the bot queued before the
upgrade are in ``test_bot_secret_header.py``.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

import server.api
from server._api_module import app
from server.telegram_bot import games
from tests.conftest import _get_db_url
from tests.test_bot_commands import _command, _run


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _new_game(client: TestClient) -> str:
    reg = client.post("/auth/register", json={"email": f"lg_{uuid.uuid4().hex}@example.com", "password": "testpass123"})
    bearer = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    resp = client.post("/games/create", json={"map_name": "standard"}, headers=bearer)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["game_id"])


def _paths() -> set[str]:
    return set(app.openapi()["paths"])


def test_the_removed_routes_are_not_mounted() -> None:
    paths = _paths()
    assert "/games/{game_id}/legal_orders/{power}" in paths  # the replacement
    assert "/games/{game_id}/legal_orders/{power}/{unit}" not in paths
    assert "/games/{game_id}/observer_state" not in paths


@pytest.mark.database
@pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
def test_observer_state_is_a_404_and_state_answers(client: TestClient) -> None:
    game_id = _new_game(client)
    assert client.get(f"/games/{game_id}/state").status_code == 200
    gone = client.get(f"/games/{game_id}/observer_state")
    assert (gone.status_code, gone.json()) == (404, {"detail": "Not Found"})


def test_server_api_no_longer_re_exports_the_app() -> None:
    with pytest.raises(AttributeError):
        server.api.app  # noqa: B018


def test_register_only_points_to_start() -> None:
    """/start registers; /register answers with one line saying so and calls nothing."""
    with patch("server.telegram_bot.games.ensure_registered") as ensure, \
            patch("server.telegram_bot.games.api_post") as post:
        reply = _run(games.register, *_command(text="/register"))
    assert reply == "/register is gone: /start registers you."
    ensure.assert_not_called()
    post.assert_not_called()


@pytest.mark.database
@pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
def test_the_season_and_phase_columns_round_trip(client: TestClient) -> None:
    """The listing derives season and phase from the board; a downgrade re-adds
    the two dropped columns and backfills them from ``state_json``."""
    game_id = _new_game(client)
    listed = next(g for g in client.get("/games").json()["games"] if str(g["game_id"]) == str(game_id))
    assert (listed["current_season"], listed["current_phase"]) == ("Spring", "Movement")

    root = Path(__file__).resolve().parent.parent
    cwd = os.getcwd()
    os.chdir(root)
    engine = create_engine(_get_db_url())
    try:
        cfg = Config(str(root / "alembic.ini"))
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "c7e3f4a5b6c7-1")
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT current_season, current_phase FROM games WHERE game_id = :g"), {"g": str(game_id)}
                ).one()
            assert tuple(row) == ("Spring", "Movement")
        finally:
            command.upgrade(cfg, "head")
        columns = {c["name"] for c in inspect(engine).get_columns("games")}
        assert {"current_season", "current_phase"} & columns == set()
    finally:
        engine.dispose()
        os.chdir(cwd)
