"""DY1: one user, one seat per game, even when two of their joins race.

``join_game`` (and ``replace_player``) checked "is this user already in the
game?" with a plain read, then wrote the seat in another transaction. Two joins
by one user at once (a double-click on Join, the web and the bot together) both
passed the check, and the user held two powers. The seat writes now re-check
under the game-row lock, and ``uq_players_game_user`` is the backstop.

Each race is forced: both requests are held right after their "already
joined?" read until both have made it, so both see no seat.
"""
from __future__ import annotations

import importlib.util
import threading
from pathlib import Path
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from server._api_module import app
from server.api.shared import db_service
from server.response_cache import clear_response_cache
from tests.bot_client import BotTestClient
from tests.conftest import _get_db_url
from tests.test_seat_guards import _as, _game, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]


@pytest.fixture
def client() -> TestClient:
    clear_response_cache()
    return BotTestClient(app)


def _race(monkeypatch: pytest.MonkeyPatch, requests: list[tuple[str, dict[str, object]]]) -> list[Any]:
    """Post each ``(path, body)`` from its own thread, all held after their first
    "already in the game?" read until every one has made it."""
    barrier = threading.Barrier(len(requests), timeout=10)
    waited = threading.local()
    real: Callable[..., Any] = db_service.get_player_by_game_id_and_user_id

    def read_then_wait(*args: Any, **kwargs: Any) -> Any:
        seat = real(*args, **kwargs)
        if not getattr(waited, "done", False):
            waited.done = True
            barrier.wait()
        return seat

    monkeypatch.setattr(db_service, "get_player_by_game_id_and_user_id", read_then_wait)
    out: list[Any] = [None] * len(requests)

    def post(i: int) -> None:
        path, body = requests[i]
        out[i] = BotTestClient(app).post(path, json=body)

    threads = [threading.Thread(target=post, args=(i,)) for i in range(len(requests))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    monkeypatch.undo()
    return out


def _user_id(tg: str) -> int:
    user = db_service.get_user_by_telegram_id(tg)
    assert user is not None
    return int(user.id)


def _seats_of(client: TestClient, game_id: str, tg: str) -> list[str]:
    return sorted(
        str(p.power_name) for p in db_service.get_players_by_game_id(int(game_id)) if p.user_id == _user_id(tg)
    )


def _one_joined_one_already(responses: list[Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    assert [r.status_code for r in responses] == [200, 200], [r.text for r in responses]
    bodies = sorted((r.json() for r in responses), key=lambda b: b["status"])
    already, joined = bodies
    assert joined["status"] == "ok" and already["status"] == "already_joined", bodies
    return joined, already


def test_a_double_click_on_join_in_a_random_powers_game_seats_once(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, _ = _game(client, [], random_powers=True)
    tg = _telegram_user(client)
    path = f"/games/{game_id}/join"
    joined, already = _one_joined_one_already(_race(monkeypatch, [(path, _as(tg)), (path, _as(tg))]))
    assert already == {"status": "already_joined", "player_id": joined["player_id"], "power": joined["power"]}
    assert _seats_of(client, game_id, tg) == [joined["power"]]


def test_two_powers_chosen_at_once_by_one_user_seat_one(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, _ = _game(client, [])
    tg = _telegram_user(client)
    path = f"/games/{game_id}/join"
    joined, already = _one_joined_one_already(
        _race(monkeypatch, [(path, _as(tg, power="FRANCE")), (path, _as(tg, power="ENGLAND"))])
    )
    assert already == {"status": "already_joined", "player_id": joined["player_id"], "power": joined["power"]}
    assert _seats_of(client, game_id, tg) == [joined["power"]]


def test_two_replaces_at_once_by_one_user_take_one_seat(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, seated = _game(client, ["ITALY", "GERMANY"])
    for power in ("ITALY", "GERMANY"):
        r = client.post(f"/games/{game_id}/quit", json=_as(seated[power], power=power))
        assert r.status_code == 200, r.text
    tg = _telegram_user(client)
    path = f"/games/{game_id}/replace"
    responses = _race(monkeypatch, [(path, _as(tg, power="ITALY")), (path, _as(tg, power="GERMANY"))])
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    won = 0 if responses[0].status_code == 200 else 1
    assert responses[won].json() == {"status": "ok", "message": "Player replaced successfully"}
    assert responses[1 - won].json() == {"detail": "User is already in the game"}
    assert _seats_of(client, game_id, tg) == [["ITALY", "GERMANY"][won]]


def test_the_index_refuses_a_second_seat_written_past_the_lock(client: TestClient) -> None:
    """The backstop: a seat write that skipped the locked re-check still cannot
    seat the user twice, and the DAL reports the seat they hold."""
    from persistence.database_service import SeatHeldError

    game_id, seated = _game(client, ["FRANCE"])
    row = db_service.get_game_by_game_id(game_id)
    assert row is not None
    france = db_service.get_player_by_game_id_and_power(game_id=int(game_id), power="FRANCE")
    assert france is not None
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("persistence.database_service._lock_game_for_seat", lambda *a, **k: None)
        with pytest.raises(SeatHeldError) as held:
            db_service.create_player(int(row.id), "ITALY", user_id=_user_id(seated["FRANCE"]))
    assert (held.value.player_id, held.value.power) == (int(france.id), "FRANCE")
    assert _seats_of(client, game_id, seated["FRANCE"]) == ["FRANCE"]


def _migration() -> Any:
    path = Path(__file__).resolve().parent.parent / "alembic/versions/d8f4a5b6c7d8_one_seat_per_user_per_game.py"
    spec = importlib.util.spec_from_file_location("one_seat_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_migration_vacates_a_users_later_seats_and_keeps_the_earliest(client: TestClient) -> None:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    game_id, seated = _game(client, ["FRANCE"])
    row = db_service.get_game_by_game_id(game_id)
    assert row is not None
    user_id = _user_id(seated["FRANCE"])
    engine = create_engine(_get_db_url())
    with engine.connect() as conn:
        trans = conn.begin()  # Postgres DDL is transactional: all of it is rolled back
        try:
            conn.execute(text("DROP INDEX uq_players_game_user"))
            for power in ("ITALY", "GERMANY"):
                conn.execute(
                    text("INSERT INTO players (game_id, power_name, user_id, is_active) VALUES (:g, :p, :u, true)"),
                    {"g": int(row.id), "p": power, "u": user_id},
                )
            with Operations.context(MigrationContext.configure(conn)):
                _migration().upgrade()
            seats = conn.execute(
                text("SELECT power_name, user_id, is_active FROM players WHERE game_id = :g ORDER BY id"),
                {"g": int(row.id)},
            ).all()
            assert [tuple(s) for s in seats] == [("FRANCE", user_id, True), ("ITALY", None, False), ("GERMANY", None, False)]
            index = conn.execute(
                text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_players_game_user'")
            ).scalar_one()
            assert index == (
                "CREATE UNIQUE INDEX uq_players_game_user ON public.players USING btree (game_id, user_id) "
                "WHERE (user_id IS NOT NULL)"
            )
        finally:
            trans.rollback()
    engine.dispose()
