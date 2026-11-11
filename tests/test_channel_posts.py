"""Posts into a game's linked Telegram group: the three formatters in
``telegram_bot/channels.py`` and the ``/games/{id}/channel/*`` routes that queue them.

Every post is sent with ``parse_mode='Markdown'`` (legacy), so bold is ``*single*``.
"""
from __future__ import annotations

import ast
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.table_helpers import fill_with_dummies
from fastapi.testclient import TestClient

from server.api import ADMIN_TOKEN, app
from server.api.shared import db_service
from server.telegram_bot.channels import format_historical_timeline, format_player_dashboard
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

BOT = {"X-Bot-Secret": BOT_SECRET}
GROUP = "-1009876543"
# Tests reuse one group id: an admin may move its link from the last test's game.
ADMIN_LINK = {**BOT, "X-Admin-Token": ADMIN_TOKEN}
SRC = Path(__file__).parent.parent / "src"


def _lines(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines()]


class TestNoDoubleAsteriskBold:
    def test_telegram_bound_strings_use_legacy_single_asterisk_bold(self) -> None:
        """``**x**`` is MarkdownV2/CommonMark; in legacy Markdown it is two empty bold
        spans around plain text, so the heading was never bold."""
        offenders = []
        for path in [*(SRC / "server" / "telegram_bot").glob("*.py"), SRC / "server" / "api" / "routes" / "channels.py", SRC / "server" / "api" / "shared.py"]:
            tree = ast.parse(path.read_text())
            docstrings = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr)}
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                    if re.search(r"\*\*[^\s*]", node.value):
                        offenders.append(f"{path.name}:{node.lineno}: {node.value[:60]!r}")
        assert not offenders, "\n".join(offenders)


class TestPlayerDashboard:
    def _state(self, powers: dict, orders: dict | None = None) -> dict:
        return {"game_id": "7", "current_year": 1901, "current_season": "SPRING", "current_phase": "MOVEMENT",
                "orders": orders or {}, "powers": powers}

    def test_as_the_route_calls_it(self) -> None:
        powers = {
            "FRANCE": {"orders_submitted": True, "last_order_time": None, "is_eliminated": False},
            "ITALY": {"orders_submitted": False, "last_order_time": None, "is_eliminated": False},
            "TURKEY": {"orders_submitted": False, "last_order_time": None, "is_eliminated": True},
        }
        players = [{"power": "FRANCE", "nickname": "Ann-Marie", "telegram_id": "1"},
                   {"power": "ITALY", "nickname": None, "telegram_id": "555"}]
        assert _lines(format_player_dashboard(self._state(powers), players)) == [
            "👥 *PLAYER STATUS DASHBOARD - GAME 7*",
            "📅 SPRING 1901 - MOVEMENT Phase",
            "",
            "✅ *Orders Submitted:*",
            "🇫🇷 FRANCE (Ann-Marie) - Submitted",
            "",
            "❌ *No Orders:*",
            "🇮🇹 ITALY - No orders",
            "🇹🇷 TURKEY - Eliminated",
            "",
        ]

    def test_an_order_in_the_state_counts_as_submitted(self) -> None:
        powers = {"GERMANY": {"orders_submitted": False, "is_eliminated": False}}
        assert "🇩🇪 GERMANY - Submitted" in format_player_dashboard(self._state(powers, orders={"GERMANY": ["A BER H"]}))

    def test_times_say_ago_once(self) -> None:
        now = datetime.now(timezone.utc)
        powers = {
            "FRANCE": {"orders_submitted": True, "last_order_time": (now - timedelta(hours=3, minutes=5)).isoformat()},
            "ITALY": {"orders_submitted": False, "last_order_time": (now - timedelta(days=2, hours=1)).replace(tzinfo=None)},
            "RUSSIA": {"orders_submitted": True, "last_order_time": (now - timedelta(minutes=7)).isoformat().replace("+00:00", "Z")},
        }
        text = format_player_dashboard(self._state(powers))
        assert "🇫🇷 FRANCE - Submitted 3h ago\n" in text
        assert "🇷🇺 RUSSIA - Submitted 7m ago\n" in text
        assert "⏳ *Pending:*\n🇮🇹 ITALY - Last active 2d ago\n" in text
        assert "ago ago" not in text

    def test_an_unreadable_time_is_left_out(self) -> None:
        powers = {"FRANCE": {"orders_submitted": True, "last_order_time": "yesterday-ish"}}
        assert "🇫🇷 FRANCE - Submitted\n" in format_player_dashboard(self._state(powers))


