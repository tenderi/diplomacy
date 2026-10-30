"""BX1: a phase that becomes empty other than by a processed turn runs at once.

BV2 processes a phase nobody has anything to order in straight after the turn
that leads into it. A phase can also become empty while it stands: the creator
makes the only power still owing a build a dummy, or that power concedes, or
the seat completing the table is taken while the phase needs only dummies. It
used to wait for its deadline (with none set, for ever) unless ``auto_process``
was on. Now each of those processes it at once, whatever ``auto_process`` says.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from server.api.shared import db_service, game_service
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_quit_and_replace import _as, _register_and_login, _telegram_user

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured"),
]

DUMMIES = ["AUSTRIA", "ITALY", "RUSSIA", "TURKEY"]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _table(
    client: TestClient, *, seat_germany: bool = True
) -> tuple[str, dict[str, str], dict[str, str]]:
    """England, France (and Germany, unless ``seat_germany`` is off) held by
    players, the rest dummies, ``auto_process`` off. Returns the game id, the
    creator's headers and the players' telegram ids by power."""
    creator = _register_and_login(client, "bx1")
    resp = client.post(
        "/games/create",
        json={"map_name": "standard", "dummy_powers": DUMMIES, "auto_process": False},
        headers=creator,
    )
    assert resp.status_code == 200, resp.text
    game_id = str(resp.json()["game_id"])
    tgs: dict[str, str] = {}
    for power in ["ENGLAND", "FRANCE", "GERMANY"] if seat_germany else ["ENGLAND", "FRANCE"]:
        tgs[power] = _telegram_user(client, power.lower())
        assert (
            client.post(f"/games/{game_id}/join", json=_as(tgs[power], power=power)).status_code
            == 200
        )
    return game_id, creator, tgs


def _winter(game_id: str, *, without: list[str]) -> None:
    """Put the game in W1901A on the opening board less the units at ``without``:
    each power that lost a unit is owed a build in the home centre it left."""
    board = game_service.state_json(game_id)
    assert board is not None
    board["season"], board["phase_type"] = "WINTER", "ADJUSTMENT"
    board["units"] = [u for u in board["units"] if u["location"] not in without]
    game_service.restore_snapshot(game_id, board, "W1901A")


def _phase(client: TestClient, game_id: str) -> str:
    return client.get(f"/games/{game_id}/state").json()["phase"]


def _snapshots(game_id: str) -> list[int]:
    return sorted(s.turn_number for s in db_service.get_game_snapshots_by_game_id(int(game_id)))


def _no_group(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    posted: list[str] = []
    monkeypatch.setattr(
        api_shared, "_post_turn_to_channel", lambda _g, text, *_a: posted.append(text)
    )
    return posted


def test_making_the_only_owing_power_a_dummy_processes_the_phase(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, creator, tgs = _table(client)
    _winter(game_id, without=["KIE"])  # only Germany is owed a build
    assert client.post(f"/games/{game_id}/quit", json=_as(tgs["GERMANY"])).status_code == 200
    posted = _no_group(monkeypatch)
    with OutboxProbe() as probe:
        resp = client.post(
            f"/games/{game_id}/dummies", json={"power": "GERMANY", "dummy": True}, headers=creator
        )
    assert resp.status_code == 200, resp.text
    # auto_process is off, yet the winter that only a dummy now owes ran.
    assert _phase(client, game_id) == "S1902M"
    assert _snapshots(game_id) == [0, 1]
    # The change first, then the turn it caused.
    assert probe.by_recipient()[tgs["ENGLAND"]] == [
        f"GERMANY in game {game_id} is now played by civil disorder.",
        f"The turn has been processed for game {game_id}. Orders are due for Spring 1902 movement.",
    ]
    assert posted == [
        "The turn has been processed. Spring 1902 movement: new orders are due -- send them to me in private.",
    ]


def test_a_dummy_that_leaves_someone_owing_waits(client: TestClient) -> None:
    game_id, creator, tgs = _table(client)
    _winter(game_id, without=["KIE", "PAR"])  # Germany and France are owed builds
    assert client.post(f"/games/{game_id}/quit", json=_as(tgs["GERMANY"])).status_code == 200
    resp = client.post(
        f"/games/{game_id}/dummies", json={"power": "GERMANY", "dummy": True}, headers=creator
    )
    assert resp.status_code == 200, resp.text
    # France still has a build to order.
    assert _phase(client, game_id) == "W1901A"
    assert _snapshots(game_id) == [0]


def test_the_only_owing_power_conceding_processes_the_phase(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, _creator, tgs = _table(client)
    _winter(game_id, without=["KIE"])
    _no_group(monkeypatch)
    resp = client.post(f"/games/{game_id}/concede", json=_as(tgs["GERMANY"], power="GERMANY"))
    assert resp.status_code == 200, resp.text
    assert resp.json()["auto_processed"] == 1
    assert _phase(client, game_id) == "S1902M"
    units = client.get(f"/games/{game_id}/state").json()["units_by_power"]
    assert units.get("GERMANY", []) == []


def test_a_concession_that_leaves_someone_owing_waits(client: TestClient) -> None:
    game_id, _creator, tgs = _table(client)
    _winter(game_id, without=["KIE", "PAR"])
    resp = client.post(f"/games/{game_id}/concede", json=_as(tgs["GERMANY"], power="GERMANY"))
    assert resp.status_code == 200, resp.text
    assert resp.json()["auto_processed"] == 0
    assert _phase(client, game_id) == "W1901A"


def test_the_seat_completing_the_table_processes_a_phase_only_dummies_owe(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, _creator, tgs = _table(client, seat_germany=False)
    _winter(game_id, without=["VIE"])  # only Austria, a dummy, is owed a build
    assert _phase(client, game_id) == "W1901A"
    _no_group(monkeypatch)
    germany = _telegram_user(client, "germany")
    assert (
        client.post(f"/games/{game_id}/join", json=_as(germany, power="GERMANY")).status_code == 200
    )
    assert _phase(client, game_id) == "S1902M"


def test_a_failure_processing_the_emptied_phase_leaves_the_change_standing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, _creator, tgs = _table(client)
    _winter(game_id, without=["KIE"])

    def boom(gid: str, expected_phase_code: str | None = None) -> dict[str, Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr(game_service, "process_turn", boom)
    resp = client.post(f"/games/{game_id}/concede", json=_as(tgs["GERMANY"], power="GERMANY"))
    # The concession is committed: the route reports it, not a 500.
    assert resp.status_code == 200, resp.text
    assert resp.json()["auto_processed"] == 0
    assert _phase(client, game_id) == "W1901A"
    assert client.get(f"/games/{game_id}/state").json()["units_by_power"].get("GERMANY", []) == []
