"""A draw or a concession tells the other players (G3a).

Filling in G3's notification matrix turned up two events with no notification at
all. `GameService.submit_draw_vote` finalizes the game **inline** the moment quorum
is reached and returns the outcome only to the power that cast the deciding vote;
because the game is then `COMPLETED`, the deadline scheduler skips it
(`get_games_with_deadlines_and_active_status`), so no later turn-processed fan-out
covered for it. A game could end by agreement and six of seven players find out by
refreshing. A concession was the same shape: a power's units come off the board and
nobody is told.

These were filed rather than fixed during G3, whose scope was the `process_turn`
drift, and are fixed here.
"""
from __future__ import annotations

import itertools
import time
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared

pytestmark = [pytest.mark.integration, pytest.mark.database]

POWERS = ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"]
_seq = itertools.count(1)


def _register(client: TestClient, tag: str) -> tuple[dict, str]:
    stamp = f"{int(time.time() * 1000000)}_{tag}_{next(_seq)}"
    telegram_id = str(abs(hash(stamp)) % 10**9)
    resp = client.post(
        "/auth/register",
        json={"email": f"dc_{stamp}@example.com", "password": "testpass123"},
    )
    if resp.status_code != 200:
        pytest.skip("Database not available for notification test")
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    user_id = int(client.get("/auth/me", headers=headers).json()["id"])
    api_shared.db_service.set_user_telegram_id(user_id, telegram_id)
    return headers, telegram_id


def _seeded_game(client: TestClient) -> tuple[str, list[tuple[dict, str]]]:
    """A game with all seven powers held by users with linked telegram_ids."""
    users = [_register(client, p) for p in POWERS]
    resp = client.post(
        "/games/create",
        json={"map_name": "standard", "initial_phase": "Movement"},
        headers=users[0][0],
    )
    assert resp.status_code == 200, resp.text
    game_id = str(resp.json()["game_id"])
    for power, (headers, _tg) in zip(POWERS, users):
        # `game_id` is sent explicitly even though G6 made it optional: this file
        # tests notifications, and depending on that change would couple it to
        # merge order for no benefit. G6's own tests cover the optional form.
        r = client.post(
            f"/games/{game_id}/join",
            json={"game_id": int(game_id), "power": power},
            headers=headers,
        )
        assert r.status_code == 200, f"join {power}: {r.text}"
    return game_id, users


def _recipients(mock: Any) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for call in mock.call_args_list:
        payload = call.kwargs.get("json") or {}
        if "telegram_id" in payload:
            out.setdefault(str(payload["telegram_id"]), []).append(payload.get("message", ""))
    return out


def test_a_non_final_draw_vote_is_announced_to_the_others() -> None:
    """One yes-vote out of seven does not end the game, but is still news.

    A draw is the one outcome every power holds a veto over, so learning that one
    is being negotiated should not require running `/status`.
    """
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    voter_headers, voter_tg = users[0]

    with patch("server.api.shared.requests.post") as mock_post:
        resp = client.post(
            f"/games/{game_id}/draw_vote",
            json={"power": POWERS[0], "vote": True},
            headers=voter_headers,
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["quorum_reached"] is False

    got = _recipients(mock_post)
    everyone = {tg for _h, tg in users}
    assert got, "a draw vote notified nobody (the G3a bug)"
    assert set(got) == everyone - {voter_tg}, "wrong recipients for a draw vote"
    messages = [m for msgs in got.values() for m in msgs]
    assert all(POWERS[0] in m and "draw" in m.lower() for m in messages), messages
    assert any("1/7" in m for m in messages), messages


def test_reaching_draw_quorum_tells_everyone_the_game_ended() -> None:
    """The headline G3a fix: a game ending by agreement must not be silent."""
    client = TestClient(app)
    game_id, users = _seeded_game(client)

    # Six votes, then the seventh completes quorum.
    for power, (headers, _tg) in list(zip(POWERS, users))[:-1]:
        with patch("server.api.shared.requests.post"):
            r = client.post(
                f"/games/{game_id}/draw_vote",
                json={"power": power, "vote": True},
                headers=headers,
            )
        assert r.status_code == 200, r.text
        assert r.json()["quorum_reached"] is False, power

    last_headers, last_tg = users[-1]
    with patch("server.api.shared.requests.post") as mock_post:
        resp = client.post(
            f"/games/{game_id}/draw_vote",
            json={"power": POWERS[-1], "vote": True},
            headers=last_headers,
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["quorum_reached"] is True
    assert resp.json()["game_status"] == "COMPLETED"

    got = _recipients(mock_post)
    everyone = {tg for _h, tg in users}
    assert set(got) == everyone - {last_tg}, (
        "the six players who did not cast the deciding vote were not told the game ended"
    )
    messages = [m for msgs in got.values() for m in msgs]
    assert any("ended" in m for m in messages), messages


def test_conceding_tells_the_remaining_players() -> None:
    """A power's units come off the board; that used to be invisible."""
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    conceder_headers, conceder_tg = users[2]

    with patch("server.api.shared.requests.post") as mock_post:
        resp = client.post(
            f"/games/{game_id}/concede",
            json={"power": POWERS[2]},
            headers=conceder_headers,
        )
    assert resp.status_code == 200, resp.text

    got = _recipients(mock_post)
    everyone = {tg for _h, tg in users}
    assert got, "a concession notified nobody (the G3a bug)"
    assert set(got) == everyone - {conceder_tg}
    messages = [m for msgs in got.values() for m in msgs]
    assert all(POWERS[2] in m and "conceded" in m for m in messages), messages


def test_withdrawing_a_draw_vote_is_not_announced() -> None:
    """`/nodraw` is a retraction; spamming six people about it is noise.

    Only `vote: true` and quorum are announced — asserted so a future change that
    notifies on every vote change has to be deliberate.
    """
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    headers, _tg = users[0]

    with patch("server.api.shared.requests.post"):
        client.post(
            f"/games/{game_id}/draw_vote",
            json={"power": POWERS[0], "vote": True},
            headers=headers,
        )
    with patch("server.api.shared.requests.post") as mock_post:
        resp = client.post(
            f"/games/{game_id}/draw_vote",
            json={"power": POWERS[0], "vote": False},
            headers=headers,
        )
    assert resp.status_code == 200, resp.text
    assert _recipients(mock_post) == {}


def test_a_notification_failure_does_not_fail_the_draw() -> None:
    """The draw is already committed to Postgres; Telegram must not undo it."""
    client = TestClient(app)
    game_id, users = _seeded_game(client)

    with patch("server.api.shared.requests.post", side_effect=OSError("telegram down")):
        for power, (headers, _tg) in zip(POWERS, users):
            resp = client.post(
                f"/games/{game_id}/draw_vote",
                json={"power": power, "vote": True},
                headers=headers,
            )
            assert resp.status_code == 200, resp.text

    assert resp.json()["quorum_reached"] is True
    assert client.get(f"/games/{game_id}/state").json()["status"] == "COMPLETED"
