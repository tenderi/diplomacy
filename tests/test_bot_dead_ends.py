"""Track DB: the game menu and order walk for a power with nothing to order outside winter."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from server.telegram_bot import hub
from tests.test_order_all_flow import Chat, api  # noqa: F401  (api is a fixture)

pytestmark = pytest.mark.unit

NOTHING = "You have nothing to order this phase; wait for the other powers."


def _buttons(legal: dict[str, Any]) -> list[str]:
    markup: Any = hub._hub_keyboard("7", "FRANCE", {"status": "ACTIVE"}, None, False, legal)
    return [b.text for row in markup.inline_keyboard for b in row]


@pytest.mark.parametrize("phase_type", ["MOVEMENT", "RETREAT"])
def test_hub_has_no_order_buttons_when_the_power_has_no_units_to_order(phase_type: str) -> None:
    labels = _buttons({"phase_type": phase_type, "units": []})
    assert "📝 Order all units" not in labels and "🎯 One unit" not in labels
    assert "📋 My orders" in labels and "🗺 Map" in labels
    with_unit = {
        "phase_type": phase_type, "units": [{"kind": "A", "location": "PAR"}],
        "orders_by_unit": {"A PAR": ["A PAR H", "A PAR R BUR", "D A PAR"]},
    }
    assert "📝 Order all units" in _buttons(with_unit)


@pytest.mark.parametrize("phase_type", ["MOVEMENT", "RETREAT"])
def test_hub_text_says_nothing_to_order(phase_type: str) -> None:
    sent: list[str] = []

    async def send(text: str, reply_markup=None, **_kw) -> None:
        sent.append(text)

    def get(path: str, **_kw: Any) -> Any:
        if path.endswith("/state"):
            return {"phase_type": phase_type, "status": "ACTIVE"}
        if "legal_orders" in path:
            return {"phase_type": phase_type, "units": []}
        return None

    with patch.object(hub, "resolve_game_and_power", return_value=("7", "GERMANY")), \
         patch.object(hub, "fetch_user_games", return_value=[]), \
         patch.object(hub, "status_text", return_value="HDR"), \
         patch.object(hub, "api_get", side_effect=get):
        asyncio.run(hub.show_hub(send, "5", "7"))
    assert sent == [f"HDR\n{NOTHING}"]


@pytest.mark.parametrize("phase_type", ["MOVEMENT", "RETREAT"])
def test_walk_says_nothing_to_order_for_a_power_without_units(api, phase_type: str) -> None:  # noqa: F811
    api.get.side_effect = lambda path, **_kw: {"phase": "S1901R"} if path.endswith("/state") else {
        "phase": "S1901R", "phase_type": phase_type, "units": [], "orders": [], "orders_by_unit": {},
    }
    chat = Chat()
    chat.command([])
    assert "has no units to order" in chat.text and not chat.buttons
