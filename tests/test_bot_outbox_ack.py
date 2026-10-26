"""BU4: the bot's at-least-once delivery from the API's outbox."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.telegram_bot import api_client, notifications

pytestmark = pytest.mark.unit


def test_a_lost_ack_leaves_the_rows_to_be_sent_again_next_poll() -> None:
    page = {"items": [{"id": 1, "telegram_id": "101", "message": "a"}, {"id": 2, "telegram_id": "102", "message": "b"}]}
    bot = MagicMock()
    bot.send_message = AsyncMock()
    acks: list[tuple[str, dict]] = []

    def ack(endpoint: str, body: dict) -> dict:
        acks.append((endpoint, body))
        if len(acks) == 1:
            raise api_client.ApiUnreachableError(OSError("down"))
        return {}

    with patch.object(notifications, "api_get", return_value=page), patch.object(notifications, "api_post", side_effect=ack):
        first = asyncio.run(notifications.deliver_pending_notifications(bot))
        # The server never saw the ack, so it offers the same rows again.
        second = asyncio.run(notifications.deliver_pending_notifications(bot))

    assert first == (2, 0)  # sent; the count only paces the loop, it is not an ack
    assert second == (2, 0)
    assert [(c.kwargs["chat_id"], c.kwargs["text"]) for c in bot.send_message.await_args_list] == [
        (101, "a"), (102, "b"), (101, "a"), (102, "b"),
    ]
    assert acks == [("/bot/outbox/ack", {"delivered": [1, 2], "failed": {}})] * 2


def test_channel_create_thread_creates_a_forum_topic_and_is_acked() -> None:
    page = {"items": [{"id": 5, "telegram_id": "-1001", "kind": "channel_create_thread", "message": "Spring talks"}]}
    bot = MagicMock()
    bot.create_forum_topic = AsyncMock()
    bot.send_message = AsyncMock()
    with patch.object(notifications, "api_get", return_value=page), \
         patch.object(notifications, "api_post", return_value={}) as ack:
        assert asyncio.run(notifications.deliver_pending_notifications(bot)) == (1, 0)
    bot.create_forum_topic.assert_awaited_once_with(chat_id=-1001, name="Spring talks")
    bot.send_message.assert_not_awaited()
    ack.assert_called_once_with("/bot/outbox/ack", {"delivered": [5], "failed": {}})


def test_channel_create_thread_without_a_name_is_called_discussion() -> None:
    bot = MagicMock()
    bot.create_forum_topic = AsyncMock()
    asyncio.run(notifications._send_outbox_item(bot, -1001, {"kind": "channel_create_thread", "message": ""}))
    bot.create_forum_topic.assert_awaited_once_with(chat_id=-1001, name="Discussion")
