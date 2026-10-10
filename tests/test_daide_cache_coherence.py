"""DAIDE order writes invalidate the cached game reads (BD11).

`SUB` and `NOT (SUB)` change a power's pending orders. Like the HTTP order routes
they must run ``invalidate_cache("games/{id}")``, through the ``on_orders_changed``
hook `_api_module` gives `DaideServer`, or `GET /games/{id}/state` keeps its copy
from before the write for the rest of its 30 s TTL.
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from server.daide import tokens as t
from server.daide.tokens import Token
from server.daide.server import DaideServer
from server.daide.session import DaideSession
from server.response_cache import _response_cache, clear_response_cache, invalidate_cache
from tests.test_daide_draw_notifications import _Writer, _send
from tests.test_draw_concede_notifications import _seeded_game

pytestmark = [pytest.mark.integration, pytest.mark.database]


def _warm(client: TestClient, game_id: str) -> None:
    clear_response_cache()
    assert client.get(f"/games/{game_id}/state").status_code == 200
    assert len(_response_cache.cache) == 1


def _paren(*inner: Token) -> list[Token]:
    return [t.OPEN_PAREN, *inner, t.CLOSE_PAREN]


def _wired_seat(game_id: str, power: str) -> DaideSession:
    """A seat on a listener wired the way `_api_module` wires the real one."""
    server = DaideServer(
        api_shared.game_service, game_id=game_id, on_orders_changed=lambda gid: invalidate_cache(f"games/{gid}")
    )
    session = DaideSession(None, _Writer(), server)
    session.power = power
    session.game_id = game_id
    server.register(game_id, power, session)
    return session


async def test_sub_drops_the_cached_state() -> None:
    client = TestClient(app)
    game_id, _users = _seeded_game(client)
    session = _wired_seat(game_id, "FRANCE")
    _warm(client, game_id)

    await _send(session, t.SUB, *_paren(*_paren(t.FRA, t.AMY, t.PAR), t.HLD))

    assert api_shared.game_service.pending_orders_parsed(game_id)["FRANCE"]
    assert len(_response_cache.cache) == 0


async def test_not_sub_drops_the_cached_state() -> None:
    client = TestClient(app)
    game_id, _users = _seeded_game(client)
    session = _wired_seat(game_id, "FRANCE")
    _warm(client, game_id)

    await _send(session, t.NOT, *_paren(t.SUB))

    assert len(_response_cache.cache) == 0


def test_the_api_wires_the_daide_listener_to_the_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIPLOMACY_DAIDE_PORT", "0")
    with TestClient(app):
        daide: Any = api_shared.daide_server
        assert daide is not None
        assert daide.on_orders_changed is not None
