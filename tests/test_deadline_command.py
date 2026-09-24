"""F5: the bot's ``/deadline`` command and ``format_deadline``.

Thin-client tests -- every HTTP call is mocked, and both ``api_get``
references matter (``game_context.api_get`` for ``/users/{id}/games``,
``games.api_get``/``api_post`` for the deadline route); see
``test_draw_vote_bot.py`` for why.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.telegram_bot.games import deadline, format_deadline, status

pytestmark = pytest.mark.unit


def _make_update_and_context(user_id: int = 12345, args: list | None = None):
    update = Mock()
    context = Mock()
    context.args = args
    message = Mock()
    message.reply_text = AsyncMock()
    user = Mock()
    user.id = user_id
    update.effective_user = user
    update.message = message
    return update, context, message


_ONE_GAME = {"games": [{"game_id": "1", "power": "FRANCE"}]}
_NOW = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)


class TestFormatDeadline:
    def test_naive_iso_is_read_as_utc_with_relative_time(self):
        assert format_deadline("2026-09-23T13:30:00", now=_NOW) == "2026-09-23 13:30 UTC (in 1d 1h 30m)"

    def test_offset_aware_iso_is_converted_to_utc(self):
        assert format_deadline("2026-09-22T15:00:00+02:00", now=_NOW) == "2026-09-22 13:00 UTC (in 1h 0m)"

    def test_under_an_hour_shows_minutes_only(self):
        assert format_deadline("2026-09-22T12:45:00", now=_NOW) == "2026-09-22 12:45 UTC (in 45m)"

    def test_past_deadline_says_passed(self):
        assert format_deadline("2026-09-22T11:00:00", now=_NOW) == "2026-09-22 11:00 UTC (passed)"

    def test_unparseable_falls_back_to_raw(self):
        assert format_deadline("soon", now=_NOW) == "soon"


class TestDeadlineCommand:
    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_set_hours_posts_a_future_utc_deadline_with_caller_id(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        before = datetime.now(timezone.utc)
        mock_post.return_value = {"status": "ok", "deadline": (before + timedelta(hours=12)).isoformat()}
        update, context, message = _make_update_and_context(args=["1", "12"])

        asyncio.run(deadline(update, context))

        endpoint, body = mock_post.call_args[0]
        assert endpoint == "/games/1/deadline"
        assert body["telegram_id"] == "12345"
        sent = datetime.fromisoformat(body["deadline"])
        assert sent.tzinfo is not None
        assert timedelta(hours=11, minutes=59) < sent - before < timedelta(hours=12, minutes=1)
        text = message.reply_text.call_args[0][0]
        assert "Deadline for game 1 set" in text
        assert "processed automatically" in text

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_clear_posts_null(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        mock_post.return_value = {"status": "ok", "deadline": None}
        update, context, message = _make_update_and_context(args=["1", "clear"])

        asyncio.run(deadline(update, context))

        mock_post.assert_called_once_with(
            "/games/1/deadline", {"deadline": None, "telegram_id": "12345"}
        )
        assert "removed" in message.reply_text.call_args[0][0]

    @patch('server.telegram_bot.games.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    def test_game_id_only_shows_current_deadline(self, mock_ctx_get, mock_get):
        mock_ctx_get.return_value = _ONE_GAME
        mock_get.return_value = {"status": "ok", "deadline": "2099-01-01T00:00:00"}
        update, context, message = _make_update_and_context(args=["1"])

        asyncio.run(deadline(update, context))

        mock_get.assert_called_once_with("/games/1/deadline")
        assert "2099-01-01 00:00 UTC" in message.reply_text.call_args[0][0]

    @patch('server.telegram_bot.games.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    def test_game_id_only_with_no_deadline_explains_how_to_set_one(self, mock_ctx_get, mock_get):
        mock_ctx_get.return_value = _ONE_GAME
        mock_get.return_value = {"status": "ok", "deadline": None}
        update, context, message = _make_update_and_context(args=["1"])

        asyncio.run(deadline(update, context))

        text = message.reply_text.call_args[0][0]
        assert "no deadline" in text
        assert "/deadline 1 <hours>" in text

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_bad_hours_is_usage_not_a_post(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        for bad, reply in ((["1", "soon"], "Usage:"), (["1", "0"], "Hours must be"),
                           (["1", "-3"], "Hours must be"), (["1", "10000"], "Hours must be")):
            update, context, message = _make_update_and_context(args=bad)
            asyncio.run(deadline(update, context))
            mock_post.assert_not_called()
            assert message.reply_text.call_args[0][0].startswith(reply), bad

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_no_args_is_usage(self, mock_ctx_get, mock_post):
        update, context, message = _make_update_and_context(args=[])
        asyncio.run(deadline(update, context))
        mock_post.assert_not_called()
        mock_ctx_get.assert_not_called()
        assert "Usage" in message.reply_text.call_args[0][0]

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_not_in_that_game_is_refused_before_any_post(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        update, context, message = _make_update_and_context(args=["7", "12"])

        asyncio.run(deadline(update, context))

        mock_post.assert_not_called()
        assert "7" in message.reply_text.call_args[0][0]

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_server_refusal_is_shown_verbatim(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        mock_post.side_effect = Exception("You are not a player in this game.")
        update, context, message = _make_update_and_context(args=["1", "12"])

        asyncio.run(deadline(update, context))

        assert "You are not a player in this game." in message.reply_text.call_args[0][0]


class TestDeadlineProposeVoteWithdraw:
    """The majority-vote alternative to a unilateral set: /deadline <id>
    propose|vote|withdraw. Unlike plain set/clear these need the caller's
    *power*, resolved from the same ``/users/{id}/games`` lookup."""

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_propose_hours_posts_power_and_hours(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        mock_post.return_value = {
            "status": "pending", "proposed_by": "FRANCE", "value_hours": 24.0,
            "yes_votes": ["FRANCE"], "no_votes": [], "active_powers": ["FRANCE", "GERMANY"],
            "needed_for_majority": 2, "vote_deadline": None,
        }
        update, context, message = _make_update_and_context(args=["1", "propose", "24"])

        asyncio.run(deadline(update, context))

        mock_post.assert_called_once_with(
            "/games/1/deadline/propose",
            {"power": "FRANCE", "hours": 24.0, "vote_hours": None, "telegram_id": "12345"},
        )
        text = message.reply_text.call_args[0][0]
        assert "FRANCE" in text and "24.0h" in text
        assert "1/2 needed" in text

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_propose_clear_sends_null_hours(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        mock_post.return_value = {
            "status": "pending", "proposed_by": "FRANCE", "value_hours": None,
            "yes_votes": ["FRANCE"], "no_votes": [], "active_powers": ["FRANCE", "GERMANY"],
            "needed_for_majority": 2, "vote_deadline": None,
        }
        update, context, message = _make_update_and_context(args=["1", "propose", "clear"])

        asyncio.run(deadline(update, context))

        body = mock_post.call_args[0][1]
        assert body["hours"] is None

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_propose_with_vote_hours(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        mock_post.return_value = {
            "status": "pending", "proposed_by": "FRANCE", "value_hours": 6.0,
            "yes_votes": ["FRANCE"], "no_votes": [], "active_powers": ["FRANCE", "GERMANY"],
            "needed_for_majority": 2, "vote_deadline": "2099-01-01T00:00:00",
        }
        update, context, message = _make_update_and_context(args=["1", "propose", "6", "2"])

        asyncio.run(deadline(update, context))

        body = mock_post.call_args[0][1]
        assert body["hours"] == 6.0 and body["vote_hours"] == 2.0

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_propose_accepted_immediately_is_announced(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        mock_post.return_value = {"status": "accepted", "value_hours": 24.0}
        update, context, message = _make_update_and_context(args=["1", "propose", "24"])

        asyncio.run(deadline(update, context))

        assert "Applied immediately" in message.reply_text.call_args[0][0]

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_propose_bad_hours_is_usage_not_a_post(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        update, context, message = _make_update_and_context(args=["1", "propose", "soon"])

        asyncio.run(deadline(update, context))

        mock_post.assert_not_called()
        assert "Usage" in message.reply_text.call_args[0][0]

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_vote_yes_posts_true(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        mock_post.return_value = {
            "status": "pending", "proposed_by": "GERMANY", "value_hours": 12.0,
            "yes_votes": ["GERMANY", "FRANCE"], "no_votes": [], "active_powers": ["FRANCE", "GERMANY"],
            "needed_for_majority": 2, "vote_deadline": None,
        }
        update, context, message = _make_update_and_context(args=["1", "vote", "yes"])

        asyncio.run(deadline(update, context))

        mock_post.assert_called_once_with(
            "/games/1/deadline/vote", {"power": "FRANCE", "vote": True, "telegram_id": "12345"}
        )

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_vote_accepted_reports_the_new_deadline(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        mock_post.return_value = {"status": "accepted", "value_hours": 12.0, "deadline": "2030-01-02T03:04:00"}
        update, context, message = _make_update_and_context(args=["1", "vote", "yes"])

        asyncio.run(deadline(update, context))

        text = message.reply_text.call_args[0][0]
        assert "passed" in text and "2030-01-02 03:04 UTC" in text

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_vote_accepted_against_an_older_api_falls_back_to_hours(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        mock_post.return_value = {"status": "accepted", "value_hours": 12.0}  # no "deadline" key
        update, context, message = _make_update_and_context(args=["1", "vote", "yes"])

        asyncio.run(deadline(update, context))

        assert "12.0h from now" in message.reply_text.call_args[0][0]

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    @pytest.mark.parametrize("bad", ["0", "-3", "nan", "721"])
    def test_propose_refuses_a_bad_vote_window_before_calling_the_api(self, mock_ctx_get, mock_post, bad):
        mock_ctx_get.return_value = _ONE_GAME
        update, context, message = _make_update_and_context(args=["1", "propose", "24", bad])

        asyncio.run(deadline(update, context))

        mock_post.assert_not_called()
        assert "Vote hours must be" in message.reply_text.call_args[0][0]

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_vote_rejected_is_reported(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        mock_post.return_value = {"status": "rejected"}
        update, context, message = _make_update_and_context(args=["1", "vote", "no"])

        asyncio.run(deadline(update, context))

        assert "voted down" in message.reply_text.call_args[0][0]

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_vote_bad_arg_is_usage_not_a_post(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        update, context, message = _make_update_and_context(args=["1", "vote", "maybe"])

        asyncio.run(deadline(update, context))

        mock_post.assert_not_called()
        assert "Usage" in message.reply_text.call_args[0][0]

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_withdraw_posts_power(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        mock_post.return_value = {"status": "withdrawn"}
        update, context, message = _make_update_and_context(args=["1", "withdraw"])

        asyncio.run(deadline(update, context))

        mock_post.assert_called_once_with(
            "/games/1/deadline/withdraw", {"power": "FRANCE", "telegram_id": "12345"}
        )
        assert "Withdrew" in message.reply_text.call_args[0][0]

    @patch('server.telegram_bot.games.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    def test_pending_proposal_shown_alongside_plain_deadline_view(self, mock_ctx_get, mock_get):
        mock_ctx_get.return_value = _ONE_GAME
        mock_get.return_value = {
            "status": "ok", "deadline": None,
            "pending_proposal": {
                "proposed_by": "GERMANY", "value_hours": 6.0, "yes_votes": ["GERMANY"],
                "no_votes": [], "needed_for_majority": 2, "vote_deadline": None,
            },
        }
        update, context, message = _make_update_and_context(args=["1"])

        asyncio.run(deadline(update, context))

        texts = [c.args[0] for c in message.reply_text.call_args_list]
        assert any("no deadline" in t for t in texts)
        assert any("GERMANY" in t and "6.0h" in t for t in texts)


class TestStatusShowsFormattedDeadline:
    @patch('server.telegram_bot.games.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    def test_status_uses_format_deadline(self, mock_ctx_get, mock_get):
        mock_ctx_get.return_value = _ONE_GAME

        def fake_get(endpoint, **kwargs):
            if endpoint.endswith("/deadline"):
                return {"status": "ok", "deadline": "2099-01-01T00:00:00"}
            if endpoint.endswith("/orders_status"):
                return {"submitted": [], "missing": []}
            if endpoint.endswith("/draw_vote_status"):
                return {"votes": [], "required": []}
            return {"phase": "S1901M", "phase_type": "MOVEMENT", "year": 1901, "season": "SPRING"}

        mock_get.side_effect = fake_get
        update, context, message = _make_update_and_context(args=["1"])

        asyncio.run(status(update, context))

        text = message.reply_text.call_args[0][0]
        assert "2099-01-01 00:00 UTC (in " in text
        assert "2099-01-01T00:00:00" not in text
