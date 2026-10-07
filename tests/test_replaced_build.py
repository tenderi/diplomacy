"""BD6: the bot says which build a new one replaced.

The bot sends adjustment orders one at a time (``merge``). When a new build
exceeds the power's allowance, ``GameService._make_room`` drops the oldest
stored one -- and nobody said so: ``/order BUILD A PAR`` after
``BUILD F BRE`` answered "✅ BUILD A PAR" and BRE's fleet quietly vanished.
``POST /games/set_orders`` now names the displaced orders per result
(``replaced``, ``note``) and every bot reply that reports results shows it.

The bot's HTTP calls are answered by the real API (``requests.post`` routed
to a ``TestClient``), so the API's response shape and the bot's text are
checked together.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests
from fastapi.testclient import TestClient

from engine.serialization import state_to_dict
from engine.types import GameState, Location, PhaseType, Season, Unit, UnitKind
from server.api import app
from server.api.shared import game_service
from server.telegram_bot import api_client
from server.telegram_bot.api_client import drain_outbox_once
from server.telegram_bot.notifications import format_delivery_report
from server.telegram_bot.orders import order, submit_interactive_order
from server.telegram_bot.outbox import reset_outbox_for_tests
from tests.conftest import _get_db_url
from tests.table_helpers import fill_with_dummies
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

BOT = {"X-Bot-Secret": BOT_SECRET}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def fresh_outbox(tmp_path):
    return reset_outbox_for_tests(tmp_path / "outbox.sqlite3")


def _posts_through(client: TestClient) -> Any:
    """``requests.post`` for the bot's ``api_client``, answered by the real API."""
    def post(url: str, json: dict, headers: dict, timeout: int) -> requests.Response:
        r = client.post(url.removeprefix(api_client.API_URL), json=json, headers=headers)
        resp = requests.Response()
        resp.status_code = r.status_code
        resp._content = r.content
        return resp
    return post


def _france_in_winter(client: TestClient, units: list[Unit], centres: list[str]) -> tuple[str, str]:
    """A game in W1901A with FRANCE seated (Telegram id returned) on ``units``/``centres``."""
    tg = _telegram_user(client, "france")
    resp = client.post("/games/create", json=_as(tg, map_name="standard"), headers=BOT)
    assert resp.status_code == 200, resp.text
    game_id = str(resp.json()["game_id"])
    assert client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE")).status_code == 200
    fill_with_dummies(game_id)
    state = GameState(
        1901, Season.WINTER, PhaseType.ADJUSTMENT,
        units=frozenset(units), ownership={c: "FRANCE" for c in centres},
    )
    game_service.restore_snapshot(game_id, state_to_dict(state), phase_code="W1901A")
    return game_id, tg


def _one_build(client: TestClient) -> tuple[str, str]:
    """FRANCE: 3 centres, 2 units, PAR and BRE vacant -- one build."""
    return _france_in_winter(
        client,
        [Unit(UnitKind.ARMY, "FRANCE", Location("MAR")), Unit(UnitKind.FLEET, "FRANCE", Location("MAO"))],
        ["PAR", "BRE", "MAR"],
    )


def _bot_order(client: TestClient, game_id: str, tg: str, text: str) -> str:
    """``/order <text>`` from the bot, through the real API; returns the reply."""
    update = Mock()
    update.effective_user = Mock(id=int(tg))
    update.message = Mock()
    update.message.reply_text = AsyncMock()
    context = Mock()
    context.args = text.split()
    with patch.object(api_client, "BOT_SECRET", BOT_SECRET), \
         patch.object(api_client.requests, "post", side_effect=_posts_through(client)), \
         patch("server.telegram_bot.orders.resolve_game_and_power", return_value=(game_id, "FRANCE")):
        asyncio.run(order(update, context))
    return update.message.reply_text.call_args[0][0]


