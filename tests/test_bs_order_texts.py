"""BS1/BS5: what a skipped unit does per phase, and what is still unordered."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests

from server.telegram_bot import orders as bot_orders

pytestmark = pytest.mark.unit


def _api(legal: dict, pending: list[str]):
    def get(path: str, **_kw):
        return {"orders": pending} if "/orders/" in path else legal
    return patch.object(bot_orders, "api_get", side_effect=get)


MOVE = {"phase_type": "MOVEMENT", "units": [{"kind": "F", "location": "NWG"}, {"kind": "A", "location": "PAR"}]}


def test_movement_lists_the_units_with_no_order() -> None:
    with _api(MOVE, ["A PAR - BUR"]):
        assert bot_orders.unordered_note("1", "ENGLAND", "5") == "No order yet (holds): F NWG"


def test_retreat_says_disbanded() -> None:
    legal = {"phase_type": "RETREAT", "units": [{"kind": "A", "location": "RUM"}]}
    with _api(legal, []):
        assert bot_orders.unordered_note("1", "RUSSIA", "5") == "No order yet (disbanded): A RUM"


def test_nothing_missing_adds_no_line() -> None:
    with _api(MOVE, ["F NWG H", "A PAR H"]):
        assert bot_orders.unordered_note("1", "ENGLAND", "5") == ""


def test_adjustment_counts() -> None:
    build = {"phase_type": "ADJUSTMENT", "adjustment": {"action": "build", "slots": 2}}
    with _api(build, ["BUILD A PAR"]):
        assert bot_orders.unordered_note("1", "FRANCE", "5") == (
            "1 build not ordered yet: unordered builds are waived."
        )
    disband = {"phase_type": "ADJUSTMENT", "adjustment": {"action": "disband", "slots": 2}}
    with _api(disband, []):
        assert bot_orders.unordered_note("1", "FRANCE", "5") == (
            "2 disbands not ordered yet: if you send none, the server chooses them by the "
            "civil-disorder rule (farthest from home first)."
        )


def test_an_api_failure_omits_the_line() -> None:
    with patch.object(bot_orders, "api_get", side_effect=requests.ConnectionError("down")):
        assert bot_orders.unordered_note("1", "ENGLAND", "5") == ""


def test_confirmation_is_titled_orders_received() -> None:
    results = [{"success": True, "order": "A PAR - BUR"}]
    with _api(MOVE, ["A PAR - BUR"]):
        assert bot_orders._orders_received(results, "1", "ENGLAND", "5") == (
            "Orders received:\n✅ A PAR - BUR\nNo order yet (holds): F NWG"
        )


def _summary(phase: str, adjust: bool) -> str:
    sent: list[str] = []

    async def send(text: str, reply_markup=None) -> None:
        sent.append(text)

    context = Mock()
    context.user_data = {bot_orders._WALK: {"1": {
        "power": "ENGLAND", "phase": phase, "adjust": adjust, "steps": ["A PAR"], "chosen": {},
    }}}
    asyncio.run(bot_orders._show_walk_summary(send, context, "1"))
    return sent[0]


def test_walk_summary_notes_per_phase() -> None:
    assert _summary("S1901M", False).endswith(
        "Skipped: 1. A skipped unit keeps any order you sent earlier; with none, it holds."
    )
    assert _summary("F1901R", False).endswith(
        "Skipped: 1. A skipped unit keeps any order you sent earlier; with none, it is disbanded."
    )
    assert _summary("W1901A", True).endswith(
        "Skipped: 1. A skipped build is waived; if you owe disbands and order too few, "
        "the server chooses the rest by the civil-disorder rule (farthest from home first)."
    )