class TestHistoricalTimeline:
    @staticmethod
    def _power(centers: int, eliminated: bool = False) -> dict:
        return {"controlled_supply_centers": [f"C{i}" for i in range(centers)], "is_eliminated": eliminated}

    def test_as_the_route_calls_it_no_events_and_the_top_five(self) -> None:
        powers = {"AUSTRIA": self._power(3), "ENGLAND": self._power(5), "FRANCE": self._power(4), "GERMANY": self._power(2),
                  "ITALY": self._power(0, eliminated=True), "RUSSIA": self._power(6), "TURKEY": self._power(1)}
        state = {"game_id": "7", "current_year": 1905, "current_season": "Fall", "powers": powers, "supply_centers": {}}
        assert _lines(format_historical_timeline(state)) == [
            "📜 *HISTORICAL TIMELINE - GAME 7*",
            "",
            "*No major events recorded yet.*",
            "",
            "*Current Status:*",
            "• 🇷🇺 RUSSIA: 6 centers",
            "• 🇬🇧 ENGLAND: 5 centers",
            "• 🇫🇷 FRANCE: 4 centers",
            "• 🇦🇹 AUSTRIA: 3 centers",
            "• 🇩🇪 GERMANY: 2 centers",
        ]

    @staticmethod
    def _board(phase: str, centers: dict, units: dict | None = None) -> dict:
        return {"phase_code": phase, "centers": centers, "units": units if units is not None else dict(centers)}

    def _history(self) -> list:
        return [
            self._board("S1901M", {"ITALY": 3, "AUSTRIA": 3, "FRANCE": 3, "RUSSIA": 4}),
            self._board("F1901M", {"ITALY": 3, "AUSTRIA": 3, "FRANCE": 3, "RUSSIA": 4}),  # quiet turn
            self._board("S1902M", {"ITALY": 1, "AUSTRIA": 5, "FRANCE": 4, "RUSSIA": 4}),  # ITALY -2, AUSTRIA +2
            self._board("F1902M", {"AUSTRIA": 6, "FRANCE": 4, "RUSSIA": 4}, {"AUSTRIA": 6, "FRANCE": 4, "RUSSIA": 4}),
            self._board("S1903M", {"AUSTRIA": 6, "FRANCE": 4, "RUSSIA": 4}),
        ]

    def test_each_turn_with_events_gets_a_heading(self) -> None:
        powers = {"AUSTRIA": self._power(6), "FRANCE": self._power(4), "RUSSIA": self._power(4)}
        state = {"game_id": "7", "powers": powers}
        assert format_historical_timeline(state, self._history()) == (
            "📜 *HISTORICAL TIMELINE - GAME 7*\n\n"
            "*Fall 1901:*\n"
            "• 🇦🇹 AUSTRIA gains 2 supply centers\n"
            "• 🇮🇹 ITALY loses 2 supply centers\n\n"
            "*Spring 1902:*\n"
            "• 🇮🇹 ITALY eliminated\n\n"
            "*Current Status:*\n"
            "• 🇦🇹 AUSTRIA: 6 centers\n"
            "• 🇫🇷 FRANCE: 4 centers\n"
            "• 🇷🇺 RUSSIA: 4 centers\n"
        )

    def test_a_win_is_an_event_of_the_turn_that_made_it(self) -> None:
        history = [self._board("F1910M", {"RUSSIA": 16, "FRANCE": 4}), self._board("W1910A", {"RUSSIA": 18, "FRANCE": 3})]
        text = format_historical_timeline({"game_id": "7", "powers": {}}, history)
        assert "*Fall 1910:*\n• 🇷🇺 RUSSIA gains 2 supply centers\n• 🏆 🇷🇺 RUSSIA achieves victory with 18 supply centers\n\n" in text

    def test_a_power_with_units_but_no_centres_is_not_eliminated(self) -> None:
        history = [self._board("F1901M", {"ITALY": 1}, {"ITALY": 1}), self._board("S1902M", {}, {"ITALY": 1})]
        assert "No major events recorded yet." in format_historical_timeline({"game_id": "7", "powers": {}}, history)

    def test_a_long_history_keeps_the_newest_turns(self) -> None:
        history = []
        for year in range(1901, 1960):
            history.append(self._board(f"F{year}M", {"AUSTRIA": 3}))
            history.append(self._board(f"S{year + 1}M", {"AUSTRIA": 5}))
            history.append(self._board(f"F{year + 1}M", {"AUSTRIA": 3}))
        text = format_historical_timeline({"game_id": "7", "powers": {}}, history)
        assert len(text) <= 4096
        assert "_Earlier turns left out._" in text
        assert "*Fall 1959:*" in text and "*Fall 1901:*" not in text


needs_db = pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")


