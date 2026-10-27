"""A write that committed is not undone by a notification that failed (BU5).

Each game route below commits its write and then notifies the players inside a
``try``: the notification is a side effect, so a failure there is logged and the
caller still gets the normal 200. Each case makes ``notify_players`` raise, then
pins the exact response and checks the write is really stored.

Plus the repository's own guard: ``save_state`` and ``modify_state_json`` on a
game that does not exist raise ``ValueError`` naming it, not a bare ``None``
dereference.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from persistence.database import utcnow_naive
from server.api import ADMIN_TOKEN, app
from server.api.shared import db_service, game_service
from server.response_cache import clear_response_cache
from tests.conftest import _get_db_url
from tests.table_helpers import fill_with_dummies
from tests.test_concurrent_processing import BOT
from tests.test_quit_and_replace import _as, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]


@pytest.fixture
def client() -> TestClient:
    clear_response_cache()
    return TestClient(app)


def _game(client: TestClient) -> tuple[str, dict[str, str]]:
    """A started game with ENGLAND, FRANCE, GERMANY and ITALY seated (one
    Telegram user each; four, so two yes votes are not yet a majority) and the
    rest dummies. Returns ``(game_id, {power: telegram_id})``."""
    seats = {p: _telegram_user(client, p.lower()) for p in ("ENGLAND", "FRANCE", "GERMANY", "ITALY")}
    game_id = str(client.post("/games/create", json=_as(seats["ENGLAND"], map_name="standard"), headers=BOT).json()["game_id"])
    for power, tg in seats.items():
        assert client.post(f"/games/{game_id}/join", json=_as(tg, power=power)).status_code == 200
    fill_with_dummies(game_id)
    return game_id, seats


def _deadline_view(client: TestClient, game_id: str) -> dict[str, Any]:
    clear_response_cache()
    resp = client.get(f"/games/{game_id}/deadline")
    assert resp.status_code == 200
    return resp.json()


def _seat_user_id(game_id: str, power: str) -> Any:
    return db_service.get_player_by_game_id_and_power(game_id=int(game_id), power=power).user_id


# Each case: (client, game_id, seats) -> (send the request, check the stored write
# and return the response the route must give).
Request = Callable[[], Any]
Check = Callable[[], dict[str, Any]]


def _quit(client: TestClient, game_id: str, seats: dict[str, str]) -> tuple[Request, Check]:
    def check() -> dict[str, Any]:
        assert _seat_user_id(game_id, "GERMANY") is None
        return {"status": "ok"}

    return lambda: client.post(f"/games/{game_id}/quit", json=_as(seats["GERMANY"])), check


def _replace(client: TestClient, game_id: str, seats: dict[str, str]) -> tuple[Request, Check]:
    assert client.post(f"/games/{game_id}/quit", json=_as(seats["GERMANY"])).status_code == 200
    newcomer = _telegram_user(client, "newcomer")

    def check() -> dict[str, Any]:
        assert _seat_user_id(game_id, "GERMANY") == db_service.get_user_by_telegram_id(newcomer).id
        return {"status": "ok", "message": "Player replaced successfully"}

    return lambda: client.post(f"/games/{game_id}/replace", json=_as(newcomer, power="GERMANY")), check


def _propose(client: TestClient, game_id: str, seats: dict[str, str]) -> tuple[Request, Check]:
    def check() -> dict[str, Any]:
        proposal = _deadline_view(client, game_id)["pending_proposal"]
        assert (proposal["proposed_by"], proposal["value_hours"], proposal["yes_votes"]) == ("FRANCE", 24.0, ["FRANCE"])
        return {"status": "pending", **proposal}

    return (
        lambda: client.post(f"/games/{game_id}/deadline/propose", json=_as(seats["FRANCE"], power="FRANCE", hours=24.0)),
        check,
    )


def _vote(client: TestClient, game_id: str, seats: dict[str, str]) -> tuple[Request, Check]:
    proposed = client.post(f"/games/{game_id}/deadline/propose", json=_as(seats["FRANCE"], power="FRANCE", hours=24.0))
    assert proposed.json()["status"] == "pending"

    def check() -> dict[str, Any]:
        proposal = _deadline_view(client, game_id)["pending_proposal"]
        assert proposal["yes_votes"] == ["FRANCE", "GERMANY"]
        return {"status": "pending", **proposal}

    return (
        lambda: client.post(f"/games/{game_id}/deadline/vote", json=_as(seats["GERMANY"], power="GERMANY", vote=True)),
        check,
    )


def _schedule(client: TestClient, game_id: str, seats: dict[str, str]) -> tuple[Request, Check]:
    def check() -> dict[str, Any]:
        view = _deadline_view(client, game_id)
        assert view["schedule"]["description"] == "Mon, Wed, Fri at 16:00 (UTC)"
        assert view["deadline"] is not None
        # The route answers the armed deadline tz-aware; it is stored naive UTC.
        return {"status": "ok", "schedule": view["schedule"], "deadline": f"{view['deadline']}+00:00"}

    return (
        lambda: client.post(
            f"/games/{game_id}/deadline/schedule",
            json=_as(seats["FRANCE"], schedule="Mon,Wed,Fri 16:00", timezone="UTC"),
        ),
        check,
    )


def _set_deadline(client: TestClient, game_id: str, seats: dict[str, str]) -> tuple[Request, Check]:
    when = (utcnow_naive() + timedelta(days=1)).replace(microsecond=0).isoformat()

    def check() -> dict[str, Any]:
        view = _deadline_view(client, game_id)
        assert view["deadline"] == when
        return {"status": "ok", "deadline": when, "phase_length_seconds": view["phase_length_seconds"]}

    return lambda: client.post(f"/games/{game_id}/deadline", json=_as(seats["FRANCE"], deadline=when)), check


def _restore(client: TestClient, game_id: str, seats: dict[str, str]) -> tuple[Request, Check]:
    snaps = client.get(f"/games/{game_id}/snapshots").json()["snapshots"]
    (opening,) = [s["id"] for s in snaps if s["turn"] == 0]
    assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    assert game_service.load(game_id).state.phase_name == "F1901M"

    def check() -> dict[str, Any]:
        assert game_service.load(game_id).state.phase_name == "S1901M"
        return {"status": "ok", "snapshot_id": opening, "phase_code": "S1901M"}

    return lambda: client.post(f"/games/{game_id}/restore/{opening}", headers={"X-Admin-Token": ADMIN_TOKEN}), check


@pytest.mark.parametrize(
    "case",
    [_quit, _replace, _propose, _vote, _schedule, _set_deadline, _restore],
    ids=["quit", "replace", "deadline-propose", "deadline-vote", "deadline-schedule", "deadline-set", "restore"],
)
def test_a_failed_notification_still_answers_200_and_keeps_the_write(
    client: TestClient, case: Callable[[TestClient, str, dict[str, str]], tuple[Request, Check]]
) -> None:
    game_id, seats = _game(client)
    send, check = case(client, game_id, seats)
    with patch("server.api.routes.games.notify_players", side_effect=RuntimeError("outbox down")) as notify:
        resp = send()
    assert notify.call_count == 1
    assert resp.status_code == 200, resp.text
    assert resp.json() == check()


# -- the repository on a missing game ------------------------------------------


def test_save_state_on_a_missing_game_raises_value_error() -> None:
    with pytest.raises(ValueError) as err:
        game_service._repo.save_state("no-such-game", {}, phase_code="S1901M", status="active")
    assert str(err.value) == "game no-such-game not found"


def test_modify_state_json_on_a_missing_game_raises_value_error() -> None:
    def change(current: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("change must not run for a missing game")

    with pytest.raises(ValueError) as err:
        game_service._repo.modify_state_json("no-such-game", change)
    assert str(err.value) == "game no-such-game not found"
