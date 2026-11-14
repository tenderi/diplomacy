"""Z2: /orderall -- order every unit in turn, then submit them together.

Driven through the real callback router (``app.button_callback``) the way
Telegram delivers button presses, so the ``ord|`` interception that makes a
pick *record* during a walk (instead of submitting at once, as /selectunit
does) is covered too. Every HTTP call is mocked.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.telegram_bot import app as bot_app
from server.telegram_bot.orders import orderall

pytestmark = pytest.mark.unit

GAMES = {"games": [{"game_id": "1", "power": "GERMANY"}]}
MOVEMENT = {
    "phase": "S1901M",
    "phase_type": "MOVEMENT",
    "units": [
        {"kind": "A", "location": "BER"},
        {"kind": "F", "location": "KIE"},
        {"kind": "A", "location": "MUN"},
    ],
    "orders_by_unit": {
        "A BER": ["A BER H", "A BER - KIE", "A BER S A MUN - KIE"],
        "F KIE": ["F KIE H", "F KIE - DEN"],
        "A MUN": ["A MUN H", "A MUN - RUH"],
    },
    "orders": [],
}
ADJUSTMENT = {
    "phase": "W1901A",
    "phase_type": "ADJUSTMENT",
    "adjustment": {"delta": 2, "action": "build", "slots": 2},
    "orders": ["BUILD A BER", "BUILD F KIE", "BUILD A MUN", "WAIVE"],
    "orders_by_unit": {},
    "units": [],
}


class Chat:
    """One player's session: a shared ``user_data`` and the last screen shown."""

    def __init__(self) -> None:
        self.context = Mock()
        self.context.user_data = {}
        self.context.args = []
        self.text = ""
        self.buttons: list[tuple[str, str]] = []

    def _capture(self, text: str, reply_markup=None, **_kw) -> None:
        self.text = text
        self.buttons = [
            (b.text, b.callback_data) for row in (reply_markup.inline_keyboard if reply_markup else []) for b in row
        ]

    def command(self, args: list[str]) -> None:
        update = Mock()
        update.effective_user = Mock(id=555)
        update.message = Mock()
        update.message.reply_text = AsyncMock(side_effect=self._capture)
        self.context.args = args
        asyncio.run(orderall(update, self.context))

    def press(self, label_part: str) -> None:
        data = next(d for text, d in self.buttons if label_part in text)
        query = Mock()
        query.data = data
        query.answer = AsyncMock()
        query.from_user = Mock(id=555)
        query.edit_message_text = AsyncMock(side_effect=self._capture)
        update = Mock()
        update.callback_query = query
        asyncio.run(bot_app.button_callback(update, self.context))


def _board(phase: str, legal: dict, pending: list[str] | None = None):
    """An ``api_get`` stand-in: the game's phase, the power's legal orders and
    its stored pending orders (``/games/{id}/orders/{power}``)."""
    def get(path: str, **_kw) -> dict:
        if path.endswith("/state"):
            return {"phase": phase}
        if "/orders/" in path:
            return {"orders": list(pending or [])}
        return legal
    return get


def _delivered(orders_response: dict) -> SimpleNamespace:
    return SimpleNamespace(status="delivered", response=orders_response, error=None)


@pytest.fixture
def api():
    with patch("server.telegram_bot.game_context.api_get", return_value=GAMES), \
         patch("server.telegram_bot.orders.api_get") as get, \
         patch("server.telegram_bot.orders.api_post_reliable") as post:
        get.side_effect = lambda path, **_kw: {"phase": "S1901M"} if path.endswith("/state") else MOVEMENT
        post.return_value = _delivered({"results": [], "auto_processed": 0})
        yield SimpleNamespace(get=get, post=post)


def test_walks_every_unit_then_submits_them_in_one_request(api) -> None:
    chat = Chat()
    chat.command([])
    assert "Unit 1/3" in chat.text and "A BER" in chat.text
    assert not any("Back" in t for t, _ in chat.buttons)  # nothing to go back to yet

    chat.press("- KIE")          # A BER - KIE: recorded, not submitted
    api.post.assert_not_called()
    assert "Unit 2/3" in chat.text and "`A BER - KIE`" in chat.text

    chat.press("Skip")           # F KIE skipped...
    assert "Unit 3/3" in chat.text
    chat.press("Back")           # ...then reconsidered
    assert "Unit 2/3" in chat.text
    chat.press("- DEN")
    chat.press("- RUH")

    assert "Your orders for game 1" in chat.text
    chat.press("Submit 3 orders")
    endpoint, body = api.post.call_args[0][:2]
    assert endpoint == "/games/set_orders"
    assert body["orders"] == ["A BER - KIE", "F KIE - DEN", "A MUN - RUH"]
    assert body["merge"] is True
    assert chat.context.user_data["order_walk"] == {}  # the walk is over