@needs_db
class TestRoutesQueueForTheGroup:
    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def _linked_game(self, client: TestClient) -> tuple[str, str]:
        creator = _telegram_user(client, "Ann-Marie")
        self.nickname = f"Ann {creator[-6:]}"  # nicknames are unique; the test DB outlives a run
        assert client.post("/users/nickname", json=_as(creator, nickname=self.nickname)).status_code == 200
        game_id = str(client.post("/games/create", json=_as(creator, map_name="standard"), headers=BOT).json()["game_id"])
        assert client.post(f"/games/{game_id}/join", json=_as(creator, power="FRANCE")).status_code == 200
        assert client.post(f"/games/{game_id}/channel/link", json={"channel_id": GROUP}, headers=ADMIN_LINK).status_code == 200
        return game_id, creator

    def _post(self, client: TestClient, path: str, **kw: object) -> dict:
        with OutboxProbe() as probe:
            resp = client.post(path, headers=BOT, **kw)
            assert resp.status_code == 200, resp.text
        rows = [r for r in probe.rows() if str(r["telegram_id"]) == GROUP]
        assert len(rows) == 1 and rows[0]["id"] == resp.json()["outbox_id"]
        return rows[0]

    def test_dashboard_names_the_seated_players(self, client: TestClient) -> None:
        game_id, creator = self._linked_game(client)
        fill_with_dummies(game_id)
        client.post("/games/set_orders", json=_as(creator, game_id=game_id, power="FRANCE", orders=["A PAR H"]))
        row = self._post(client, f"/games/{game_id}/channel/dashboard")
        assert row["kind"] == "channel_text" and row["payload"]["parse_mode"] == "Markdown"
        assert row["message"].startswith(f"👥 *PLAYER STATUS DASHBOARD - GAME {game_id}*\n📅 SPRING 1901 - MOVEMENT Phase")
        assert f"🇫🇷 FRANCE ({self.nickname}) - Submitted" in row["message"]
        assert "🇩🇪 GERMANY - No orders" in row["message"]

    def test_timeline_ranks_the_opening_board(self, client: TestClient) -> None:
        game_id, _ = self._linked_game(client)
        timeline = self._post(client, f"/games/{game_id}/channel/timeline")["message"]
        assert "• 🇷🇺 RUSSIA: 4 centers" in timeline
        assert client.get(f"/games/{game_id}/channel/timeline", headers=BOT).json()["timeline"] == timeline

    def test_timeline_reads_the_snapshot_trail(self, client: TestClient) -> None:
        game_id, _ = self._linked_game(client)
        row = db_service.get_game_by_game_id(game_id)
        boards = [
            (0, "F1901M", {"VEN": "ITALY", "ROM": "ITALY", "NAP": "ITALY"}, [{"power": "ITALY"}]),
            (1, "S1902M", {"VEN": "AUSTRIA", "ROM": "AUSTRIA", "NAP": "AUSTRIA"}, [{"power": "AUSTRIA"}]),
        ]
        for turn, code, centres, units in boards:
            db_service.create_game_snapshot(
                int(row.id), turn, 1901 + turn // 2, "Fall", "Movement", code,
                {"units": units, "supply_centers": centres},
            )
        timeline = client.get(f"/games/{game_id}/channel/timeline", headers=BOT).json()["timeline"]
        assert "*Fall 1901:*\n• 🇦🇹 AUSTRIA gains 3 supply centers\n• 🇮🇹 ITALY eliminated\n\n" in timeline

    def test_broadcast_is_attributed_and_escaped(self, client: TestClient) -> None:
        game_id, creator = self._linked_game(client)
        row = self._post(client, f"/games/{game_id}/channel/broadcast",
                         json={"telegram_id": creator, "message": "Go *now* [x](y)", "power": "FRANCE", "reply_to_message_id": 9})
        assert row["message"] == "📢 *FRANCE* → All Powers\n\nGo \\*now\\* \\[x](y)"
        assert row["payload"]["reply_to_message_id"] == 9
        public = self._post(client, f"/games/{game_id}/channel/broadcast", json={"telegram_id": creator, "message": "hi"})
        assert public["message"] == "📢 *PUBLIC BROADCAST*\n\nhi"

    def test_the_current_map_is_queued_by_path(self, client: TestClient) -> None:
        """This route used to answer success and post nothing ("will be implemented")."""
        game_id, _ = self._linked_game(client)
        row = self._post(client, f"/games/{game_id}/channel/map")
        assert (row["kind"], row["message"]) == ("channel_map", f"🗺️ Game {game_id} · Spring 1901 movement: the board now")
        assert row["payload"] == {"game_id": game_id, "path": f"/games/{game_id}/map"}

    def test_thread_is_queued_with_its_title(self, client: TestClient) -> None:
        game_id, _ = self._linked_game(client)
        row = self._post(client, f"/games/{game_id}/channel/thread", json={"topic": "Spring talks", "phase": "S1901M"})
        assert (row["kind"], row["message"]) == ("channel_create_thread", "Spring talks - S1901M")

    @pytest.mark.parametrize("route", ["map", "dashboard", "timeline", "thread", "broadcast"])
    def test_an_unlinked_game_is_404_and_queues_nothing(self, client: TestClient, route: str) -> None:
        creator = _telegram_user(client, "nolink")
        game_id = str(client.post("/games/create", json=_as(creator, map_name="standard"), headers=BOT).json()["game_id"])
        body = {"topic": "t", "telegram_id": creator, "message": "m"}
        with OutboxProbe() as probe:
            assert client.post(f"/games/{game_id}/channel/{route}", json=body, headers=BOT).status_code == 404
        assert probe.rows() == []

    def test_the_timeline_read_is_members_only(self, client: TestClient) -> None:
        game_id, _ = self._linked_game(client)
        assert client.get(f"/games/{game_id}/channel/timeline").status_code == 403
