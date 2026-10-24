"""BS3/BS6: a finished game reads as finished; phase codes read as words."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.telegram_bot import games as bot_games
from server.telegram_bot import hub as bot_hub
from server.telegram_bot import orders as bot_orders
from server.telegram_bot.utils import game_end_line, phase_label, phase_text

pytestmark = pytest.mark.unit

WON = {"phase": "F1903M", "status": "COMPLETED", "winners": ["FRANCE"]}
DRAW = {"phase": "F1903M", "status": "COMPLETED", "winners": ["FRANCE", "ITALY"]}
LIVE = {"phase": "F1903M", "status": "ACTIVE", "winners": None}


def test_phase_labels() -> None:
    assert phase_label("F1903M") == "Fall 1903 movement"
    assert phase_label("S1904R") == "Spring 1904 retreats"
    assert phase_label("W1901A") == "Winter 1901 builds"
    assert phase_label("???") == "???"
    assert phase_text("F1903M") == "Fall 1903 movement (F1903M)"
    assert phase_text("???") == "???"


def test_game_end_line() -> None:
    assert game_end_line(WON) == "Game ended: won by France"
    assert game_end_line(DRAW) == "Game ended in a draw shared by France, Italy"
    assert game_end_line({"status": "COMPLETED", "winners": []}) == "Game ended with no winner"
    assert game_end_line(LIVE) is None


def _status(view: dict) -> str:
    def get(path: str, **_kw):
        if path.endswith("/state"):
            return view
        raise AssertionError(f"a finished game must not ask for {path}")

    with patch.object(bot_games, "api_get", side_effect=get):
        return bot_games.status_text("1", "FRANCE", "5")


def test_status_of_a_finished_game_leads_with_the_result() -> None:
    assert _status(WON) == (
        "📊 *Game 1 Status*\n\n🏁 *Game ended: won by France*\n🎯 *You are:* FRANCE\n"
        "📅 *Final turn:* Fall 1903 movement (F1903M)\n"
    )


def test_status_of_a_live_game_uses_the_label() -> None:
    def get(path: str, **_kw):
        if path.endswith("/state"):
            return LIVE
        return {}

    with patch.object(bot_games, "api_get", side_effect=get):
        text = bot_games.status_text("1", "FRANCE", "5")
    assert "📅 *Turn:* Fall 1903 movement (F1903M)\n" in text
    assert "Phase Code" not in text and "Game ended" not in text


def test_ready_on_a_finished_game_refuses() -> None:
    with patch.object(bot_games, "api_get", return_value=WON), \
         patch.object(bot_games, "api_post") as post:
        assert bot_games.set_wait_flag("1", "FRANCE", "5", False) == "Game 1 has ended."
    post.assert_not_called()


def test_order_walk_of_a_finished_game_refuses() -> None:
    sent: list[str] = []

    async def send(text: str, **_kw) -> None:
        sent.append(text)

    def get(path: str, **_kw):
        return WON if path.endswith("/state") else {"phase_type": "MOVEMENT", "units": []}

    context = Mock()
    context.user_data = {}
    with patch.object(bot_orders, "resolve_game_and_power", return_value=("1", "FRANCE")), \
         patch.object(bot_orders, "api_get", side_effect=get):
        asyncio.run(bot_orders.start_order_walk(send, context, "5", "1"))
    assert sent == ["Game 1 has ended. Game ended: won by France."]


def test_deadline_view_of_a_finished_game_offers_no_proposals() -> None:
    send = AsyncMock()
    with patch.object(bot_hub, "api_get", return_value=WON):
        asyncio.run(bot_hub._show_deadline(send, "1", "FRANCE"))
    assert send.call_args[0] == ("Game 1 has ended.",)
    assert send.call_args[1]["parse_mode"] is None


@pytest.mark.parametrize(("legal", "expected"), [
    ({"phase_type": "MOVEMENT", "units": []}, "France has nothing to order this phase."),
    ({"phase_type": "RETREAT", "units": [{}, {}]}, "France owes retreats for 2 units: /orderall 1."),
    ({"phase_type": "ADJUSTMENT", "units": [{}], "adjustment": {"action": "build", "slots": 1}},
     "France owes 1 build: /orderall 1."),
    ({"phase_type": "ADJUSTMENT", "units": [{}], "adjustment": {"action": "disband", "slots": 2}},
     "France owes 2 disbands: /orderall 1."),
    ({"phase_type": "ADJUSTMENT", "units": [{}], "adjustment": {"action": "none", "slots": 0}},
     "France has nothing to build or disband."),
])
def test_process_turn_says_what_the_caller_owes(legal: dict, expected: str) -> None:
    with patch.object(bot_orders, "resolve_game_and_power", return_value=("1", "FRANCE")), \
         patch.object(bot_orders, "api_get", return_value=legal):
        assert bot_orders._owed_text("1", "5") == expected


def test_walk_header_and_stale_message_use_labels() -> None:
    sent: list[str] = []

    async def send(text: str, reply_markup=None) -> None:
        sent.append(text)

    context = Mock()
    context.user_data = {bot_orders._WALK: {"1": {
        "power": "ENGLAND", "phase": "S1904M", "adjust": False, "steps": ["A LON"], "chosen": {},
    }}}
    asyncio.run(bot_orders._show_walk_summary(send, context, "1"))
    assert "(ENGLAND, Spring 1904 movement)" in sent[0]
