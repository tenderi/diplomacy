"""BD4: a player's own DMs address them as "you".

A play-through found DMs talking about their reader in the third person: the
winner of a solo was told "FRANCE has won", a sharer of a draw read its own power
in the list, and a proposer read "the deadline proposal (from FRANCE) was voted
down". The reader is now "you"; everyone else, and the group, still read the power.
(The turn-processed DM's "you" texts are pinned in ``test_turn_notification_text``.)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from engine.serialization import state_to_dict
from engine.types import GameState, GameStatus, Location, PhaseType, Season, Unit, UnitKind
from server.api import app
from server.api import shared as api_shared
from tests.reliability_helpers import OutboxProbe
from tests.test_draw_concede_notifications import GROUP, POWERS, _seeded_game

pytestmark = [pytest.mark.integration, pytest.mark.database]


def _dms(probe: OutboxProbe) -> dict[str, list[str]]:
    return {
        str(r["telegram_id"]): [m["message"] for m in probe.rows() if m["telegram_id"] == r["telegram_id"]]
        for r in probe.rows()
        if r["kind"] == "dm"
    }


def test_the_solo_winner_is_told_they_won() -> None:
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

    with OutboxProbe() as probe:
        api_shared.notify_turn_processed(game_id, row_id, trigger="deadline", game_ended=True)

    ended = f"Game {game_id} has ended: FRANCE has won with a solo victory."
    winner_tg = users[POWERS.index("FRANCE")][1]
    assert _dms(probe) == {
        tg: [f"Game {game_id} has ended: you have won with a solo victory." if tg == winner_tg else ended]
        for _h, tg in users
    }
    # The group still names the winner.
    assert [(r["telegram_id"], r["message"]) for r in probe.rows() if r["kind"] == "channel_text"] == [
        (GROUP, f"🔔 Turn Processed - Game {game_id}\nThe turn has been processed. {ended}")
    ]


def test_a_draw_sharer_reads_you_among_the_sharers() -> None:
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    row_id = int(api_shared.db_service.get_game_by_game_id(game_id).id)
    api_shared.db_service.link_game_to_channel(game_id, GROUP, any_displacer=True)
    by_power = {power: tg for power, (_h, tg) in zip(POWERS, users)}

    with OutboxProbe() as probe:
        api_shared.notify_game_drawn(game_id, row_id, ["ENGLAND", "FRANCE", "ITALY"])

    shared = f"Game {game_id} has ended in a draw shared by ENGLAND, FRANCE and ITALY."
    expected = {tg: [shared] for tg in by_power.values()}
    expected[by_power["ENGLAND"]] = [f"Game {game_id} has ended in a draw shared by you, FRANCE and ITALY."]
    expected[by_power["FRANCE"]] = [f"Game {game_id} has ended in a draw shared by you, ENGLAND and ITALY."]
    expected[by_power["ITALY"]] = [f"Game {game_id} has ended in a draw shared by you, ENGLAND and FRANCE."]
    assert _dms(probe) == expected
    assert [(r["telegram_id"], r["message"]) for r in probe.rows() if r["kind"] == "channel_text"] == [
        (GROUP, f"🤝 Draw - Game {game_id}\n{shared}")
    ]


def test_the_proposer_of_a_rejected_deadline_reads_your_proposal() -> None:
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    seat = dict(zip(POWERS, users))
    assert client.post(
        f"/games/{game_id}/deadline/propose", json={"power": "FRANCE", "hours": 6.0}, headers=seat["FRANCE"][0]
    ).status_code == 200
    for power in ["GERMANY", "ITALY", "RUSSIA"]:
        with OutboxProbe():
            r = client.post(
                f"/games/{game_id}/deadline/vote", json={"power": power, "vote": False}, headers=seat[power][0]
            )
        assert r.json()["status"] == "pending", r.text
    with OutboxProbe() as probe:
        r = client.post(
            f"/games/{game_id}/deadline/vote", json={"power": "TURKEY", "vote": False}, headers=seat["TURKEY"][0]
        )
    assert r.json()["status"] == "rejected", r.text

    others = f"Game {game_id}'s deadline proposal (from FRANCE) was voted down; nothing changed."
    expected = {tg: [others] for power, (_h, tg) in seat.items() if power not in ("FRANCE", "TURKEY")}
    expected[seat["FRANCE"][1]] = [f"Your deadline proposal in game {game_id} was voted down; nothing changed."]
    assert _dms(probe) == expected


def test_the_proposer_of_an_expired_deadline_reads_your_proposal() -> None:
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    seat = dict(zip(POWERS, users))
    with OutboxProbe():
        assert client.post(
            f"/games/{game_id}/deadline/propose",
            json={"power": "ITALY", "hours": 5.0, "vote_hours": 1.0},
            headers=seat["ITALY"][0],
        ).status_code == 200
    with OutboxProbe() as probe:
        api_shared.expire_deadline_proposals(datetime.now(timezone.utc) + timedelta(hours=2))

    others = f"The deadline proposal in game {game_id} (from ITALY) expired without a majority; nothing changed."
    mine = {tg for _h, tg in users}
    got = {tg: msgs for tg, msgs in _dms(probe).items() if tg in mine}
    expected = {tg: [others] for _h, tg in users}
    expected[seat["ITALY"][1]] = [
        f"Your deadline proposal in game {game_id} expired without a majority; nothing changed."
    ]
    assert got == expected
