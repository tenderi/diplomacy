"""
Unit tests for games API routes.

Tests all game management endpoints including creation, state management,
player management, deadlines, and snapshots.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from server.api import app
from server.api.shared import db_service, server
from tests.conftest import _get_db_url

BOT_SECRET = "test_bot_secret_for_tests"


@pytest.fixture
def client():
    """Create test client with bot/user auth bypassed (tests non-auth behavior)."""
    from server.api.routes.auth import require_bot_or_user
    app.dependency_overrides[require_bot_or_user] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestCreateGame:
    """Test game creation endpoint."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    @pytest.mark.parametrize("body", [{"map_name": "standard"}, {}])
    def test_create_game_starts_at_the_standard_opening(self, client, body):
        """An omitted map_name means the standard map."""
        resp = client.post("/games/create", json=body)
        assert resp.status_code == 200
        state = client.get(f"/games/{resp.json()['game_id']}/state").json()
        assert (state["map_name"], state["phase"], state["status"]) == ("standard", "S1901M", "ACTIVE")
        assert len(state["units"]) == 22
        assert sum(len(units) for units in state["units_by_power"].values()) == 22


@pytest.mark.unit
class TestAddPlayer:
    """Test add player endpoint."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_add_player_success(self, client):
        """Test successful player addition."""
        # Create game first
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        
        resp = client.post("/games/add_player", json={"game_id": game_id, "power": "france"})
        assert resp.status_code == 200, resp.text
        assert [p["power"] for p in client.get(f"/games/{game_id}/players").json()] == ["FRANCE"]
        assert client.post("/games/add_player", json={"game_id": game_id, "power": "FRANCE"}).status_code == 400
        assert client.post("/games/add_player", json={"game_id": game_id, "power": "ATLANTIS"}).status_code == 400


@pytest.mark.unit
class TestGetGameState:
    """Test get game state endpoint."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_game_state_success(self, client):
        """Test successful game state retrieval."""
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        resp = client.get(f"/games/{game_id}/state")
        assert resp.status_code == 200
        data = resp.json()
        assert str(data["game_id"]) == str(game_id)
        assert (data["year"], data["season"], data["phase_type"]) == (1901, "SPRING", "MOVEMENT")
        assert data["ownership"]["PAR"] == "FRANCE" and data["ownership"]["STP"] == "RUSSIA"
        assert len(data["ownership"]) == 22  # home centres only; the 12 neutrals are unowned
        assert data["orders"] == {}

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_game_state_not_found(self, client):
        """Test getting state for non-existent game."""
        resp = client.get("/games/nonexistent/state")
        assert resp.status_code == 404


@pytest.mark.unit
class TestListGames:
    """Test list games endpoint."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_list_games_success(self, client):
        """Test successful game listing."""
        game_id = client.post("/games/create", json={"map_name": "standard"}).json()["game_id"]
        client.post("/games/add_player", json={"game_id": game_id, "power": "FRANCE"})
        resp = client.get("/games")
        assert resp.status_code == 200
        listed = [g for g in resp.json()["games"] if str(g["game_id"]) == str(game_id)]
        assert len(listed) == 1
        assert (listed[0]["player_count"], listed[0]["max_players"], listed[0]["private"]) == (1, 7, False)


@pytest.mark.unit
class TestGetPlayers:
    """Test get players endpoint."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_players_success(self, client):
        """Test successful player listing."""
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        client.post("/games/add_player", json={"game_id": game_id, "power": "FRANCE"})
        resp = client.get(f"/games/{game_id}/players")
        assert resp.status_code == 200
        assert [(p["power"], p["user_id"], p["is_active"]) for p in resp.json()] == [("FRANCE", None, True)]
    
    def test_get_players_not_found(self, client):
        """Test getting players for non-existent game."""
        resp = client.get("/games/nonexistent/players")
        # May return 404 or 500 depending on error handling
        assert resp.status_code == 404, resp.text