def test_a_support_picked_from_the_sub_menu_is_recorded_too(api) -> None:
    chat = Chat()
    chat.command(["1"])
    chat.press("Support options")
    chat.press("MUN")            # the supported unit
    chat.press("KIE")            # its destination
    assert "Unit 2/3" in chat.text and "`A BER S A MUN - KIE`" in chat.text
    api.post.assert_not_called()


def test_a_skipped_unit_is_left_out_and_explained(api) -> None:
    chat = Chat()
    chat.command([])
    chat.press("Skip")
    chat.press("- DEN")
    chat.press("- RUH")
    assert "A BER: _skipped_" in chat.text and "keeps any order you sent earlier" in chat.text
    chat.press("Submit 2 orders")
    assert api.post.call_args[0][1]["orders"] == ["F KIE - DEN", "A MUN - RUH"]


def test_nothing_is_sent_if_the_turn_moved_on_meanwhile(api) -> None:
    chat = Chat()
    chat.command([])
    for label in ("- KIE", "- DEN", "- RUH"):
        chat.press(label)
    api.get.side_effect = lambda path, **_kw: {"phase": "F1901M"} if path.endswith("/state") else MOVEMENT
    chat.press("Submit 3 orders")
    api.post.assert_not_called()
    assert chat.text == (
        "⏰ Game 1 moved on to Fall 1901 movement (F1901M) while you were choosing, "
        "so these orders no longer apply. Start again with /orderall 1."
    )


def test_cancel_ends_the_walk_without_sending(api) -> None:
    chat = Chat()
    chat.command([])
    chat.press("- KIE")
    chat.press("Cancel")
    api.post.assert_not_called()
    assert "Nothing was submitted" in chat.text
    assert "1" not in chat.context.user_data["order_walk"]


def test_adjustments_walk_the_build_slots(api) -> None:
    api.get.side_effect = _board("W1901A", ADJUSTMENT)
    chat = Chat()
    chat.command([])
    assert "Build 1 of 2" in chat.text
    chat.press("BER")
    assert "Build 2 of 2" in chat.text
    assert not any("BER" in t for t, _ in chat.buttons)  # already chosen
    chat.press("Waive")
    chat.press("Submit 2 orders")
    assert api.post.call_args[0][1]["orders"] == ["BUILD A BER", "WAIVE"]


def test_a_build_takes_its_province_for_the_later_slots(api) -> None:
    """Only the exact string chosen was hidden, so after BUILD A KIE the walk
    still offered BUILD F KIE -- both were submitted and the second was VOID,
    losing the slot."""
    two_at_kie = {**ADJUSTMENT, "orders": ["BUILD A KIE", "BUILD F KIE", "BUILD A MUN", "WAIVE"]}
    api.get.side_effect = _board("W1901A", two_at_kie)
    chat = Chat()
    chat.command([])
    chat.press("Build army KIE")
    assert "Build 2 of 2" in chat.text
    assert not any("KIE" in t for t, _ in chat.buttons)
    assert any("Build army MUN" in t for t, _ in chat.buttons)


RUSSIA_BUILDS = {
    "phase": "W1901A",
    "phase_type": "ADJUSTMENT",
    "adjustment": {"delta": 2, "action": "build", "slots": 2},
    "orders": ["BUILD A MOS", "BUILD A SEV", "BUILD F SEV", "BUILD A STP", "BUILD F STP/NC", "WAIVE"],
    "orders_by_unit": {},
    "units": [],
}


def test_a_walk_after_a_typed_build_walks_only_the_free_slot(api) -> None:
    """DK1: Russia (2 builds) typed ``/order BUILD A MOS``, then opened the
    Builds walk. It said "Build 1 of 2", offered Moscow again, and its two new
    picks were submitted as a merge past the count, so the server dropped
    ``BUILD A MOS`` ("replaced BUILD A MOS (you may build 2)")."""
    api.get.side_effect = _board("W1901A", RUSSIA_BUILDS, pending=["BUILD A MOS"])
    chat = Chat()
    chat.command([])
    assert "Build 2 of 2" in chat.text and "Build 1 of 2" not in chat.text
    assert "• `BUILD A MOS` (ordered earlier)" in chat.text
    assert not any("MOS" in t for t, _ in chat.buttons)  # Moscow is taken
    chat.press("Build army SEV")
    assert "• `BUILD A MOS` (ordered earlier, kept)\n• `BUILD A SEV`" in chat.text
    chat.press("Submit 1 order")
    body = api.post.call_args[0][1]
    assert body["orders"] == ["BUILD A SEV"]
    assert body["merge"] is True  # added beside BUILD A MOS: 2 builds, nothing replaced


