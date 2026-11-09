"""CF2: the adjustment walk's Back keeps the step's own build pickable, and
disband buttons carry their emoji."""

from __future__ import annotations

from server.telegram_bot.orders import _order_label, _order_verb
from tests.test_order_all_flow import ADJUSTMENT, Chat, api  # noqa: F401  (api is a fixture)


def test_back_keeps_the_current_steps_own_build_pickable(api) -> None:  # noqa: F811
    """Back left the step's earlier choice in ``taken``, so after BUILD F STP/SC
    every STP option vanished and it could not be changed to STP/NC."""
    three = {
        **ADJUSTMENT,
        "adjustment": {"delta": 3, "action": "build", "slots": 3},
        "orders": ["BUILD F STP/NC", "BUILD F STP/SC", "BUILD A SEV", "WAIVE"],
    }
    api.get.side_effect = lambda path, **_kw: {"phase": "W1901A"} if path.endswith("/state") else three
    chat = Chat()
    chat.command([])
    chat.press("Build fleet STP/SC")
    assert not any("STP" in t for t, _ in chat.buttons)  # later step: site taken
    chat.press("Back")
    assert "Build 1 of 3" in chat.text
    assert any("Build fleet STP/NC" in t for t, _ in chat.buttons)
    chat.press("Build fleet STP/NC")
    chat.press("Build army SEV")
    chat.press("Waive")
    chat.press("Submit 3 orders")
    assert api.post.call_args[0][1]["orders"] == ["BUILD F STP/NC", "BUILD A SEV", "WAIVE"]


def test_disband_buttons_get_their_emoji() -> None:
    assert _order_verb("D F STP/SC") == "D"
    assert _order_label("D F STP/SC") == "✂️ Disband fleet STP/SC"
    assert _order_label("D A MUN") == "✂️ Disband army MUN"
    assert _order_label("A MUN - RUH") == "➡️ A MUN - RUH"
    assert _order_label("BUILD A BER") == "🏗️ Build army BER"
