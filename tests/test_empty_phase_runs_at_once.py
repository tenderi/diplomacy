"""BV2: a phase in which no power has anything to order runs at once.

A movement turn that dislodges a unit with nowhere to retreat yields a retreat
phase nobody owes an order in. It used to sit there until the deadline or a
manual process, wasting a schedule slot. Now it is processed straight after the
turn that produced it, whatever ``auto_process`` says, and the players get one
DM, for the phase that needs them, still carrying the trapped unit's notice.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from engine.serialization import resolution_from_dict
from engine.types import PhaseType, Season
from persistence.game_repo import StaleGameError
from server.api import ADMIN_TOKEN, app
from server.api import shared as api_shared
from server.api.shared import db_service, game_service
from server.daide import tokens as t
from server.daide.clauses import turn_clause
from server.daide.server import DaideServer
from server.daide.session import build_ord_messages
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_auto_process import BOT, _order, _phase, _table

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _unit(kind: str, power: str, prov: str) -> dict[str, Any]:
    return {"kind": kind, "power": power, "location": prov}


def _trap_board(game_id: str) -> None:
    """S1901M: England can take BEL from PIC with two supports; France's A BEL
    then has nowhere to go (HOL is English, RUH and BUR German, PIC the
    attacker's origin)."""
    board = game_service.state_json(game_id)
    assert board is not None
    board["units"] = [
        _unit("A", "ENGLAND", "PIC"),
        _unit("A", "ENGLAND", "HOL"),
        _unit("F", "ENGLAND", "NTH"),
        _unit("A", "FRANCE", "BEL"),
        _unit("A", "FRANCE", "PAR"),
        _unit("A", "GERMANY", "RUH"),
        _unit("A", "GERMANY", "BUR"),
    ]
    game_service.restore_snapshot(game_id, board, "S1901M")


def _dislodge(client: TestClient, game_id: str, e: str, f: str) -> None:
    _order(client, game_id, e, "ENGLAND", ["A PIC - BEL", "A HOL S A PIC - BEL", "F NTH S A PIC - BEL"])
    _order(client, game_id, f, "FRANCE", ["A BEL H", "A PAR H"])


def test_a_trapped_retreat_phase_runs_straight_after_the_movement(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, e, f = _table(client, auto=False)
    _trap_board(game_id)
    _dislodge(client, game_id, e, f)
    posted: list[str] = []
    monkeypatch.setattr(api_shared, "_post_turn_to_channel", lambda _g, text, *_a: posted.append(text))
    with OutboxProbe() as probe:
        resp = client.post(f"/games/{game_id}/process_turn", headers=BOT)
    assert resp.status_code == 200, resp.text
    # Straight past the empty S1901R, though auto_process is off.
    assert resp.json()["phase"] == "F1901M"
    assert _phase(client, game_id) == "F1901M"
    units = client.get(f"/games/{game_id}/state").json()["units_by_power"]
    assert [u["location"] for u in units["FRANCE"]] == ["PAR"]
    # One snapshot per processed phase: the movement and the retreat.
    assert sorted(s.turn_number for s in db_service.get_game_snapshots_by_game_id(int(game_id))) == [0, 1, 2]

    head = f"The turn has been processed for game {game_id}. Orders are due for Fall 1901 movement."
    assert probe.by_recipient() == {
        e: [
            f"{head}\nYour results for Spring 1901 movement:\n"
            "A HOL S A PIC - BEL succeeded.\nF NTH S A PIC - BEL succeeded.\nA PIC - BEL succeeded."
        ],
        f: [
            f"{head}\nYour results for Spring 1901 movement:\nA BEL was dislodged by A PIC (ENGLAND).\nA PAR held.\n"
            "Your A BEL was dislodged and has nowhere to retreat: it is disbanded, no order needed."
        ],
    }
    # The group, too, gets one post, for the phase that needs orders, telling it what
    # the folded retreat phase did (#414).
    assert posted == [
        "The turn has been processed. Fall 1901 movement: new orders are due -- send them to me in private.\n"
        "FRANCE: A BEL was dislodged and had nowhere to retreat: it was disbanded.",
    ]


# The slot a weekly schedule would give the phase that begins now.
SLOT = datetime(2031, 3, 3, 16, 0, tzinfo=timezone.utc)


def _deadline(game_id: str) -> datetime | None:
    row = db_service.get_game_by_id(int(game_id))
    assert row is not None
    if row.deadline is None:
        return None
    return row.deadline if row.deadline.tzinfo else row.deadline.replace(tzinfo=timezone.utc)


def _scheduled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_shared, "scheduled_deadline", lambda _gid, now=None: SLOT)


def test_the_deadline_path_chains_the_empty_phase_too(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, e, f = _table(client, auto=False)
    _trap_board(game_id)
    _dislodge(client, game_id, e, f)
    _scheduled(monkeypatch)
    now = datetime.now(timezone.utc)
    db_service.update_game_deadline(int(game_id), now - timedelta(minutes=1))
    with OutboxProbe() as probe:
        api_shared.process_due_deadlines(now)
    assert _phase(client, game_id) == "F1901M"
    units = client.get(f"/games/{game_id}/state").json()["units_by_power"]
    assert [u["location"] for u in units["FRANCE"]] == ["PAR"]
    assert sorted(s.turn_number for s in db_service.get_game_snapshots_by_game_id(int(game_id))) == [0, 1, 2]
    # Armed once, for the phase the game ends up in.
    assert _deadline(game_id) == SLOT
    # One DM, for the phase that needs them, carrying the movement's results
    # and the deadline armed for it.
    assert probe.by_recipient()[f] == [
        f"The turn has been processed for game {game_id} because its deadline passed. "
        "Orders are due for Fall 1901 movement.\n"
        "Your results for Spring 1901 movement:\nA BEL was dislodged by A PIC (ENGLAND).\nA PAR held.\n"
        "Your A BEL was dislodged and has nowhere to retreat: it is disbanded, no order needed.\n"
        "Next deadline: 2031-03-03 16:00 UTC."
    ]


def test_a_phase_someone_owes_orders_in_still_waits(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, e, f = _table(client, auto=False)
    _trap_board(game_id)
    board = game_service.state_json(game_id)
    assert board is not None
    # Free BUR: France's A BEL can now retreat there, so France owes an order.
    board["units"] = [u for u in board["units"] if u["location"] != "BUR"]
    game_service.restore_snapshot(game_id, board, "S1901M")
    _dislodge(client, game_id, e, f)
    _scheduled(monkeypatch)
    with OutboxProbe() as probe:
        resp = client.post(f"/games/{game_id}/process_turn", headers=BOT)
    assert resp.status_code == 200, resp.text
    assert resp.json()["phase"] == "S1901R"
    state = client.get(f"/games/{game_id}/state").json()
    assert state["phase"] == "S1901R"
    # France's A BEL waits for its retreat order, under the phase's deadline.
    assert [(d["unit"]["location"], d["retreats"]) for d in state["dislodged"]] == [("BEL", ["BUR"])]
    assert _deadline(game_id) == SLOT
    assert sorted(s.turn_number for s in db_service.get_game_snapshots_by_game_id(int(game_id))) == [0, 1]
    assert probe.by_recipient()[f] == [
        f"The turn has been processed for game {game_id}. Spring 1901 retreats: your orders are due.\n"
        "Your A BEL was dislodged: it may retreat to BUR, or disband. With no order it is disbanded.\n"
        "Your results for Spring 1901 movement:\nA BEL was dislodged by A PIC (ENGLAND).\nA PAR held.\n"
        "Next deadline: 2031-03-03 16:00 UTC."
    ]


def _fail_second_process(monkeypatch: pytest.MonkeyPatch, fail_games: set[str] | None = None) -> list[str]:
    """Make ``process_turn`` raise on the empty S1901R phase (of the first game
    to reach it, or of each game in ``fail_games``); returns the games it failed."""
    real = game_service.process_turn
    failed: list[str] = []

    def flaky(gid: str, expected_phase_code: str | None = None) -> dict[str, Any]:
        if expected_phase_code == "S1901R" and (gid in fail_games if fail_games is not None else not failed):
            failed.append(gid)
            raise RuntimeError("boom")
        return real(gid, expected_phase_code)

    monkeypatch.setattr(game_service, "process_turn", flaky)
    return failed


def test_a_failing_empty_phase_does_not_break_the_turn_before_it(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, e, f = _table(client, auto=False)
    _trap_board(game_id)
    _dislodge(client, game_id, e, f)
    db_service.update_game_deadline(int(game_id), datetime.now(timezone.utc) + timedelta(hours=1))
    _scheduled(monkeypatch)
    assert _fail_second_process(monkeypatch, {game_id}) == []
    posted: list[str] = []
    monkeypatch.setattr(api_shared, "post_to_game_group", lambda _g, text, _kind, **_k: posted.append(text))
    with OutboxProbe() as probe:
        resp = client.post(f"/games/{game_id}/process_turn", headers=BOT)
    # The movement is committed: the route reports it, not a 500.
    assert resp.status_code == 200, resp.text
    assert resp.json()["phase"] == "S1901R"
    assert len(resp.json()["resolution"]["results"]) == 7
    assert _phase(client, game_id) == "S1901R"
    # The spent movement deadline is replaced by the one the retreat phase gets.
    assert _deadline(game_id) == SLOT
    # BX2: the players and the group are told the phase is stuck and how to move it.
    stuck = (
        f"⚠️ Game {game_id}: nobody has anything to order in Spring 1901 retreats, but it could not be "
        "processed automatically. The game's creator can move it on with ⚙️ Process turn now in the game "
        "menu (or Process turn on the web game page). "
        "Otherwise it is processed at its deadline, 2031-03-03 16:00 UTC."
    )
    assert probe.by_recipient()[f] == [
        f"The turn has been processed for game {game_id}.\nYour results for Spring 1901 movement:\n"
        "A BEL was dislodged by A PIC (ENGLAND).\nA PAR held.\n"
        "Your A BEL was dislodged and has nowhere to retreat: it is disbanded, no order needed.",
        stuck,
    ]
    assert posted == [stuck]


def test_a_failing_empty_phase_does_not_stop_the_scheduler(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    games = []
    for _ in range(2):
        game_id, e, f = _table(client, auto=False)
        _trap_board(game_id)
        _dislodge(client, game_id, e, f)
        games.append(game_id)
    now = datetime.now(timezone.utc)
    for game_id in games:
        db_service.update_game_deadline(int(game_id), now - timedelta(minutes=1))
    _scheduled(monkeypatch)
    failed = _fail_second_process(monkeypatch)
    api_shared.process_due_deadlines(now)
    assert len(failed) == 1
    (other,) = [g for g in games if g != failed[0]]
    assert (_phase(client, failed[0]), _deadline(failed[0])) == ("S1901R", SLOT)
    assert (_phase(client, other), _deadline(other)) == ("F1901M", SLOT)


def test_another_worker_processing_the_empty_phase_still_gets_the_lines_out(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, e, f = _table(client, auto=False)
    _trap_board(game_id)
    _dislodge(client, game_id, e, f)
    real = game_service.process_turn
    calls: list[str | None] = []

    def once(gid: str, expected_phase_code: str | None = None) -> dict[str, Any]:
        calls.append(expected_phase_code)
        if len(calls) > 1:
            raise StaleGameError(f"game {gid} is no longer in {expected_phase_code}")
        return real(gid, expected_phase_code)

    monkeypatch.setattr(game_service, "process_turn", once)
    with OutboxProbe() as probe:
        assert client.post(f"/games/{game_id}/process_turn", headers=BOT).json()["phase"] == "S1901R"
    assert calls == ["S1901M", "S1901R"]  # DD2: the manual process pins its phase too
    assert probe.by_recipient()[f] == [
        f"The turn has been processed for game {game_id}.\nYour results for Spring 1901 movement:\n"
        "A BEL was dislodged by A PIC (ENGLAND).\nA PAR held.\n"
        "Your A BEL was dislodged and has nowhere to retreat: it is disbanded, no order needed."
    ]


class _Session:
    """A DAIDE session that records what it is sent."""

    def __init__(self) -> None:
        self.sent: list[tuple[Any, ...]] = []

    async def deliver(self, *messages: Any) -> bool:
        self.sent.extend(tuple(m) for m in messages)
        return True


def test_daide_ord_carries_the_movement_results_not_the_empty_retreat_s(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, e, f = _table(client, auto=False)
    _trap_board(game_id)
    _dislodge(client, game_id, e, f)
    daide = DaideServer(game_service)
    session = _Session()
    daide._sessions[game_id] = {"FRANCE": session}  # type: ignore[dict-item]
    monkeypatch.setattr(api_shared, "daide_server", daide)
    monkeypatch.setattr(api_shared, "main_loop", None)
    resp = client.post(f"/games/{game_id}/process_turn", headers=BOT)
    assert resp.status_code == 200, resp.text
    movement = resolution_from_dict(resp.json()["resolution"])
    retreat_dict = game_service.last_resolution(game_id)
    assert retreat_dict is not None
    retreat = resolution_from_dict(retreat_dict)

    def ords(phase_type: PhaseType, resolution: Any, as_dict: Any) -> list[list[Any]]:
        turn = list(turn_clause(Season.SPRING, phase_type, 1901))
        return [
            list(m) for m in build_ord_messages(resolution, as_dict["units"], phase_type, daide.map, turn)
        ]

    expected = ords(PhaseType.MOVEMENT, movement, resp.json()["resolution"]) + ords(
        PhaseType.RETREAT, retreat, retreat_dict
    )
    # Seven movement orders, then the trapped unit's disband in S1901R. Read
    # late, both batches were the retreat phase's.
    assert (len(movement.results), len(retreat.results)) == (7, 1)
    assert [list(m) for m in session.sent if m[0] == t.ORD] == expected


GROUP = "-1004414"


def _link_group(client: TestClient, game_id: str) -> None:
    link = {"channel_id": GROUP}
    resp = client.post(f"/games/{game_id}/channel/link", json=link, headers={**BOT, "X-Admin-Token": ADMIN_TOKEN})
    assert resp.status_code == 200, resp.text


def _group_rows(probe: OutboxProbe) -> list[tuple[str, str, str | None]]:
    return [
        (r["kind"], r["message"], (r["payload"] or {}).get("path"))
        for r in probe.rows()
        if str(r["telegram_id"]) == GROUP
    ]


def test_the_group_gets_one_post_for_the_fold(client: TestClient) -> None:
    """#414: a movement that dislodged a unit with no retreat posted the group two
    texts and four maps, three of them alike, and neither text said the unit was
    lost. The fold is one post, as any turn is: the text for the phase that needs
    orders, carrying the disband, the orders map of the movement the players
    ordered, then the board after the folded retreat phase."""
    game_id, e, f = _table(client, auto=False)
    _trap_board(game_id)
    _dislodge(client, game_id, e, f)
    _link_group(client, game_id)
    with OutboxProbe() as probe:
        assert client.post(f"/games/{game_id}/process_turn", headers=BOT).json()["phase"] == "F1901M"
    assert _group_rows(probe) == [
        (
            "channel_text",
            f"🔔 Turn Processed - Game {game_id}\n"
            "The turn has been processed. Fall 1901 movement: new orders are due -- send them to me in private.\n"
            "FRANCE: A BEL was dislodged and had nowhere to retreat: it was disbanded.",
            None,
        ),
        (
            "channel_map",
            f"📝 Game {game_id} · Spring 1901 movement: orders and results",
            f"/games/{game_id}/map/turn/0/orders",
        ),
        # Turn 1 was the folded retreat phase: this is the board Fall 1901 starts on.
        ("channel_map", f"🗺️ Game {game_id} · Spring 1901 movement: the result", f"/games/{game_id}/map/history/2"),
    ]


def test_a_fold_another_worker_finished_still_posts_what_it_held_back(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The empty phase was processed elsewhere, and that worker's post knows nothing
    of the movement: the post the fold held back goes out as it stood."""
    game_id, e, f = _table(client, auto=False)
    _trap_board(game_id)
    _dislodge(client, game_id, e, f)
    _link_group(client, game_id)
    real = game_service.process_turn

    def once(gid: str, expected_phase_code: str | None = None) -> dict[str, Any]:
        if expected_phase_code == "S1901R":
            raise StaleGameError(f"game {gid} is no longer in {expected_phase_code}")
        return real(gid, expected_phase_code)

    monkeypatch.setattr(game_service, "process_turn", once)
    with OutboxProbe() as probe:
        assert client.post(f"/games/{game_id}/process_turn", headers=BOT).json()["phase"] == "S1901R"
    assert _group_rows(probe) == [
        (
            "channel_text",
            f"🔔 Turn Processed - Game {game_id}\n"
            "The turn has been processed. Spring 1901 retreats: nobody has anything to order.\n"
            "FRANCE: A BEL was dislodged and had nowhere to retreat: it was disbanded.",
            None,
        ),
        (
            "channel_map",
            f"📝 Game {game_id} · Spring 1901 movement: orders and results",
            f"/games/{game_id}/map/turn/0/orders",
        ),
        ("channel_map", f"🗺️ Game {game_id} · Spring 1901 movement: the result", f"/games/{game_id}/map/history/1"),
    ]


def test_a_folded_adjustment_is_one_post_too(client: TestClient) -> None:
    """An adjustment only a dummy owes (Italy, one unit over its centres) runs at once
    after the Fall movement: one post, whose text names the spring and carries the
    dummy's civil-disorder disband, and whose maps are the Fall orders and the board
    after the winter."""
    game_id, e, f = _table(client, auto=False)
    board = game_service.state_json(game_id)
    assert board is not None
    board["season"] = "FALL"
    board["units"].append(_unit("A", "ITALY", "TUS"))
    game_service.restore_snapshot(game_id, board, "F1901M")
    _order(client, game_id, e, "ENGLAND", ["F LON H"])
    _order(client, game_id, f, "FRANCE", ["A PAR H"])
    _link_group(client, game_id)
    with OutboxProbe() as probe:
        assert client.post(f"/games/{game_id}/process_turn", headers=BOT).json()["phase"] == "S1902M"
    rows = _group_rows(probe)
    assert [kind for kind, _m, _p in rows] == ["channel_text", "channel_map", "channel_map"]
    assert rows[0][1] == (
        f"🔔 Turn Processed - Game {game_id}\n"
        "The turn has been processed. Spring 1902 movement: new orders are due -- send them to me in private.\n"
        "ITALY was 1 disband short, so A TUS was disbanded (civil disorder)."
    )
    assert rows[1:] == [
        (
            "channel_map",
            f"📝 Game {game_id} · Fall 1901 movement: orders and results",
            f"/games/{game_id}/map/turn/0/orders",
        ),
        ("channel_map", f"🗺️ Game {game_id} · Fall 1901 movement: the result", f"/games/{game_id}/map/history/2"),
    ]
