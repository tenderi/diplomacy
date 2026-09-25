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
from fastapi.testclient import TestClient

from server.api import app
from server.telegram_bot.channels import format_battle_results, format_historical_timeline, format_player_dashboard
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

BOT = {"X-Bot-Secret": BOT_SECRET}
GROUP = "-1009876543"
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


class TestBattleResults:
    CENTERS = {
        "RUSSIA": ["MOS", "WAR", "SEV", "STP"],
        "AUSTRIA": ["VIE", "BUD", "TRI"],
        "ENGLAND": ["LON", "EDI", "LVP"],
        "ITALY": ["ROM", "VEN"],
    }

    def _state(self, **extra: object) -> dict:
        return {"current_year": 1902, "current_season": "Fall", "supply_centers": self.CENTERS, "units": {}, **extra}

    def test_as_the_route_calls_it_header_and_dense_ranking(self) -> None:
        assert _lines(format_battle_results(self._state())) == [
            "⚔️ *ADJUDICATION RESULTS - FALL 1902*",
            "",
            "📈 *Power Rankings:*",
            "1. 🇷🇺 RUSSIA (4 centers)",
            "2. 🇦🇹 AUSTRIA (3 centers)",
            "2. 🇬🇧 ENGLAND (3 centers)",
            "3. 🇮🇹 ITALY (2 centers)",
        ]

    def test_moves_are_split_into_attacks_and_bounces(self) -> None:
        history = {
            "AUSTRIA": [{"order_type": "move", "status": "success", "unit": {"unit_type": "A", "province": "VIE"}, "target_province": "TRI"}],
            "ENGLAND": [
                {"order_type": "MOVE", "status": "bounced", "unit": {"unit_type": "F", "province": "NTH"}, "target_province": "NOR"},
                {"order_type": "move", "status": "failed", "unit": {"unit_type": "A", "province": "LVP"}, "target_province": "YOR"},
                {"order_type": "hold", "status": "success", "unit": {"unit_type": "F", "province": "LON"}},
            ],
        }
        text = format_battle_results(self._state(), order_history=history)
        assert "🎯 *Successful Attacks:*\n• A VIE → TRI\n\n" in text
        assert "🔄 *Bounced Movements:*\n• F NTH → NOR (bounced)\n• A LVP → YOR (bounced)\n\n" in text
        assert "LON" not in text.split("📈")[0]  # a hold is neither

    def test_dislodgements_name_the_attacker(self) -> None:
        units = {"ITALY": [{"unit_type": "A", "province": "DISLODGED_VEN", "is_dislodged": True, "dislodged_by": "A TRI"}]}
        assert "💥 *Dislodgements:*\n• A VEN dislodged by A TRI\n\n" in format_battle_results(self._state(units=units))

    def test_center_changes_and_trend_arrows(self) -> None:
        previous = {**self.CENTERS, "AUSTRIA": ["VIE", "BUD"], "ITALY": ["ROM", "VEN", "TRI"]}
        text = format_battle_results(self._state(), previous_supply_centers=previous)
        changes = text.split("📊 *Supply Center Changes:*\n")[1].split("\n\n")[0].splitlines()
        assert sorted(changes) == ["🇦🇹 AUSTRIA: +1 (TRI captured)", "🇮🇹 ITALY: -1 (TRI lost)"]
        assert "2. 🇦🇹 AUSTRIA (3 centers) ↗️" in text
        assert "3. 🇮🇹 ITALY (2 centers) ↘️" in text
        assert "1. 🇷🇺 RUSSIA (4 centers) →" in text

    def test_bad_input_degrades_to_an_error_post_instead_of_raising(self) -> None:
        assert format_battle_results(None).startswith("⚔️ *ADJUDICATION RESULTS*\n\nError formatting results:")  # type: ignore[arg-type]


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
        players = [{"power": "FRANCE", "full_name": "Ann-Marie", "telegram_id": "1"},
                   {"power": "ITALY", "full_name": None, "telegram_id": "555"}]
        assert _lines(format_player_dashboard(self._state(powers), players)) == [
            "👥 *PLAYER STATUS DASHBOARD - GAME 7*",
            "📅 SPRING 1901 - MOVEMENT Phase",
            "",
            "✅ *Orders Submitted:*",
            "🇫🇷 FRANCE (Ann-Marie) - Submitted",
            "",
            "❌ *No Orders:*",
            "🇮🇹 ITALY (User 555) - No orders",
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

    def test_eliminations_swings_of_two_and_a_win_are_events(self) -> None:
        previous = {"ITALY": self._power(1), "AUSTRIA": self._power(5), "FRANCE": self._power(4), "RUSSIA": self._power(16)}
        current = {"ITALY": self._power(0, eliminated=True), "AUSTRIA": self._power(3), "FRANCE": self._power(5), "RUSSIA": self._power(18)}
        state = {"game_id": "7", "current_year": 1910, "current_season": "Fall", "powers": current, "supply_centers": {"x": []}}
        events = format_historical_timeline(state, previous_powers=previous).split("*Fall 1910:*\n")[1].split("\n\n")[0]
        assert events.splitlines() == [
            "• 🇮🇹 ITALY eliminated",
            "• 🇦🇹 AUSTRIA loses 2 supply centers",
            "• 🇷🇺 RUSSIA gains 2 supply centers",
            "• 🏆 🇷🇺 RUSSIA achieves victory with 18 supply centers",
        ]  # FRANCE's +1 is not an event


needs_db = pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")


@needs_db
class TestRoutesQueueForTheGroup:
    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def _linked_game(self, client: TestClient) -> tuple[str, str]:
        creator = _telegram_user(client, "Ann-Marie")
        game_id = str(client.post("/games/create", json=_as(creator, map_name="standard"), headers=BOT).json()["game_id"])
        assert client.post(f"/games/{game_id}/join", json=_as(creator, power="FRANCE")).status_code == 200
        assert client.post(f"/games/{game_id}/channel/link", json={"channel_id": GROUP}, headers=BOT).status_code == 200
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
        client.post("/games/set_orders", json=_as(creator, game_id=game_id, power="FRANCE", orders=["A PAR H"]))
        row = self._post(client, f"/games/{game_id}/channel/dashboard")
        assert row["kind"] == "channel_text" and row["payload"]["parse_mode"] == "Markdown"
        assert row["message"].startswith(f"👥 *PLAYER STATUS DASHBOARD - GAME {game_id}*\n📅 SPRING 1901 - MOVEMENT Phase")
        assert "🇫🇷 FRANCE (Ann-Marie) - Submitted" in row["message"]
        assert "🇩🇪 GERMANY - No orders" in row["message"]

    def test_timeline_and_battle_results_rank_the_opening_board(self, client: TestClient) -> None:
        game_id, _ = self._linked_game(client)
        timeline = self._post(client, f"/games/{game_id}/channel/timeline")["message"]
        assert "• 🇷🇺 RUSSIA: 4 centers" in timeline
        results = self._post(client, f"/games/{game_id}/channel/battle_results")["message"]
        assert "1. 🇷🇺 RUSSIA (4 centers)" in results and "🇮🇹 ITALY (3 centers)" in results
        assert client.get(f"/games/{game_id}/channel/timeline", headers=BOT).json()["timeline"] == timeline

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

    @pytest.mark.parametrize("route", ["map", "dashboard", "timeline", "battle_results", "thread", "broadcast"])
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
