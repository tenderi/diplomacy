"""A finished game takes no messages: the bot's replies for the API's 409."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from server.telegram_bot import hub
from server.telegram_bot import outbox as ob
from server.telegram_bot.api_client import DeliveryResult
from server.telegram_bot.messages import send_diplomatic_message
from server.telegram_bot.notifications import format_delivery_report

pytestmark = pytest.mark.unit

ENDED = "Game 7 has ended; messages can no longer be sent."


def _replayed(tmp_path, endpoint: str, error: str) -> DeliveryResult:
    box = ob.Outbox(tmp_path / "o.sqlite3")
    entry = box.enqueue(1, endpoint, {"text": "hi"}, "message to FRANCE in game 7: hi")
    box.close()
    return DeliveryResult("rejected", entry, error=error)


def _rejected(error: str) -> DeliveryResult:
    return DeliveryResult("rejected", None, error=error)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "recipient,anonymous,kind",
    [("FRANCE", False, "message"), (None, False, "broadcast"), (None, True, "rumour")],
)
def test_sending_to_a_finished_game_says_it_has_ended(recipient, anonymous, kind) -> None:
    with patch("server.telegram_bot.messages.api_post_reliable", return_value=_rejected(ENDED)):
        reply = send_diplomatic_message("1", 1, "7", recipient, "hi", anonymous=anonymous)
    assert reply == f"Game 7 has ended. Messages can no longer be sent, so your {kind} was not sent."


def test_another_refusal_keeps_the_api_text() -> None:
    with patch("server.telegram_bot.messages.api_post_reliable", return_value=_rejected("Sender not in game")):
        assert send_diplomatic_message("1", 1, "7", None, "hi") == "Broadcast error: Sender not in game"


def test_a_queued_message_replayed_into_a_finished_game_is_reported(tmp_path) -> None:
    report = format_delivery_report(_replayed(tmp_path, "/games/7/message", ENDED))
    assert report.splitlines()[1:] == ["The game has ended, so your message was not sent."]
    assert report.splitlines()[0].endswith("message to FRANCE in game 7: hi")


def test_the_messages_screen_of_a_finished_game_offers_no_composer() -> None:
    sent = AsyncMock()

    def fake_get(path: str, **_kw):
        if path.endswith("/state"):
            return {"status": "COMPLETED", "winners": ["FRANCE"]}
        return []

    with patch.object(hub, "api_get", side_effect=fake_get), \
         patch.object(hub, "recent_messages_text", return_value="history"):
        asyncio.run(hub._show_messages(sent, "1", "7", "FRANCE"))
    (text,), kwargs = sent.call_args
    assert text == "history\n\nGame 7 has ended. Messages can no longer be sent."
    data = [b.callback_data for row in kwargs["reply_markup"].inline_keyboard for b in row]
    assert not any("|msg|" in d for d in data)
