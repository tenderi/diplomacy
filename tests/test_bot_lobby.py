"""DQ1: the bot treats a game that hasn't filled as not started, and the first build step has no empty row."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import Mock, patch

import pytest

from server.telegram_bot import games, hub, orders
from tests.test_order_all_flow import Chat, api  # noqa: F401  (api is a fixture)

pytestmark = pytest.mark.unit

UNSEATED = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA"]
LOBBY = (
    "⏳ Game 2 hasn't started: waiting for 6 more players "
    "(AUSTRIA, ENGLAND, FRANCE, GERMANY, ITALY, RUSSIA). "
    "Others can join with /join 2; orders open once every seat is filled."
)
STATUS = {"phase": "S1901M", "submitted": [], "missing": ["TURKEY"] + UNSEATED, "unseated": UNSEATED, "auto_process": True}


def _get(path: str, **_kw: Any) -> Any:
    if path.endswith("/state"):
        return {"phase": "S1901M", "phase_type": "MOVEMENT", "status": "ACTIVE"}
    if path.endswith("/orders_status"):
        return STATUS
    if path.endswith("/deadline"):
        return {}
    if path.endswith("/draw_vote_status"):
        return {"votes": [], "required": ["TURKEY"] + UNSEATED}
    if "legal_orders" in path:
        return {"phase_type": "MOVEMENT", "units": [{"kind": "A", "location": "CON"}],
                "orders_by_unit": {"A CON": ["A CON H"]}}
    return None


def test_status_text_says_the_game_has_not_started() -> None:
    with patch.object(games, "api_get", side_effect=_get):
        text = games.status_text("2", "TURKEY", "5")
    assert text == f"📊 *Game 2 Status*\n\n🎯 *You are:* TURKEY\n{LOBBY}\n"


def test_status_text_after_the_first_turn_ignores_a_reopened_seat() -> None:
    def get(path: str, **kw: Any) -> Any:
        if path.endswith("/orders_status"):
            return {**STATUS, "phase": "F1901M"}
        return _get(path, **kw)

    with patch.object(games, "api_get", side_effect=get):
        assert "hasn't started" not in games.status_text("2", "TURKEY", "5")


def test_hub_offers_no_order_buttons_in_a_lobby() -> None:
    sent: list[tuple[str, Any]] = []

    async def send(text: str, reply_markup=None, **_kw) -> None:
        sent.append((text, reply_markup))

    with patch.object(hub, "resolve_game_and_power", return_value=("2", "TURKEY")), \
         patch.object(hub, "fetch_user_games", return_value=[]), \
         patch.object(games, "api_get", side_effect=_get), \
         patch.object(hub, "api_get", side_effect=_get):
        asyncio.run(hub.show_hub(send, "5", "2"))
    text, markup = sent[0]
    labels = [b.text for row in markup.inline_keyboard for b in row]
    assert LOBBY in text and "Waiting on" not in text and "Draw vote" not in text
    assert "📝 Order all units" not in labels and "🎯 One unit" not in labels
    assert not any("Wait for me" in label for label in labels)
    assert "📋 My orders" in labels


def test_order_buttons_in_a_lobby_say_the_game_has_not_started(api) -> None:  # noqa: F811
    api.get.side_effect = _get
    chat = Chat()
    chat.command(["1"])
    assert chat.text == LOBBY.replace("Game 2", "Game 1").replace("join 2", "join 1") and not chat.buttons


def test_first_build_step_has_no_empty_keyboard_row() -> None:
    context = Mock()
    context.user_data = {orders._WALK: {"2": {
        "power": "TURKEY", "phase": "W1901A", "adjust": True, "action": "build", "duty": "",
        "steps": ["Build 1"], "flat": ["BUILD A CON", "WAIVE"], "i": 0, "chosen": {}, "existing": [],
        "replace": False,
    }}}
    sent: list[Any] = []

    async def send(text: str, reply_markup=None, **_kw) -> None:
        sent.append(reply_markup)

    asyncio.run(orders.show_walk_step(send, context, "2"))
    assert all(row for row in sent[0].inline_keyboard)
