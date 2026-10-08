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
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from engine.serialization import state_to_dict
from engine.types import GameState, GameStatus, Location, PhaseType, Season, Unit, UnitKind
from server.api import app
from server.api import shared as api_shared
from tests.reliability_helpers import OutboxProbe

pytestmark = [pytest.mark.integration, pytest.mark.database]

GROUP = f"-100{int(time.time() * 1000) % 10**9}"
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


def _recipients(probe: OutboxProbe) -> dict[str, list[str]]:
    """telegram_id -> messages queued in ``bot_outbox`` during the probe."""
    return probe.by_recipient()


def test_a_non_final_draw_vote_is_announced_to_the_others() -> None:
    """One yes-vote out of seven does not end the game, but is still news.

    A draw is the one outcome every power holds a veto over, so learning that one
    is being negotiated should not require running `/status`.
    """
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    voter_headers, voter_tg = users[0]

    with OutboxProbe() as mock_post:
        resp = client.post(
            f"/games/{game_id}/draw_vote",
            json={"power": POWERS[0], "vote": True},
            headers=voter_headers,
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["quorum_reached"] is False

    everyone = {tg for _h, tg in users}
    expected = (
        f"ENGLAND has voted to end game {game_id} in a draw (1/7 agreed). "
        "Draw votes last until this phase is processed. "
        "Use /draw to agree or /nodraw to withdraw."
    )
    assert _recipients(mock_post) == {tg: [expected] for tg in everyone - {voter_tg}}


def test_reaching_draw_quorum_tells_everyone_the_game_ended() -> None:
    """The headline G3a fix: a game ending by agreement must not be silent."""
    client = TestClient(app)
    game_id, users = _seeded_game(client)

    # Six votes, then the seventh completes quorum.
    for power, (headers, _tg) in list(zip(POWERS, users))[:-1]:
        with OutboxProbe():
            r = client.post(
                f"/games/{game_id}/draw_vote",
                json={"power": power, "vote": True},
                headers=headers,
            )
        assert r.status_code == 200, r.text
        assert r.json()["quorum_reached"] is False, power

    api_shared.db_service.link_game_to_channel(game_id, GROUP, any_displacer=True)
    last_headers, last_tg = users[-1]
    with OutboxProbe() as mock_post:
        resp = client.post(
            f"/games/{game_id}/draw_vote",
            json={"power": POWERS[-1], "vote": True},
            headers=last_headers,
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["quorum_reached"] is True
    assert resp.json()["game_status"] == "COMPLETED"

    everyone = {tg for _h, tg in users}
    drawn = (
        f"Game {game_id} has ended in a draw shared by "
        "AUSTRIA, ENGLAND, FRANCE, GERMANY, ITALY, RUSSIA and TURKEY."
    )
    rows = mock_post.rows()
    # BD4: every power shares this draw, so each reads itself as "you"
    # (TURKEY cast the deciding vote and is not told).
    assert {str(r["telegram_id"]): [r["message"]] for r in rows if r["kind"] != "channel_text"} == {
        tg: [
            f"Game {game_id} has ended in a draw shared by you, "
            + ", ".join(p for p in ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA"] if p != power)
            + " and TURKEY."
        ]
        for power, (_h, tg) in zip(POWERS, users)
        if tg != last_tg
    }
    # BD1: a draw is not a processed turn, so the group gets no "Turn Processed"
    # heading and no maps -- one post, headed as a draw.
    assert [(r["telegram_id"], r["message"]) for r in rows if r["kind"] == "channel_text"] == [
        (GROUP, f"🤝 Draw - Game {game_id}\n{drawn}")
    ]
    assert [r for r in rows if r["kind"] == "channel_map"] == []


def test_conceding_tells_the_remaining_players() -> None:
    """A power's units come off the board; that used to be invisible."""
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    conceder_headers, conceder_tg = users[2]

    with OutboxProbe() as mock_post:
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


def test_withdrawing_a_draw_vote_is_announced_with_the_new_count() -> None:
    """BD1: a withdrawal reaches the people the vote did, or they keep believing
    the count they were last told."""
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    headers, tg = users[0]

    with OutboxProbe():
        client.post(f"/games/{game_id}/draw_vote", json={"power": POWERS[0], "vote": True}, headers=headers)
    with OutboxProbe() as mock_post:
        resp = client.post(f"/games/{game_id}/draw_vote", json={"power": POWERS[0], "vote": False}, headers=headers)
    assert resp.status_code == 200, resp.text
    everyone = {t for _h, t in users}
    expected = f"ENGLAND has withdrawn its vote to end game {game_id} in a draw (0/7 agreed)."
    assert _recipients(mock_post) == {t: [expected] for t in everyone - {tg}}


def test_a_repeated_vote_or_an_empty_withdrawal_announces_nothing() -> None:
    """BD1: only a change of vote is news. A second yes, or a "no" from a power
    that never voted, would otherwise repeat a count nobody's vote moved."""
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    headers, _tg = users[0]
    other_headers, _other_tg = users[1]

    with OutboxProbe():
        client.post(f"/games/{game_id}/draw_vote", json={"power": POWERS[0], "vote": True}, headers=headers)
    with OutboxProbe() as mock_post:
        again = client.post(f"/games/{game_id}/draw_vote", json={"power": POWERS[0], "vote": True}, headers=headers)
        empty = client.post(
            f"/games/{game_id}/draw_vote", json={"power": POWERS[1], "vote": False}, headers=other_headers
        )
    assert (again.status_code, again.json()["votes"]) == (200, ["ENGLAND"]), again.text
    assert (empty.status_code, empty.json()["votes"]) == (200, ["ENGLAND"]), empty.text
    assert mock_post.rows() == []


def test_a_solo_victory_names_the_winner() -> None:
    """BD1: a processed turn ends a game only by a solo victory, and says whose."""
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    api_shared.db_service.link_game_to_channel(game_id, GROUP, any_displacer=True)
    won = GameState(
        1901, Season.WINTER, PhaseType.ADJUSTMENT,
        units=frozenset({Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))}),
        ownership={"PAR": "FRANCE"},
        status=GameStatus.COMPLETED,
        winners=frozenset({"FRANCE"}),
    )
    api_shared.game_service.restore_snapshot(game_id, state_to_dict(won), phase_code="W1901A")
    row_id = int(api_shared.db_service.get_game_by_game_id(game_id).id)

    with OutboxProbe() as mock_post:
        api_shared.notify_turn_processed(
            game_id, row_id, trigger="manual", game_ended=True, exclude_telegram_id=users[1][1]
        )
    ended = f"Game {game_id} has ended: FRANCE has won with a solo victory."
    rows = mock_post.rows()
    assert {str(r["telegram_id"]): [r["message"]] for r in rows if r["kind"] == "dm"} == {
        tg: [ended] for _h, tg in users if tg != users[1][1]
    }
    assert [(r["telegram_id"], r["message"]) for r in rows if r["kind"] == "channel_text"] == [
        (GROUP, f"🔔 Turn Processed - Game {game_id}\nThe turn has been processed. {ended}")
    ]


def test_a_notification_failure_does_not_fail_the_draw() -> None:
    """The draw is already committed to Postgres; Telegram must not undo it."""
    client = TestClient(app)
    game_id, users = _seeded_game(client)

    with patch.object(api_shared.db_service, "enqueue_bot_notification", side_effect=OSError("db down")):
        for power, (headers, _tg) in zip(POWERS, users):
            resp = client.post(
                f"/games/{game_id}/draw_vote",
                json={"power": power, "vote": True},
                headers=headers,
            )
            assert resp.status_code == 200, resp.text

    assert resp.json()["quorum_reached"] is True
    assert client.get(f"/games/{game_id}/state").json()["status"] == "COMPLETED"
