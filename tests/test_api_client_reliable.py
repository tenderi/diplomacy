"""``api_post_reliable`` / ``drain_outbox_once`` and the bot's background loops.

``requests`` is mocked; the outbox is a real SQLite file in ``tmp_path``.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import requests
from telegram.error import BadRequest, Forbidden, NetworkError

from server.telegram_bot import api_client, game_context, notifications
from server.telegram_bot.outbox import DELIVERED, PENDING, REJECTED, reset_outbox_for_tests

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def fresh_outbox(tmp_path):
    return reset_outbox_for_tests(tmp_path / "outbox.sqlite3")


def _resp(status: int, body=None, headers=None) -> Mock:
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    resp.json.return_value = body if body is not None else {}
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"{status} error", response=resp)
    else:
        resp.raise_for_status.return_value = None
    return resp


# --- api_post_reliable -------------------------------------------------------

def test_delivered_on_2xx_with_idempotency_key_and_client_timestamp(fresh_outbox, monkeypatch):
    monkeypatch.setattr(api_client, "BOT_SECRET", "s3cret")
    with patch.object(api_client.requests, "post", return_value=_resp(200, {"status": "ok"})) as post:
        result = api_client.api_post_reliable(
            "/games/1/broadcast", {"telegram_id": "5", "text": "hi"}, chat_id=5, description="broadcast"
        )
    assert result.status == "delivered" and result.response == {"status": "ok"}
    assert fresh_outbox.get(result.entry.id).state == DELIVERED

    kwargs = post.call_args.kwargs
    assert kwargs["headers"]["Idempotency-Key"] == result.entry.key
    assert kwargs["headers"]["X-Bot-Secret"] == "s3cret"
    body = kwargs["json"]
    assert body["bot_secret"] == "s3cret"
    # The composed-at time is the entry's creation time, not "now at send".
    assert datetime.fromisoformat(body["client_timestamp"]) == result.entry.created_at


def test_queued_on_connection_error_and_entry_stays_pending(fresh_outbox):
    with patch.object(api_client.requests, "post", side_effect=requests.ConnectionError("refused")):
        result = api_client.api_post_reliable("/games/set_orders", {"orders": []}, chat_id=5, description="orders")
    assert result.status == "queued"
    entry = fresh_outbox.get(result.entry.id)
    assert entry.state == PENDING and entry.attempts == 1 and "ConnectionError" in entry.last_error
    assert entry.next_attempt_at is not None
    assert "queued" in api_client.queued_reply(result)
    assert "/queue" in api_client.queued_reply(result)


@pytest.mark.parametrize("status", [502, 503, 504])
def test_gateway_errors_are_transient(fresh_outbox, status):
    with patch.object(api_client.requests, "post", return_value=_resp(status)):
        result = api_client.api_post_reliable("/x", {}, chat_id=1, description="x")
    assert result.status == "queued"
    assert fresh_outbox.get(result.entry.id).state == PENDING


def test_rejected_on_4xx_with_server_detail(fresh_outbox):
    with patch.object(api_client.requests, "post", return_value=_resp(403, {"detail": "Sender not in game"})):
        result = api_client.api_post_reliable("/x", {}, chat_id=1, description="x")
    assert result.status == "rejected" and result.error == "Sender not in game"
    assert fresh_outbox.get(result.entry.id).state == REJECTED


def test_drain_delivers_in_order_and_stops_at_first_unreachable(fresh_outbox):
    with patch.object(api_client.requests, "post", side_effect=requests.ConnectionError("down")):
        a = api_client.api_post_reliable("/a", {}, chat_id=1, description="a").entry
        b = api_client.api_post_reliable("/b", {}, chat_id=1, description="b").entry
        c = api_client.api_post_reliable("/c", {}, chat_id=2, description="c").entry
    # Make everything due now.
    fresh_outbox._conn.execute("UPDATE outbox SET next_attempt_at = NULL")

    # a succeeds, b is unreachable -> c must NOT be attempted (ordering).
    answers = [_resp(200, {"ok": 1}), requests.ConnectionError("down again")]
    with patch.object(api_client.requests, "post", side_effect=answers) as post:
        finished = api_client.drain_outbox_once()
    assert [r.entry.id for r in finished] == [a.id]
    assert post.call_count == 2
    assert fresh_outbox.get(b.id).state == PENDING
    assert fresh_outbox.get(c.id).state == PENDING and fresh_outbox.get(c.id).attempts == 1


def test_plain_api_calls_raise_a_friendly_unreachable_error():
    with patch.object(api_client.requests, "get", side_effect=requests.ConnectionError("refused")):
        with pytest.raises(api_client.ApiUnreachableError) as exc:
            api_client.api_get("/games")
    assert "unreachable" in str(exc.value) and "/queue" in str(exc.value)
    assert isinstance(exc.value, OSError)  # existing `except OSError` call sites still work
    with patch.object(api_client.requests, "post", side_effect=requests.Timeout("slow")):
        with pytest.raises(api_client.ApiUnreachableError):
            api_client.api_post("/x", {})


# --- game_context cache ------------------------------------------------------

def test_fetch_user_games_falls_back_to_cache_when_unreachable(fresh_outbox):
    with patch.object(game_context, "api_get", return_value={"games": [{"game_id": "1", "power": "FRANCE"}]}):
        assert game_context.fetch_user_games("77") == [{"game_id": "1", "power": "FRANCE"}]
    with patch.object(game_context, "api_get", side_effect=api_client.ApiUnreachableError(OSError())):
        assert game_context.fetch_user_games("77") == [{"game_id": "1", "power": "FRANCE"}]
        assert game_context.resolve_game_and_power("77") == ("1", "FRANCE")
        # No cache for a stranger: the error propagates as before.
        with pytest.raises(api_client.ApiUnreachableError):
            game_context.fetch_user_games("unknown")


# --- notification loop -------------------------------------------------------

def test_render_notification_prefixes_only_when_late():
    now = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    fresh = {"message": "Turn processed", "created_at": (now - timedelta(seconds=10)).isoformat()}
    late = {"message": "Turn processed", "created_at": (now - timedelta(hours=2)).isoformat()}
    yesterday = {"message": "Reminder", "created_at": (now - timedelta(days=1, hours=1)).isoformat()}
    assert notifications.render_notification(fresh, now) == "Turn processed"
    assert notifications.render_notification(late, now) == "⏱ Delayed notification (from 10:00 UTC):\nTurn processed"
    assert notifications.render_notification(yesterday, now).startswith("⏱ Delayed notification (from 2026-09-07 11:00 UTC)")
    assert notifications.render_notification({"message": "x"}, now) == "x"


def _items(*ids):
    return {"items": [{"id": i, "telegram_id": str(100 + i), "message": f"m{i}",
                       "created_at": datetime.now(timezone.utc).isoformat()} for i in ids]}


def test_poll_sends_acks_and_reports_permanent_failures():
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=[None, Forbidden("blocked"), None])
    calls = []
    with patch.object(notifications, "api_get", return_value=_items(1, 2, 3)), \
         patch.object(notifications, "api_post", side_effect=lambda ep, body: calls.append((ep, body)) or {}):
        delivered, failed = asyncio.run(notifications.deliver_pending_notifications(bot))
    assert (delivered, failed) == (2, 1)
    assert calls == [("/bot/outbox/ack", {"delivered": [1, 3], "failed": {2: "Forbidden: blocked"}})]
    assert notifications.api_reachable() is True


def test_poll_stops_batch_on_transient_telegram_error_and_acks_only_sent():
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=[None, NetworkError("tg down")])
    calls = []
    with patch.object(notifications, "api_get", return_value=_items(1, 2, 3)), \
         patch.object(notifications, "api_post", side_effect=lambda ep, body: calls.append(body) or {}):
        delivered, failed = asyncio.run(notifications.deliver_pending_notifications(bot))
    assert (delivered, failed) == (1, 0)
    assert calls == [{"delivered": [1], "failed": {}}]
    bot.send_message.assert_awaited()
    assert bot.send_message.await_count == 2  # #3 was never attempted


def test_poll_when_api_unreachable_sends_nothing_and_notes_state():
    bot = MagicMock()
    bot.send_message = AsyncMock()
    with patch.object(notifications, "api_get", side_effect=api_client.ApiUnreachableError(OSError())):
        assert asyncio.run(notifications.deliver_pending_notifications(bot)) == (0, 0)
    bot.send_message.assert_not_awaited()
    assert notifications.api_reachable() is False


def test_bad_request_is_permanent_too():
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=BadRequest("chat not found"))
    calls = []
    with patch.object(notifications, "api_get", return_value=_items(9)), \
         patch.object(notifications, "api_post", side_effect=lambda ep, body: calls.append(body) or {}):
        asyncio.run(notifications.deliver_pending_notifications(bot))
    assert calls[0]["failed"] == {9: "BadRequest: chat not found"}


# --- replay loop -------------------------------------------------------------

def test_replay_reports_each_finished_entry_to_its_chat(fresh_outbox):
    with patch.object(api_client.requests, "post", side_effect=requests.ConnectionError("down")):
        api_client.api_post_reliable(
            "/games/set_orders", {"orders": ["A PAR H"]}, chat_id=11, description="orders for game 1 (FRANCE): A PAR H"
        )
        api_client.api_post_reliable("/games/1/message", {"text": "x"}, chat_id=22, description="message to GERMANY in game 1")
    fresh_outbox._conn.execute("UPDATE outbox SET next_attempt_at = NULL")

    bot = MagicMock()
    bot.send_message = AsyncMock()
    answers = [
        _resp(200, {"results": [{"success": True, "order": "A PAR H"}]}),
        _resp(403, {"detail": "Sender not in game"}),
    ]
    with patch.object(api_client.requests, "post", side_effect=answers):
        finished = asyncio.run(notifications.replay_outbox(bot))
    assert [r.status for r in finished] == ["delivered", "rejected"]

    sent = {c.kwargs["chat_id"]: c.kwargs["text"] for c in bot.send_message.await_args_list}
    assert "📬 Delivered (queued since" in sent[11] and "✅ A PAR H" in sent[11]
    assert "❌ Not delivered" in sent[22] and "Sender not in game" in sent[22]
    assert fresh_outbox.count_pending() == 0
