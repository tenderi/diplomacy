"""Tests for the Telegram bot's draw-vote client UX: ``/draw``, ``/nodraw``,
and the draw-vote line added to ``/status``.

These are thin-client tests -- the bot never touches the engine or DB, so
every HTTP call is mocked. Two separate ``api_get``/``api_post`` references
matter here (same gotcha as ``test_interactive_orders.py``):
- ``server.telegram_bot.game_context.api_get`` -- used by
  ``resolve_game_and_power`` to fetch ``/users/{id}/games``.
- ``server.telegram_bot.games.api_get``/``api_post`` -- used directly by
  ``games.py`` for ``/games/{id}/state``, ``/draw_vote_status``, and
  ``/draw_vote``.
Both must be patched independently; patching only one leaves the other
making a real (failing) network call.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.telegram_bot.games import draw, nodraw, status

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


class TestDrawCommand:
    """``/draw`` casts a yes vote via POST /games/{id}/draw_vote."""

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_draw_recorded_no_quorum(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        mock_post.return_value = {
            "status": "recorded",
            "game_status": "ACTIVE",
            "votes": ["FRANCE"],
            "required": ["FRANCE", "GERMANY", "ENGLAND"],
            "quorum_reached": False,
        }
        update, context, message = _make_update_and_context()

        asyncio.run(draw(update, context))

        mock_post.assert_called_once_with(
            "/games/1/draw_vote",
            {"power": "FRANCE", "vote": True, "telegram_id": "12345"},
        )
        text = message.reply_text.call_args[0][0]
        assert "recorded" in text
        assert "1/3 voted" in text
        assert "FRANCE" in text

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_draw_reaches_quorum_ends_game(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        mock_post.return_value = {
            "status": "completed",
            "game_status": "COMPLETED",
            "winners": ["ENGLAND", "FRANCE", "GERMANY"],
            "votes": ["ENGLAND", "FRANCE", "GERMANY"],
            "required": ["ENGLAND", "FRANCE", "GERMANY"],
            "quorum_reached": True,
        }
        update, context, message = _make_update_and_context()

        asyncio.run(draw(update, context))

        text = message.reply_text.call_args[0][0]
        assert "Draw reached" in text
        assert "ENGLAND" in text and "FRANCE" in text and "GERMANY" in text

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_draw_with_explicit_game_id(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = {
            "games": [
                {"game_id": "1", "power": "FRANCE"},
                {"game_id": "2", "power": "GERMANY"},
            ]
        }
        mock_post.return_value = {
            "status": "recorded", "game_status": "ACTIVE",
            "votes": ["GERMANY"], "required": ["GERMANY", "FRANCE"],
            "quorum_reached": False,
        }
        update, context, _ = _make_update_and_context(args=["2"])

        asyncio.run(draw(update, context))

        mock_post.assert_called_once_with(
            "/games/2/draw_vote",
            {"power": "GERMANY", "vote": True, "telegram_id": "12345"},
        )

    @patch('server.telegram_bot.game_context.api_get')
    def test_draw_no_games(self, mock_ctx_get):
        mock_ctx_get.return_value = {"games": []}
        update, context, message = _make_update_and_context()

        asyncio.run(draw(update, context))

        message.reply_text.assert_called_once()
        text = message.reply_text.call_args[0][0]
        assert "not in any games" in text

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_draw_api_failure_reports_gracefully(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        mock_post.side_effect = Exception("boom")
        update, context, message = _make_update_and_context()

        asyncio.run(draw(update, context))

        text = message.reply_text.call_args[0][0]
        assert "Draw vote failed" in text


class TestNodrawCommand:
    """``/nodraw`` withdraws a yes vote (``vote: False``)."""

    @patch('server.telegram_bot.games.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_nodraw_withdraws_vote(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = _ONE_GAME
        mock_post.return_value = {
            "status": "recorded",
            "game_status": "ACTIVE",
            "votes": [],
            "required": ["FRANCE", "GERMANY", "ENGLAND"],
            "quorum_reached": False,
        }
        update, context, message = _make_update_and_context()

        asyncio.run(nodraw(update, context))

        mock_post.assert_called_once_with(
            "/games/1/draw_vote",
            {"power": "FRANCE", "vote": False, "telegram_id": "12345"},
        )
        text = message.reply_text.call_args[0][0]
        assert "withdrawn" in text
        assert "0/3 voted" in text


class TestStatusDrawVoteLine:
    """``/status`` grows a draw-vote tally line, degrading gracefully on failure."""

    @patch('server.telegram_bot.games.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    def test_status_shows_draw_tally(self, mock_ctx_get, mock_games_get):
        mock_ctx_get.return_value = _ONE_GAME

        def games_get_side_effect(endpoint, telegram_id=None):
            if endpoint.endswith("/state"):
                return {"year": 1901, "season": "SPRING", "phase_type": "MOVEMENT", "phase": "S1901M"}
            if endpoint.endswith("/deadline"):
                return {"deadline": None}
            if endpoint.endswith("/orders_status"):
                return {"submitted": ["FRANCE"], "missing": ["GERMANY"]}
            if endpoint.endswith("/draw_vote_status"):
                return {
                    "phase": "S1901M", "game_status": "ACTIVE",
                    "required": ["FRANCE", "GERMANY", "ENGLAND"],
                    "votes": ["FRANCE"], "missing": ["GERMANY", "ENGLAND"],
                    "quorum_reached": False,
                }
            raise AssertionError(f"unexpected endpoint {endpoint}")

        mock_games_get.side_effect = games_get_side_effect
        update, context, message = _make_update_and_context()

        asyncio.run(status(update, context))

        text = message.reply_text.call_args[0][0]
        assert "Draw vote" in text
        assert "1/3 voted for draw" in text
        assert "FRANCE" in text

    @patch('server.telegram_bot.games.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    def test_status_degrades_gracefully_when_draw_vote_status_fails(self, mock_ctx_get, mock_games_get):
        """A failing GET /draw_vote_status must not break /status entirely."""
        mock_ctx_get.return_value = _ONE_GAME

        def games_get_side_effect(endpoint, telegram_id=None):
            if endpoint.endswith("/state"):
                return {"year": 1901, "season": "SPRING", "phase_type": "MOVEMENT", "phase": "S1901M"}
            if endpoint.endswith("/deadline"):
                return {"deadline": None}
            if endpoint.endswith("/orders_status"):
                return {"submitted": [], "missing": ["FRANCE"]}
            if endpoint.endswith("/draw_vote_status"):
                raise Exception("network error")
            raise AssertionError(f"unexpected endpoint {endpoint}")

        mock_games_get.side_effect = games_get_side_effect
        update, context, message = _make_update_and_context()

        asyncio.run(status(update, context))

        message.reply_text.assert_called_once()
        text = message.reply_text.call_args[0][0]
        assert "Game 1 Status" in text
        assert "Draw vote" not in text
