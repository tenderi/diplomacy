"""BV3: deadline notices read in the schedule's own timezone, a deadline-processed turn
names the powers that had not ordered, and the disband DM says what no order does."""
from __future__ import annotations

import datetime
import re
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_deadline_schedule_api import _game as _schedule_game
from tests.test_deadline_voting import POWERS as VOTE_POWERS
from tests.test_quit_and_replace import BOT_SECRET
from tests.test_turn_notifications import REQUIRED_POWERS, _seeded_game

pytestmark = [
    pytest.mark.integration,
    pytest.mark.database,
    pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured"),
]

HELSINKI = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC \((Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{2}:\d{2} Europe/Helsinki\)"


def test_the_set_deadline_notice_shows_the_schedules_local_time() -> None:
    client = TestClient(app)
    game_id, users = _schedule_game(
        client, VOTE_POWERS, deadline_schedule="Mon,Wed,Fri 16:00", deadline_timezone="Europe/Helsinki"
    )
    future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=6)).replace(microsecond=0)
    with patch("server.api.routes.games.notify_players") as notify:
        resp = client.post(f"/games/{game_id}/deadline", json={"deadline": future.isoformat()}, headers=users["ITALY"])
    assert resp.status_code == 200, resp.text
    schedule = api_shared.game_schedule(game_id)
    expected = (
        f"Deadline for game {game_id} set to {api_shared.format_scheduled_deadline(future, schedule)}. "
        "Orders in by then; the turn is processed automatically when it passes. "
        "This deadline covers the current phase only."
    )
    text = notify.call_args[0][1]
    assert re.match(re.escape(f"Deadline for game {game_id} set to ") + HELSINKI + r"\. ", text)
    assert text == expected


def test_the_proposal_passed_notice_shows_the_schedules_local_time() -> None:
    client = TestClient(app)
    game_id, users = _schedule_game(
        client, VOTE_POWERS, deadline_schedule="Mon,Wed,Fri 16:00", deadline_timezone="Europe/Helsinki"
    )
    assert client.post(
        f"/games/{game_id}/deadline/propose", json={"power": "FRANCE", "hours": 24.0}, headers=users["FRANCE"]
    ).status_code == 200
    with patch("server.api.routes.games.notify_players") as notify:
        for power in ["GERMANY", "ITALY", "ENGLAND"]:
            r = client.post(
                f"/games/{game_id}/deadline/vote", json={"power": power, "vote": True}, headers=users[power]
            )
            assert r.status_code == 200, r.text
    text = notify.call_args[0][1]
    assert re.fullmatch(re.escape(f"Game {game_id}'s deadline proposal passed: deadline now ") + HELSINKI + r"\.", text)


def test_a_deadline_turn_names_the_powers_that_had_not_ordered() -> None:
    client = TestClient(app)
    game_id, row_id, users = _seeded_game(client)
    assert REQUIRED_POWERS[1] == "FRANCE"
    resp = client.post(
        "/games/set_orders",
        json={
            "game_id": game_id, "power": "FRANCE", "orders": ["A PAR - BUR"],
            "telegram_id": users[1][1], "bot_secret": BOT_SECRET,
        },
    )
    assert resp.status_code == 200, resp.text
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
    api_shared.db_service.update_game_deadline(row_id, past)
    with OutboxProbe() as probe:
        api_shared.process_due_deadlines(datetime.datetime.now(datetime.timezone.utc))
    line = "AUSTRIA, ENGLAND, GERMANY, ITALY, RUSSIA and TURKEY had not ordered: their units held."
    by_tg = probe.by_recipient()
    france = by_tg[users[1][1]]
    assert len(france) == 1 and ("\n" + line + "\n") in france[0]  # FRANCE ordered: not named
    italy = by_tg[users[REQUIRED_POWERS.index("ITALY")][1]]
    assert len(italy) == 1 and ("\n" + line + "\n") in italy[0], italy[0]


def test_a_manual_turn_does_not_name_unordered_powers() -> None:
    client = TestClient(app)
    game_id, _row_id, users = _seeded_game(client)
    with OutboxProbe() as probe:
        assert client.post(f"/games/{game_id}/process_turn", headers=users[0][0]).status_code == 200
    assert not any("had not ordered" in m for m in probe.messages())
