"""DK6: bot text nits."""
from __future__ import annotations

from typing import Any

from server.telegram_bot import hub, orders as bot_orders


def test_via_move_button_says_by_convoy_and_keeps_the_order_text() -> None:
    assert bot_orders._order_label("A YOR - EDI") == "➡️ A YOR - EDI"
    assert bot_orders._order_label("A YOR - EDI VIA") == "➡️ A YOR - EDI (by convoy)"
    assert bot_orders._order_label("A LON - BEL VIA CONVOY") == "➡️ A LON - BEL (by convoy)"


def test_hub_deadline_button_shows_a_pending_vote() -> None:
    def labels(pending: bool) -> list[str]:
        markup: Any = hub._hub_keyboard("7", "FRANCE", {"status": "ACTIVE"}, None, False, None, pending)
        return [b.text for row in markup.inline_keyboard for b in row]

    assert "⏰ Deadline" in labels(False)
    assert "⏰ Deadline (vote pending)" in labels(True)
