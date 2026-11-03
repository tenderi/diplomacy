"""A group's ``notification_level`` (all / important / none) decides which of the
game's automatic posts reach it; posts a player sent themselves always do."""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from server.api import ADMIN_TOKEN, app
from server.api import shared as api_shared
from tests.reliability_helpers import OutboxProbe
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

BOT = {"X-Bot-Secret": BOT_SECRET}
GROUP = "-1009876544"
ADMIN_LINK = {**BOT, "X-Admin-Token": ADMIN_TOKEN}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _linked_game(client: TestClient, level: str) -> tuple[str, str]:
    creator = _telegram_user(client, "Levels")
    game_id = str(client.post("/games/create", json=_as(creator, map_name="standard"), headers=BOT).json()["game_id"])
    assert client.post(f"/games/{game_id}/join", json=_as(creator, power="FRANCE")).status_code == 200
    assert client.post(f"/games/{game_id}/channel/link", json={"channel_id": GROUP}, headers=ADMIN_LINK).status_code == 200
    resp = client.put(f"/games/{game_id}/channel/settings", json={"notification_level": level}, headers=BOT)
    assert resp.status_code == 200, resp.text
    return game_id, creator


def _group_posts(probe: OutboxProbe) -> list[str]:
    return [r["message"] for r in probe.rows() if str(r["telegram_id"]) == GROUP]


def _what_goes_out(client: TestClient, level: str) -> dict[str, bool]:
    game_id, creator = _linked_game(client, level)
    went: dict[str, bool] = {}

    joiner = _telegram_user(client, "Joiner")
    with OutboxProbe() as probe:
        assert client.post(f"/games/{game_id}/join", json=_as(joiner, power="ITALY")).status_code == 200
    went["join"] = any("has joined game" in m for m in _group_posts(probe))

    with OutboxProbe() as probe:
        api_shared._send_deadline_reminder(game_id, int(game_id), timedelta(minutes=10))
    went["reminder"] = any("are due in 10 minutes" in m for m in _group_posts(probe))

    with OutboxProbe() as probe:
        api_shared._post_turn_to_channel(game_id, "Spring moved.")
    went["turn"] = any("Turn Processed" in m for m in _group_posts(probe))

    with OutboxProbe() as probe:
        resp = client.post(f"/games/{game_id}/channel/broadcast", headers=BOT, json={"telegram_id": creator, "message": "hello all"})
        assert resp.status_code == 200, resp.text
    went["broadcast"] = any("hello all" in m for m in _group_posts(probe))

    with OutboxProbe() as probe:
        api_shared.post_to_game_group(game_id, "The game has ended", api_shared.GroupPost.IMPORTANT)
    went["ending"] = _group_posts(probe) == ["The game has ended"]
    return went


@pytest.mark.parametrize(
    "level, expected",
    [
        ("all", {"join": True, "reminder": True, "turn": True, "broadcast": True, "ending": True}),
        ("important", {"join": False, "reminder": False, "turn": True, "broadcast": True, "ending": True}),
        ("none", {"join": False, "reminder": False, "turn": False, "broadcast": True, "ending": False}),
    ],
)
def test_the_level_decides_which_posts_reach_the_group(client: TestClient, level: str, expected: dict[str, bool]) -> None:
    assert _what_goes_out(client, level) == expected


def test_an_unrecognised_stored_level_posts_everything(client: TestClient) -> None:
    game_id, _ = _linked_game(client, "all")
    api_shared.db_service.update_game_channel_settings(game_id, {"notification_level": "loud"})
    with OutboxProbe() as probe:
        api_shared.post_to_game_group(game_id, "x", api_shared.GroupPost.ROUTINE)
    assert _group_posts(probe) == ["x"]


def test_an_unknown_level_is_a_422_naming_the_three(client: TestClient) -> None:
    game_id, _ = _linked_game(client, "all")
    resp = client.put(f"/games/{game_id}/channel/settings", json={"notification_level": "loud"}, headers=BOT)
    assert resp.status_code == 422
    assert "'all', 'important' or 'none'" in resp.json()["detail"][0]["msg"]