class TestTheApiNamesTheReplacedBuild:
    def test_a_build_past_the_allowance_names_the_one_it_replaced(self, client: TestClient) -> None:
        game_id, tg = _one_build(client)
        body = _as(tg, game_id=game_id, power="FRANCE", merge=True)
        first = client.post("/games/set_orders", json={**body, "orders": ["BUILD F BRE"]})
        assert first.json()["results"] == [
            {"order": "BUILD F BRE", "success": True, "error": None, "replaced": [], "note": None}
        ]
        second = client.post("/games/set_orders", json={**body, "orders": ["BUILD A PAR"]})
        assert second.json()["results"] == [{
            "order": "BUILD A PAR", "success": True, "error": None,
            "replaced": ["BUILD F BRE"], "note": "replaced BUILD F BRE (you may build 1)",
        }]
        assert game_service.pending_orders_view(game_id)["FRANCE"] == ["BUILD A PAR"]

    def test_a_disband_past_the_count_names_the_one_it_replaced(self, client: TestClient) -> None:
        game_id, tg = _france_in_winter(
            client,
            [Unit(UnitKind.ARMY, "FRANCE", Location("MAR")), Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))],
            ["PAR"],
        )
        body = _as(tg, game_id=game_id, power="FRANCE", merge=True)
        client.post("/games/set_orders", json={**body, "orders": ["D A MAR"]})
        resp = client.post("/games/set_orders", json={**body, "orders": ["D A PAR"]})
        assert resp.json()["results"] == [{
            "order": "D A PAR", "success": True, "error": None,
            "replaced": ["D A MAR"], "note": "replaced D A MAR (you must disband 1)",
        }]


class TestTheBotSaysSo:
    def test_order_reply_names_the_replaced_build(self, client: TestClient) -> None:
        game_id, tg = _one_build(client)
        assert _bot_order(client, game_id, tg, "BUILD F BRE") == "Order results:\n✅ BUILD F BRE"
        assert _bot_order(client, game_id, tg, "BUILD A PAR") == (
            "Order results:\n✅ BUILD A PAR replaced BUILD F BRE (you may build 1)"
        )

    def test_a_waive_that_replaces_a_build_says_so(self, client: TestClient) -> None:
        game_id, tg = _one_build(client)
        _bot_order(client, game_id, tg, "BUILD F BRE")
        assert _bot_order(client, game_id, tg, "WAIVE") == (
            "Order results:\n✅ WAIVE replaced BUILD F BRE (you may build 1)"
        )

    def test_a_build_within_the_allowance_reads_as_before(self, client: TestClient) -> None:
        game_id, tg = _france_in_winter(
            client, [Unit(UnitKind.ARMY, "FRANCE", Location("MAR"))], ["PAR", "BRE", "MAR"],
        )
        assert _bot_order(client, game_id, tg, "BUILD F BRE") == "Order results:\n✅ BUILD F BRE"
        assert _bot_order(client, game_id, tg, "BUILD A PAR") == "Order results:\n✅ BUILD A PAR"
        assert game_service.pending_orders_view(game_id)["FRANCE"] == ["BUILD F BRE", "BUILD A PAR"]

    def test_the_interactive_pick_names_the_replaced_build(self, client: TestClient) -> None:
        game_id, tg = _one_build(client)
        _bot_order(client, game_id, tg, "BUILD F BRE")
        query = Mock()
        query.from_user = Mock(id=int(tg))
        query.edit_message_text = AsyncMock()
        with patch.object(api_client, "BOT_SECRET", BOT_SECRET), \
             patch.object(api_client.requests, "post", side_effect=_posts_through(client)), \
             patch("server.telegram_bot.orders.resolve_game_and_power", return_value=(game_id, "FRANCE")):
            asyncio.run(submit_interactive_order(query, game_id, "BUILD A PAR"))
        assert query.edit_message_text.call_args[0][0] == (
            f"✅ *Order submitted:* `BUILD A PAR`\n🎮 Game {game_id} · FRANCE\n"
            "↩️ This replaced BUILD F BRE (you may build 1)"
        )

    def test_a_queued_build_reports_the_replacement_when_it_is_delivered(
        self, client: TestClient, fresh_outbox
    ) -> None:
        game_id, tg = _one_build(client)
        _bot_order(client, game_id, tg, "BUILD F BRE")
        with patch.object(api_client.requests, "post", side_effect=requests.ConnectionError("no route")), \
             patch("server.telegram_bot.orders.resolve_game_and_power", return_value=(game_id, "FRANCE")):
            update = Mock()
            update.effective_user = Mock(id=int(tg))
            update.message = Mock()
            update.message.reply_text = AsyncMock()
            context = Mock()
            context.args = ["BUILD", "A", "PAR"]
            asyncio.run(order(update, context))
        assert "queued" in update.message.reply_text.call_args[0][0]
        fresh_outbox._conn.execute("UPDATE outbox SET next_attempt_at = NULL")  # due now
        with patch.object(api_client, "BOT_SECRET", BOT_SECRET), \
             patch.object(api_client.requests, "post", side_effect=_posts_through(client)):
            [result] = drain_outbox_once()
        report = format_delivery_report(result)
        assert report.splitlines()[1:] == ["✅ BUILD A PAR replaced BUILD F BRE (you may build 1)"]
        assert report.splitlines()[0].endswith(f"orders for game {game_id} (FRANCE): BUILD A PAR")