def test_a_walk_with_every_build_ordered_offers_to_change_them(api) -> None:
    api.get.side_effect = _board("W1901A", RUSSIA_BUILDS, pending=["BUILD A MOS", "BUILD F STP/NC"])
    chat = Chat()
    chat.command([])
    assert chat.text == (
        "✅ GERMANY has already ordered all 2 builds in game 1:\n• `BUILD A MOS`\n• `BUILD F STP/NC`\n\n"
        "To change them, choose them all again: the new set replaces these."
    )
    api.post.assert_not_called()
    chat.press("Change them")
    assert "Build 1 of 2" in chat.text
    assert any("Build army MOS" in t for t, _ in chat.buttons)  # every site is free again
    chat.press("Build army SEV")
    chat.press("Waive")
    assert "Submitting replaces the builds or disbands you ordered earlier." in chat.text
    chat.press("Submit 2 orders")
    body = api.post.call_args[0][1]
    assert body["orders"] == ["BUILD A SEV", "WAIVE"]
    assert body["merge"] is False  # the new set replaces the stored one


def test_a_disband_walk_keeps_the_disband_already_ordered(api) -> None:
    disbands = {
        "phase": "W1901A",
        "phase_type": "ADJUSTMENT",
        "adjustment": {"delta": -2, "action": "disband", "slots": 2},
        "orders": ["D A BER", "D F KIE", "D A MUN"],
        "orders_by_unit": {},
        "units": [],
    }
    api.get.side_effect = _board("W1901A", disbands, pending=["D A BER"])
    chat = Chat()
    chat.command([])
    assert "Disband 2 of 2" in chat.text
    assert not any("BER" in t for t, _ in chat.buttons)
    chat.press("MUN")
    chat.press("Submit 1 order")
    assert api.post.call_args[0][1]["orders"] == ["D A MUN"]
    assert api.post.call_args[0][1]["merge"] is True


def test_a_skipped_slot_in_a_change_walk_is_said_to_drop_its_earlier_order(api) -> None:
    """In a "Change them" walk the submit replaces the stored set, so a
    skipped slot keeps nothing; the summary must not imply otherwise."""
    disbands = {
        "phase": "W1901A",
        "phase_type": "ADJUSTMENT",
        "adjustment": {"delta": -2, "action": "disband", "slots": 2},
        "orders": ["D A BER", "D F KIE", "D A MUN"],
        "orders_by_unit": {},
        "units": [],
    }
    api.get.side_effect = _board("W1901A", disbands, pending=["D A BER", "D F KIE"])
    chat = Chat()
    chat.command([])
    chat.press("Change them")
    chat.press("MUN")
    chat.press("Skip")
    assert chat.text.endswith(
        "Skipped: 1. If you order too few disbands, the server chooses the rest by the civil-disorder rule "
        "(farthest from home first).\n\n"
        "Submitting replaces the builds or disbands you ordered earlier, and a skipped slot does not keep "
        "its earlier order."
    )
    assert "keeps any order you sent earlier" not in chat.text
    chat.press("Submit 1 order")
    assert api.post.call_args[0][1]["orders"] == ["D A MUN"]
    assert api.post.call_args[0][1]["merge"] is False


def test_selectunit_still_sends_one_order_at_once(api) -> None:
    """The single-order flow is unchanged: no walk, so ord| submits immediately."""
    chat = Chat()
    chat.buttons = [("go", "selunit|1|A MUN")]
    chat.press("go")
    chat.press("- RUH")
    assert api.post.call_args[0][1]["orders"] == ["A MUN - RUH"]


def test_a_button_left_on_an_older_unit_menu_submits_nothing(api) -> None:
    """Menus are separate messages, so the first unit's buttons stay tappable after
    the second unit's menu opens. Tapping one must not submit the order at the
    same position in the newer menu (A MUN - RUH would have become F KIE - DEN)."""
    chat = Chat()
    chat.buttons = [("go", "selunit|1|A MUN")]
    chat.press("go")
    mun_menu = chat.buttons
    chat.buttons = [("go", "selunit|1|F KIE")]
    chat.press("go")
    chat.buttons = mun_menu
    chat.press("- RUH")
    api.post.assert_not_called()
    assert "expired" in chat.text
