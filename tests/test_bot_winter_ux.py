"""Track DA: the bot's adjustment-phase (winter) texts and buttons."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from server.telegram_bot import hub, orders as bot_orders
from server.telegram_bot.orders import adjustment_duty, run_process_turn
from tests.test_order_all_flow import ADJUSTMENT, Chat, api  # noqa: F401  (api is a fixture)

pytestmark = pytest.mark.unit

NAMES = {"BUD": "Budapest", "STP": "St Petersburg"}
DISBAND = {
    **ADJUSTMENT,
    "adjustment": {"delta": -1, "action": "disband", "slots": 1},
    "orders": ["D A BUD", "D F STP/NC"],
}


@pytest.fixture(autouse=True)
def names():
    bot_orders._reset_province_names_cache()
    bot_orders._PROVINCE_NAMES.update(NAMES)
    bot_orders._PROVINCE_NAMES_FETCHED = True
    yield
    bot_orders._reset_province_names_cache()


def test_labels_are_readable_and_disband_is_not_a_cross() -> None:
    assert bot_orders._order_label("D A BUD") == "✂️ Disband army Budapest (BUD)"
    assert bot_orders._order_label("BUILD F STP/NC") == "🏗️ Build fleet St Petersburg north coast (STP/NC)"
    assert bot_orders._order_label("WAIVE") == "⏭️ Waive build"


def test_duty_lines() -> None:
    assert adjustment_duty(ADJUSTMENT) == "You may build 2 units (free home centres: BER, KIE, MUN)."
    assert adjustment_duty(DISBAND) == "You must disband 1 unit. With no order, civil disorder picks which."
    assert adjustment_duty({"adjustment": {"action": "none", "slots": 0}}) == (
        "You have nothing to order this phase; wait for the other powers."
    )


def test_build_step_has_waive_but_no_skip_and_shows_the_duty(api) -> None:  # noqa: F811
    api.get.side_effect = lambda path, **_kw: {"phase": "W1901A"} if path.endswith("/state") else ADJUSTMENT
    chat = Chat()
    chat.command([])
    assert "Build 1 of 2" in chat.text and "You may build 2 units (free home centres: BER, KIE, MUN)." in chat.text
    labels = [t for t, _ in chat.buttons]
    assert "⏭️ Waive build" in labels and not any("Skip" in t for t in labels)


def test_disband_step_keeps_skip_and_summary_names_only_disbands(api) -> None:  # noqa: F811
    api.get.side_effect = lambda path, **_kw: {"phase": "W1901A"} if path.endswith("/state") else DISBAND
    chat = Chat()
    chat.command([])
    assert "✂️ *Disband 1 of 1*" in chat.text
    assert any("Skip" in t for t, _ in chat.buttons)
    chat.press("Skip")
    assert "A skipped build" not in chat.text and "civil-disorder rule" in chat.text


def test_process_turn_reply_carries_the_callers_own_results() -> None:
    send = AsyncMock()
    state = {"phase": "S1902M", "status": "IN_PROGRESS", "dislodged": [], "contested": []}
    post = {"status": "ok", "results": ["Your results for Winter 1901 adjustment:", "F MAR was built."]}
    with patch.object(bot_orders, "api_post", return_value=post), \
         patch.object(bot_orders, "api_get", return_value=state), \
         patch.object(bot_orders, "_owed_text", return_value="X."):
        asyncio.run(run_process_turn(send, "1", "5"))
    assert send.call_args[0][0] == (
        "✅ *Turn Processed!*\n📊 Now: Spring 1902 movement (S1902M)\n"
        "\nYour results for Winter 1901 adjustment:\nF MAR was built.\n\n🎮 X. Game menu: /game 1."
    )


def _buttons(legal: dict[str, Any] | None) -> list[str]:
    markup: Any = hub._hub_keyboard("7", "FRANCE", {"status": "ACTIVE"}, None, False, legal)
    return [b.text for row in markup.inline_keyboard for b in row]


def test_hub_buttons_follow_what_is_owed() -> None:
    assert "🏗️ Builds" in _buttons(ADJUSTMENT)
    assert "✂️ Disbands" in _buttons(DISBAND)
    for legal in (ADJUSTMENT, DISBAND):
        assert "📝 Order all units" not in _buttons(legal) and "🎯 One unit" not in _buttons(legal)
    nothing = {"phase_type": "ADJUSTMENT", "adjustment": {"action": "none", "slots": 0}}
    labels = _buttons(nothing)
    assert not any(t in labels for t in ("🏗️ Builds", "✂️ Disbands", "📝 Order all units", "🎯 One unit"))
    assert "📋 My orders" in labels
    assert "📝 Order all units" in _buttons(None)


def test_hub_text_says_what_is_owed() -> None:
    sent: list[str] = []

    async def send(text: str, reply_markup=None, **_kw) -> None:
        sent.append(text)

    def get(path: str, **_kw: Any) -> Any:
        if path.endswith("/state"):
            return {"phase_type": "ADJUSTMENT", "status": "ACTIVE"}
        if "legal_orders" in path:
            return ADJUSTMENT
        return None

    with patch.object(hub, "resolve_game_and_power", return_value=("7", "GERMANY")), \
         patch.object(hub, "fetch_user_games", return_value=[]), \
         patch.object(hub, "status_text", return_value="HDR"), \
         patch.object(hub, "api_get", side_effect=get):
        asyncio.run(hub.show_hub(send, "5", "7"))
    assert sent == ["HDR\nYou may build 2 units (free home centres: BER, KIE, MUN)."]
