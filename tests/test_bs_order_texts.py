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
    legal = {
        "phase_type": "RETREAT",
        "units": [{"kind": "A", "location": "RUM"}],
        "orders_by_unit": {"A RUM": ["A RUM R BUL", "D A RUM"]},
    }
    with _api(legal, []):
        assert bot_orders.unordered_note("1", "RUSSIA", "5") == "No order yet (disbanded if none comes): A RUM"


def test_nothing_missing_adds_no_line() -> None:
    with _api(MOVE, ["F NWG H", "A PAR H"]):
        assert bot_orders.unordered_note("1", "ENGLAND", "5") == ""


def test_adjustment_counts() -> None:
    build = {"phase_type": "ADJUSTMENT", "adjustment": {"action": "build", "slots": 2}}
    with _api(build, ["BUILD A PAR"]):
        assert bot_orders.unordered_note("1", "FRANCE", "5") == (
            "1 build not ordered yet: auto-processing waits until every build is ordered or waived (/order WAIVE); at a deadline the unordered ones are waived."
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


def _summary(phase: str, adjust: bool, action: str | None = None) -> str:
    sent: list[str] = []

    async def send(text: str, reply_markup=None) -> None:
        sent.append(text)

    context = Mock()
    context.user_data = {bot_orders._WALK: {"1": {
        "power": "ENGLAND", "phase": phase, "adjust": adjust, "action": action, "steps": ["A PAR"], "chosen": {},
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
    assert _summary("W1901A", True, "build").endswith("Skipped: 1. A skipped build is waived.")
    assert _summary("W1901A", True, "disband").endswith(
        "Skipped: 1. If you order too few disbands, the server chooses the rest by the "
        "civil-disorder rule (farthest from home first)."
    )


# -- #460: the order helper's notes -------------------------------------------------

CONVOY = "A LON - NWY needs a convoy: it can succeed only if France's F NTH convoys it"


def test_results_show_the_helper_notes_once() -> None:
    results = [
        {
            "success": True,
            "order": "A LON - NWY",
            "stored": "A LON - NWY VIA",
            "note": CONVOY,
            "notes": [{"kind": "warning", "code": "needs_convoy", "text": CONVOY}],
        },
        {
            "success": False,
            "order": "F EDI - PAR",
            "error": "F EDI cannot reach PAR",
            "notes": [{"kind": "impossible", "code": "fleet_inland", "text": "a fleet cannot go inland"}],
        },
        {
            "success": True,
            "order": "F NTH S A LON - NWY",
            "notes": [{"kind": "warning", "code": "support_mismatch", "text": "but A LON is ordered to hold"}],
        },
    ]
    assert bot_orders.format_order_results(results) == (
        f"✅ A LON - NWY VIA CONVOY {CONVOY}\n"
        "❌ F EDI - PAR\n   Error: F EDI cannot reach PAR\n   💡 A fleet cannot go inland\n"
        "✅ F NTH S A LON - NWY\n   💡 But A LON is ordered to hold"
    )


def _walk(**extra) -> dict:
    return {
        "power": "ENGLAND", "phase": "S1901M", "adjust": False, "action": None,
        "steps": ["A LON", "F NTH"], "chosen": {"A LON": "A LON - NWY"}, "user_id": "5", **extra,
    }


def test_the_walk_summary_asks_for_notes_on_the_picks_before_submitting() -> None:
    sent: list[str] = []

    async def send(text: str, reply_markup=None) -> None:
        sent.append(text)

    context = Mock()
    context.user_data = {bot_orders._WALK: {"1": _walk()}}
    answer = {
        "orders": [{"order": "A LON - NWY", "ok": True, "notes": [{"kind": "warning", "code": "needs_convoy", "text": CONVOY}]}],
        "notes": [{"kind": "warning", "code": "unordered", "text": "F NTH has no order, so it will hold"}],
    }
    with patch.object(bot_orders, "api_post", return_value=answer) as post:
        asyncio.run(bot_orders._show_walk_summary(send, context, "1"))
    post.assert_called_once_with(
        "/games/1/orders/ENGLAND/notes", {"orders": ["A LON - NWY"], "merge": True, "telegram_id": "5"}
    )
    assert sent[0].endswith(
        "\n\n💡 *Before you submit:*\n• " + CONVOY + "\n• F NTH has no order, so it will hold"
    )


def test_a_replace_walk_asks_without_merging_and_a_failure_shows_nothing() -> None:
    with patch.object(bot_orders, "api_post", return_value={"orders": [], "notes": []}) as post:
        assert bot_orders.walk_helper_notes("1", _walk(replace=True)) == []
    assert post.call_args.args[1]["merge"] is False
    with patch.object(bot_orders, "api_post", side_effect=requests.ConnectionError("down")):
        assert bot_orders.walk_helper_notes("1", _walk()) == []
    with patch.object(bot_orders, "api_post") as post:
        assert bot_orders.walk_helper_notes("1", _walk(chosen={})) == []
    post.assert_not_called()
