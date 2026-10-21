"""BJ3 / BJ4 / BO1: a fully refused replacement changes nothing; an army build names no coast."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api.shared import game_service
from tests.conftest import _get_db_url
from tests.test_quit_and_replace import _as
from tests.test_replaced_build import _one_build

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_all_refused_non_merge_submission_keeps_the_earlier_orders(client: TestClient) -> None:
    game_id, tg = _one_build(client)
    body = _as(tg, game_id=game_id, power="FRANCE")
    ok = client.post("/games/set_orders", json={**body, "orders": ["BUILD F BRE"]})
    assert ok.json()["results"][0]["success"] is True
    resp = client.post("/games/set_orders", json={**body, "orders": ["BUILD A MUN"]})
    assert resp.json()["results"] == [{
        "order": "BUILD A MUN", "success": False, "error": "MUN is not a home supply center of FRANCE",
        "replaced": [], "superseded_by": None,
        "note": "none of these orders was accepted, so nothing was changed. Your earlier orders stand: BUILD F BRE",
    }]
    assert game_service.pending_orders_view(game_id)["FRANCE"] == ["BUILD F BRE"]


def test_partly_valid_replace_still_replaces(client: TestClient) -> None:
    game_id, tg = _one_build(client)
    body = _as(tg, game_id=game_id, power="FRANCE")
    client.post("/games/set_orders", json={**body, "orders": ["BUILD F BRE"]})
    resp = client.post("/games/set_orders", json={**body, "orders": ["BUILD A MUN", "BUILD A PAR"]})
    assert [r["success"] for r in resp.json()["results"]] == [False, True]
    assert game_service.pending_orders_view(game_id)["FRANCE"] == ["BUILD A PAR"]


def test_accepted_replacement_reports_nothing_dropped(client: TestClient) -> None:
    game_id, tg = _one_build(client)
    body = _as(tg, game_id=game_id, power="FRANCE")
    client.post("/games/set_orders", json={**body, "orders": ["BUILD F BRE"]})
    resp = client.post("/games/set_orders", json={**body, "orders": ["BUILD A PAR"]})
    assert resp.json()["results"][0]["replaced"] == []


def test_army_build_with_coast_is_refused(client: TestClient) -> None:
    game_id, tg = _one_build(client)
    body = _as(tg, game_id=game_id, power="FRANCE")
    resp = client.post("/games/set_orders", json={**body, "orders": ["BUILD A BRE/NC", "A PAR BUILD"]})
    assert [(r["success"], r["error"]) for r in resp.json()["results"]] == [
        (False, "parse error: an army build may not specify a coast"),
        (True, None),
    ]
    assert game_service.pending_orders_view(game_id)["FRANCE"] == ["BUILD A PAR"]
