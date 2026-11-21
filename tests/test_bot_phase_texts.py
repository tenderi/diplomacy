"""Track DU: bot texts that must match the phase (DU1) and the game's end (DU2)."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.telegram_bot import hub
from server.telegram_bot.orders import processturn

pytestmark = pytest.mark.unit

FATES = [
    ("S1901M", "their units will hold"),
    ("F1901R", "their dislodged units will be disbanded"),
    ("W1901A", "their builds are waived and any disbands are chosen for them"),
]


@pytest.mark.parametrize("phase,fate", FATES)
def test_hub_process_warning_is_phase_aware(phase: str, fate: str) -> None:
    sent: list[str] = []

    async def send(text: str, **_kw: Any) -> None:
        sent.append(text)

    with patch.object(hub, "api_get", return_value={"missing": ["ITALY"], "phase": phase}):
        asyncio.run(hub._process_turn(send, "5", "7"))
    assert sent == [f"⚠️ Still waiting on: ITALY. If you process now, {fate}."]


@pytest.mark.parametrize("phase,fate", FATES)
def test_processturn_warning_is_phase_aware(phase: str, fate: str) -> None:
    update, context = Mock(), Mock()
    context.args = ["1"]
    update.effective_user = Mock(id=12345)
    update.message.reply_text = AsyncMock()
    status = {"missing": ["GERMANY"], "phase": phase}
    with patch("server.telegram_bot.orders.resolve_game_and_power", return_value=("1", "FRANCE")), \
         patch("server.telegram_bot.orders.api_get", return_value=status):
        asyncio.run(processturn(update, context))
    assert f"Processing now: {fate}. Continue?" in update.message.reply_text.call_args[0][0]


@pytest.mark.parametrize("phase_type", ["MOVEMENT", "RETREAT", "ADJUSTMENT"])
@pytest.mark.parametrize("how", ["draw", "solo"])
def test_hub_of_a_finished_game_does_not_say_wait(how: str, phase_type: str) -> None:
    sent: list[tuple[str, Any]] = []

    async def send(text: str, reply_markup: Any = None, **_kw: Any) -> None:
        sent.append((text, reply_markup))

    def get(path: str, **_kw: Any) -> Any:
        if path.endswith("/state"):
            return {"phase_type": phase_type, "status": "COMPLETED", "result": how}
        if "legal_orders" in path:
            return {"phase_type": phase_type, "units": [], "adjustment": {"action": "none", "slots": 0}}
        return None

    with patch.object(hub, "resolve_game_and_power", return_value=("7", "GERMANY")), \
         patch.object(hub, "fetch_user_games", return_value=[]), \
         patch.object(hub, "status_text", return_value="HDR"), \
         patch.object(hub, "api_get", side_effect=get):
        asyncio.run(hub.show_hub(send, "5", "7"))
    assert sent[0][0] == "HDR"
    labels = [b.text for row in sent[0][1].inline_keyboard for b in row]
    assert not any("order" in t.lower().replace("order history", "") or "process" in t.lower() for t in labels)