@pytest.mark.unit
class TestJoinGame:
    """Test join game endpoint."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_join_game_success(self, client):
        """Test successful game join."""
        # Register user first
        client.post("/users/persistent_register", json={"telegram_id": "test123", "full_name": "Test User", "bot_secret": BOT_SECRET})
        
        # Create game
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = int(game_resp.json()["game_id"])
        
        # Join game
        resp = client.post(f"/games/{game_id}/join", json={"telegram_id": "test123", "bot_secret": BOT_SECRET, "game_id": game_id, "power": "FRANCE"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "player_id" in data
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_join_game_already_joined(self, client):
        """Test joining game when already joined."""
        # Register user
        client.post("/users/persistent_register", json={"telegram_id": "test456", "full_name": "Test User", "bot_secret": BOT_SECRET})
        
        # Create game
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = int(game_resp.json()["game_id"])
        
        # Join first time
        resp1 = client.post(f"/games/{game_id}/join", json={"telegram_id": "test456", "bot_secret": BOT_SECRET, "game_id": game_id, "power": "FRANCE"})
        assert resp1.status_code == 200

        # Join again
        resp2 = client.post(f"/games/{game_id}/join", json={"telegram_id": "test456", "bot_secret": BOT_SECRET, "game_id": game_id, "power": "FRANCE"})
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "already_joined"


@pytest.mark.unit
class TestProcessTurn:
    """Test process turn endpoint."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_process_turn_success(self, client):
        """Test successful turn processing.

        The bare (no-auth) call this test used to make encoded the E1d bug --
        the ``client`` fixture bypasses ``require_bot_or_user`` entirely, so an
        unauthenticated request was indistinguishable here from an authorized
        one. Now that ``process_turn`` checks bot-secret/admin/membership on its
        own (independent of that bypassed dependency), the call must carry a
        real credential -- the bot-secret path, exercised elsewhere too (e.g.
        the deadline scheduler and Telegram bot).
        """
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        resp = client.post(f"/games/{game_id}/process_turn", headers={"X-Bot-Secret": BOT_SECRET})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert (data["phase"], data["game_status"]) == ("F1901M", "ACTIVE")
        assert len(data["resolution"]["results"]) == 22  # every opening unit held

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_process_turn_not_found(self, client):
        """Test processing turn for non-existent game."""
        resp = client.post("/games/nonexistent/process_turn", headers={"X-Bot-Secret": BOT_SECRET})
        assert resp.status_code == 404

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_process_turn_unauthenticated_is_forbidden(self, client):
        """No Bearer, no X-Bot-Secret, no X-Admin-Token -> 403, not 200.

        This is the E1d regression test: any caller (not just "any authenticated
        user") used to be able to end a turn early. The ``client`` fixture only
        bypasses ``require_bot_or_user``; process_turn's own membership check is
        independent of it and must still reject a bare call.
        """
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        resp = client.post(f"/games/{game_id}/process_turn")
        assert resp.status_code == 403

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_process_turn_non_member_forbidden(self, client):
        """A logged-in user who holds no power in this game gets 403, even
        though they are a perfectly valid, authenticated user elsewhere."""
        import time as _time
        email = f"nonmember_{int(_time.time() * 1000)}@example.com"
        reg = client.post("/auth/register", json={"email": email, "password": "testpass123"})
        assert reg.status_code == 200, reg.text
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]

        resp = client.post(f"/games/{game_id}/process_turn", headers=headers)
        assert resp.status_code == 403

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_process_turn_member_allowed(self, client):
        """The game's creator, seated in it, may process its turn -- the fix must
        not lock out legitimate players. (Since v2.7.107 only the creator may;
        a seated non-creator is refused -- see test_telegram_flows_api.py.)"""
        import time as _time
        email = f"member_{int(_time.time() * 1000)}@example.com"
        reg = client.post("/auth/register", json={"email": email, "password": "testpass123"})
        assert reg.status_code == 200, reg.text
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=headers)
        game_id = game_resp.json()["game_id"]
        join_resp = client.post(
            f"/games/{game_id}/join",
            json={"game_id": int(game_id), "power": "AUSTRIA"},
            headers=headers,
        )
        assert join_resp.status_code == 200, join_resp.text

        resp = client.post(f"/games/{game_id}/process_turn", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


@pytest.mark.unit
class TestLastResolution:
    """Test GET /games/{game_id}/last_resolution (E1b)."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_last_resolution_not_found(self, client):
        resp = client.get("/games/nonexistent/last_resolution")
        assert resp.status_code == 404

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_last_resolution_before_any_turn_processed(self, client):
        """A real game that has never had a turn processed -> empty results,
        not 404 (the game does exist)."""
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        resp = client.get(f"/games/{game_id}/last_resolution")
        assert resp.status_code == 200
        assert resp.json() == {"results": []}

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_last_resolution_after_process_turn_matches_inline_resolution(self, client):
        """The persisted resolution fetched afterwards must match what
        process_turn returned inline (E1a), decorated with power/order_str."""
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        process_resp = client.post(f"/games/{game_id}/process_turn", headers={"X-Bot-Secret": BOT_SECRET})
        assert process_resp.status_code == 200
        inline_resolution = process_resp.json()["resolution"]

        resp = client.get(f"/games/{game_id}/last_resolution")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == len(inline_resolution["results"])
        assert len(data["results"]) > 0  # 22 opening holds

        for entry in data["results"]:
            assert "power" in entry
            assert "order_str" in entry
            assert "order" in entry
            assert "result" in entry
            assert entry["power"] == entry["order"]["power"]

        # Every submitted power appears among the results (all holds at the
        # opening position, since no orders were submitted).
        powers = {r["power"] for r in data["results"]}
        assert powers == {"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"}
        assert all(r["result"] == "OK" for r in data["results"])

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_last_resolution_fleet_order_renders_with_f_not_a(self, client):
        """Regression: a fleet's order_str must render "F", never "A".

        RUSSIA's opening fleet sits at SEV and TURKEY's at ANK -- both
        non-split-coast provinces, exactly the case ``format_order``'s
        docstring warns about when no ``kind_by_province`` map is supplied.
        No orders are submitted, so process_turn adjudicates the opening
        position's implicit holds for all 22 units. Before the fix,
        ``GameService.last_resolution_view`` called ``format_order(order)``
        with no board map, so these printed as "A SEV H" / "A ANK H".
        """
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        process_resp = client.post(f"/games/{game_id}/process_turn", headers={"X-Bot-Secret": BOT_SECRET})
        assert process_resp.status_code == 200

        resp = client.get(f"/games/{game_id}/last_resolution")
        assert resp.status_code == 200
        results = resp.json()["results"]

        by_unit = {r["order"]["unit"]: r["order_str"] for r in results if "unit" in r["order"]}
        assert by_unit["SEV"].startswith("F "), by_unit["SEV"]
        assert by_unit["ANK"].startswith("F "), by_unit["ANK"]
        # Sanity: an army at a non-coast province still renders as an army.
        assert by_unit["PAR"].startswith("A "), by_unit["PAR"]

        # The same must hold for what process_turn returns inline (no reload
        # needed) -- it's the same decorated resolution, persisted verbatim.
        inline_results = process_resp.json()["resolution"]["results"]
        inline_by_unit = {
            r["order"]["unit"]: r["order_str"] for r in inline_results if "unit" in r["order"]
        }
        assert inline_by_unit["SEV"].startswith("F "), inline_by_unit["SEV"]
        assert inline_by_unit["ANK"].startswith("F "), inline_by_unit["ANK"]


@pytest.mark.unit
class TestDeadlineEndpoints:
    """Test deadline management endpoints."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_deadline(self, client):
        """Test getting game deadline."""
        # Create game
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        
        # Get deadline
        resp = client.get(f"/games/{game_id}/deadline")
        assert resp.status_code == 200
        data = resp.json()
        assert (data["deadline"], data["pending_proposal"]) == (None, None)
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_set_deadline(self, client):
        """Test setting game deadline -- by a player in the game (Track T)."""
        # Create game
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        tg = f"dl_{int(datetime.now().timestamp() * 1000000)}"
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": tg, "full_name": "Deadline"})
        join = client.post(f"/games/{game_id}/join", json={"telegram_id": tg, "bot_secret": BOT_SECRET, "power": "FRANCE"})
        assert join.status_code == 200, join.text
        
        # Set deadline
        future = (datetime.now(timezone.utc) + timedelta(hours=24)).replace(microsecond=0)
        resp = client.post(f"/games/{game_id}/deadline", json={"deadline": future.isoformat(), "telegram_id": tg, "bot_secret": BOT_SECRET})
        assert resp.status_code == 200, resp.text
        stored = datetime.fromisoformat(client.get(f"/games/{game_id}/deadline").json()["deadline"])
        assert stored.replace(tzinfo=timezone.utc) == future  # stored as naive UTC


@pytest.mark.unit
class TestGameHistory:
    """Test game history endpoints."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_game_history(self, client):
        """Test getting game history."""
        game_id = client.post("/games/create", json={"map_name": "standard"}).json()["game_id"]
        assert client.get(f"/games/{game_id}/history/1").status_code == 404  # nothing played yet
        tg = f"hist_{int(datetime.now().timestamp() * 1000000)}"
        client.post("/users/persistent_register", json={"bot_secret": BOT_SECRET, "telegram_id": tg, "full_name": "History"})
        client.post(f"/games/{game_id}/join", json={"telegram_id": tg, "bot_secret": BOT_SECRET, "power": "FRANCE"})
        ordered = client.post("/games/set_orders", json={"game_id": game_id, "power": "FRANCE", "orders": ["A PAR - BUR"],
                                                         "telegram_id": tg, "bot_secret": BOT_SECRET})
        assert ordered.status_code == 200, ordered.text
        assert client.post(f"/games/{game_id}/process_turn", headers={"X-Bot-Secret": BOT_SECRET}).status_code == 200

        resp = client.get(f"/games/{game_id}/history/1")
        assert resp.status_code == 200, resp.text
        turn = resp.json()
        assert turn["phase_code"] == "F1901M"
        assert turn["orders"]["FRANCE"] == ["A PAR - BUR"]
        assert {"A BUR"} <= {f"{u['kind']} {u['location']}" for u in turn["state"]["units"] if u["power"] == "FRANCE"}


@pytest.mark.unit
class TestGameSnapshots:
    """Test game snapshot endpoints."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_save_snapshot(self, client):
        """Test saving game snapshot."""
        # Create game
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        
        resp = client.post(f"/games/{game_id}/snapshot")
        assert resp.status_code == 200, resp.text
        assert resp.json()["turn"] == 0
        listed = client.get(f"/games/{game_id}/snapshots").json()["snapshots"]
        assert [(s["id"], s["turn"], s["phase_code"]) for s in listed] == [(resp.json()["snapshot_id"], 0, "S1901M")]
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_snapshots(self, client):
        """Test getting game snapshots."""
        # Create game
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        
        assert client.get(f"/games/{game_id}/snapshots").json()["snapshots"] == []
        assert client.get("/games/nonexistent/snapshots").status_code == 404


@pytest.mark.unit
class TestLegalOrders:
    """Test legal orders endpoints (power-level and per-unit)."""

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_legal_orders_success(self, client):
        """Per-unit route returns real, non-empty content for an army at Paris."""
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        client.post("/games/add_player", json={"game_id": game_id, "power": "FRANCE"})
        resp = client.get(f"/games/{game_id}/legal_orders/FRANCE/A PAR")
        assert resp.status_code == 200
        data = resp.json()
        assert "orders" in data
        assert isinstance(data["orders"], list)
        assert "A PAR H" in data["orders"]
        assert all(o.startswith("A PAR") for o in data["orders"])

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_legal_orders_for_power(self, client):
        """New power-level route: phase-aware dict with units/orders_by_unit/orders."""
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        client.post("/games/add_player", json={"game_id": game_id, "power": "FRANCE"})
        resp = client.get(f"/games/{game_id}/legal_orders/FRANCE")
        assert resp.status_code == 200
        data = resp.json()
        assert data["power"] == "FRANCE"
        assert data["phase_type"] == "MOVEMENT"
        assert "F BRE" in data["orders_by_unit"]
        assert "A PAR" in data["orders_by_unit"]
        assert all(o.startswith("F BRE") for o in data["orders_by_unit"]["F BRE"])
        assert "F BRE H" in data["orders"]

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_legal_orders_for_power_game_not_found(self, client):
        """Power-level route 404s for an unknown game."""
        resp = client.get("/games/nonexistent/legal_orders/FRANCE")
        assert resp.status_code == 404

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_legal_orders_unknown_unit_returns_empty_not_404(self, client):
        """A unit that doesn't exist (or belongs to another power) is a 200 with

        an empty orders list -- never a 404, which would trip the frontend's
        fallback path.
        """
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        client.post("/games/add_player", json={"game_id": game_id, "power": "FRANCE"})
        # No unit for FRANCE at Munich (that's a German home center).
        resp = client.get(f"/games/{game_id}/legal_orders/FRANCE/A MUN")
        assert resp.status_code == 200
        assert resp.json() == {"orders": []}

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_legal_orders_bare_province_falls_back_to_coast(self, client):
        """A bare 'F STP' finds a unit actually standing on 'STP/SC'."""
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        client.post("/games/add_player", json={"game_id": game_id, "power": "RUSSIA"})
        resp = client.get(f"/games/{game_id}/legal_orders/RUSSIA/F STP")
        assert resp.status_code == 200
        data = resp.json()
        assert data["orders"], "expected the STP/SC fleet's orders via province fallback"
        assert all(o.startswith("F STP/SC") for o in data["orders"])

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_legal_orders_invalid_format(self, client):
        """Test getting legal orders with invalid unit format."""
        game_resp = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"})
        game_id = game_resp.json()["game_id"]
        resp = client.get(f"/games/{game_id}/legal_orders/FRANCE/invalid")
        assert resp.status_code == 400

    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_get_legal_orders_game_not_found(self, client):
        """Test getting legal orders for non-existent game."""
        resp = client.get("/games/nonexistent/legal_orders/FRANCE/A PAR")
        assert resp.status_code == 404

