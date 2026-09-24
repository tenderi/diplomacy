"""After every processed turn a game's Telegram group gets two maps: the orders, drawn
on the board they were given on, and the result. Both are fetched by turn number, so
a post delivered late still shows the turn it announces."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests
from fastapi.testclient import TestClient

from rendering.view_adapter import units_for_render
from server.api import app
from server.api.shared import game_service, phase_label
from server.telegram_bot import notifications
from server.telegram_bot.api_client import ApiUnreachableError
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

BOT = {"X-Bot-Secret": BOT_SECRET}
GROUP = "-1004242"
PNG = b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize(("code", "label"), [
    ("S1901M", "Spring 1901 movement"), ("F1902R", "Fall 1902 retreats"), ("W1903A", "Winter 1903 builds"), ("odd", "odd"),
])
def test_phase_label(code: str, label: str) -> None:
    assert phase_label(code) == label


def test_dislodged_units_are_drawn_where_they_were_knocked_out() -> None:
    view = {
        "units_by_power": {"GERMANY": [{"kind": "A", "power": "GERMANY", "location": "BUR"}]},
        "dislodged": [{"unit": {"kind": "F", "power": "FRANCE", "location": "SPA/SC"}, "attacker_origin": "MAR", "retreats": []}],
    }
    assert units_for_render(view) == {"GERMANY": ["A BUR"], "FRANCE": ["F DISLODGED_SPA"]}


needs_db = pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")


@needs_db
@pytest.mark.map
class TestTheGroupSeesEachTurn:
    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def _group_game(self, client: TestClient, settings: dict | None = None) -> str:
        creator = _telegram_user(client, "mapper")
        game_id = str(client.post("/games/create", json=_as(creator, map_name="standard"), headers=BOT).json()["game_id"])
        link = {"channel_id": GROUP, **({"settings": settings} if settings else {})}
        assert client.post(f"/games/{game_id}/channel/link", json=link, headers=BOT).status_code == 200
        return game_id

    def _process(self, client: TestClient, game_id: str, orders: dict[str, list[str]]) -> list[dict[str, Any]]:
        for power, power_orders in orders.items():
            game_service.submit_orders(game_id, power, power_orders)
        with OutboxProbe() as probe:
            assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
        return [r for r in probe.rows() if str(r["telegram_id"]) == GROUP]

    def test_a_processed_turn_posts_the_orders_then_the_result(self, client: TestClient) -> None:
        game_id = self._group_game(client)
        rows = self._process(client, game_id, {"FRANCE": ["A PAR - BUR"], "GERMANY": ["A MUN - BUR"]})
        maps = [(r["message"], r["payload"]["path"]) for r in rows if r["kind"] == "channel_map"]
        assert maps == [
            (f"📝 Game {game_id} · Spring 1901 movement: the orders", f"/games/{game_id}/map/turn/0/orders"),
            (f"🗺️ Game {game_id} · Spring 1901 movement: the result", f"/games/{game_id}/map/history/1"),
        ]
        assert [r["kind"] for r in rows] == ["channel_text", "channel_map", "channel_map"]

    def test_the_orders_map_is_the_opening_board_with_the_bounce_marked(self, client: TestClient) -> None:
        game_id = self._group_game(client)
        self._process(client, game_id, {"FRANCE": ["A PAR - BUR"], "GERMANY": ["A MUN - BUR"]})
        with patch("server.api.routes.maps.Map.render_board_png_resolution", return_value=PNG) as render:
            resp = client.get(f"/games/{game_id}/map/turn/0/orders")
        assert (resp.status_code, resp.content) == (200, PNG)
        _svg, units, order_viz, resolution_data = render.call_args.args[:4]
        assert "A PAR" in units["FRANCE"] and "A MUN" in units["GERMANY"]
        assert {o["status"] for o in order_viz["FRANCE"] if o.get("target") == "BUR"} == {"bounced"}
        assert resolution_data["conflicts"] == [{"province": "BUR", "result": "standoff"}]
        assert render.call_args.kwargs["phase_info"]["phase_code"] == "S1901M"

    def test_both_paths_render_real_images(self, client: TestClient) -> None:
        game_id = self._group_game(client)
        self._process(client, game_id, {"FRANCE": ["A PAR - PIC"]})
        for path in (f"/games/{game_id}/map/turn/0/orders", f"/games/{game_id}/map/history/1"):
            resp = client.get(path)
            assert resp.status_code == 200 and resp.content.startswith(PNG), path

    def test_a_later_turns_orders_are_drawn_on_that_turns_board(self, client: TestClient) -> None:
        game_id = self._group_game(client)
        self._process(client, game_id, {"FRANCE": ["A PAR - PIC"]})
        self._process(client, game_id, {"FRANCE": ["A PIC - BEL"]})
        with patch("server.api.routes.maps.Map.render_board_png_resolution", return_value=PNG) as render:
            assert client.get(f"/games/{game_id}/map/turn/1/orders").status_code == 200
        units = render.call_args.args[1]
        assert "A PIC" in units["FRANCE"] and "A PAR" not in units["FRANCE"]
        assert render.call_args.kwargs["phase_info"]["phase_code"] == "F1901M"

    def test_maps_off_means_no_maps(self, client: TestClient) -> None:
        game_id = self._group_game(client, settings={"auto_post_maps": False})
        rows = self._process(client, game_id, {"FRANCE": ["A PAR H"]})
        assert [r["kind"] for r in rows] == ["channel_text"]

    def test_a_turn_not_yet_played_has_no_orders_map(self, client: TestClient) -> None:
        game_id = self._group_game(client)
        assert client.get(f"/games/{game_id}/map/turn/0/orders").status_code == 404
        assert client.get("/games/999999999/map/turn/0/orders").status_code == 404


class TestBotDelivery:
    def _row(self, row_id: int, payload: dict) -> dict:
        return {"id": row_id, "telegram_id": GROUP, "kind": "channel_map", "message": "caption", "payload": payload}

    def test_a_map_row_fetches_its_own_path(self) -> None:
        bot = Mock(send_photo=AsyncMock())
        with patch.object(notifications, "api_get_bytes", return_value=PNG) as fetch:
            asyncio.run(notifications._send_outbox_item(bot, int(GROUP), self._row(1, {"game_id": "7", "path": "/games/7/map/turn/3/orders"})))
            asyncio.run(notifications._send_outbox_item(bot, int(GROUP), self._row(2, {"game_id": "7"})))
        assert [c.args[0] for c in fetch.call_args_list] == ["/games/7/map/turn/3/orders", "/games/7/map"]
        assert bot.send_photo.call_args.kwargs["caption"] == "caption"

    def test_an_image_the_api_refuses_is_failed_and_does_not_block_the_rest(self) -> None:
        bad = self._row(1, {"game_id": "7", "path": "/games/7/map/turn/9/orders"})
        good = {"id": 2, "telegram_id": "555", "kind": "dm", "message": "Your turn", "payload": {}}
        refused = requests.HTTPError("No orders recorded for this turn.")
        bot = Mock(send_photo=AsyncMock(), send_message=AsyncMock())
        with patch.object(notifications, "api_get", return_value={"items": [bad, good]}), \
             patch.object(notifications, "api_get_bytes", side_effect=refused), \
             patch.object(notifications, "api_post") as ack:
            assert asyncio.run(notifications.deliver_pending_notifications(bot)) == (1, 1)
        body = ack.call_args.args[1]
        assert body["delivered"] == [2]
        assert body["failed"] == {1: "image unavailable: No orders recorded for this turn."}

    def test_losing_the_api_mid_image_retries_later(self) -> None:
        row = self._row(1, {"game_id": "7", "path": "/games/7/map/history/1"})
        with patch.object(notifications, "api_get", return_value={"items": [row]}), \
             patch.object(notifications, "api_get_bytes", side_effect=ApiUnreachableError(ConnectionError("down"))), \
             patch.object(notifications, "api_post") as ack:
            assert asyncio.run(notifications.deliver_pending_notifications(Mock())) == (0, 0)
        ack.assert_not_called()  # the row stays queued
