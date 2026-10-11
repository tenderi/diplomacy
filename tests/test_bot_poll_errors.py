"""BF5 review follow-ups: which Telegram errors retry an outbox row, a malformed row,
and the quiet log line for a polling network error."""
from __future__ import annotations

import asyncio
from unittest.mock import Mock, patch

import pytest
from telegram.error import Conflict, InvalidToken, NetworkError

from server.telegram_bot import app as bot_app
from server.telegram_bot import notifications

pytestmark = pytest.mark.unit


def _poll(items: list[dict], send: object) -> tuple[tuple[int, int], Mock]:
    with patch.object(notifications, "api_get", return_value={"items": items}), \
         patch.object(notifications, "api_post") as ack, \
         patch.object(notifications, "_send_outbox_item", new=send):
        return asyncio.run(notifications.deliver_pending_notifications(Mock())), ack


@pytest.mark.parametrize("error", [InvalidToken("rotated"), Conflict("two pollers")])
def test_a_telegram_error_about_the_bot_retries_instead_of_failing_the_row(error: Exception) -> None:
    items = [{"id": 1, "telegram_id": "10", "message": "a"}, {"id": 2, "telegram_id": "11", "message": "b"}]

    async def send(_bot: object, chat_id: int, item: dict) -> None:
        raise error

    counts, ack = _poll(items, send)
    assert counts == (0, 0)
    ack.assert_not_called()  # nothing acked: both rows come back next poll


def test_a_row_with_a_malformed_chat_id_is_acked_failed_not_wedging_the_batch(caplog: pytest.LogCaptureFixture) -> None:
    items = [
        {"id": 1, "telegram_id": "not-a-number", "message": "x"},
        {"id": 2, "telegram_id": "12", "message": "ok"},
    ]

    async def send(_bot: object, chat_id: int, item: dict) -> None:
        return None

    counts, ack = _poll(items, send)
    assert counts == (1, 1)
    body = ack.call_args[0][1]
    assert body["delivered"] == [2] and list(body["failed"]) == [1] and "ValueError" in body["failed"][1]
    assert any(r.exc_info for r in caplog.records if "#1" in r.getMessage())


def test_a_polling_network_error_is_one_warning_line(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("WARNING")
    asyncio.run(bot_app._on_handler_error(None, Mock(error=NetworkError("httpx.ReadError"))))
    (record,) = caplog.records
    assert record.levelname == "WARNING" and record.exc_info is None
    assert record.getMessage() == "Telegram polling error: httpx.ReadError"


def test_other_errors_with_no_update_still_log_a_traceback(caplog: pytest.LogCaptureFixture) -> None:
    asyncio.run(bot_app._on_handler_error(None, Mock(error=RuntimeError("boom"))))
    (record,) = caplog.records
    assert record.levelname == "ERROR" and record.exc_info is not None
