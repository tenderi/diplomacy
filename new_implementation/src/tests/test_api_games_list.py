import os
import pytest

from fastapi.testclient import TestClient

os.environ.setdefault("DIPLOMACY_MAP_PATH", "maps/standard.svg")


@pytest.mark.unit
def test_list_games_and_state_import_ok():
    # Import app with proper PYTHONPATH during pytest via pytest.ini
    from server.api import app

    client = TestClient(app)

    # Create a game
    r_create = client.post("/games/create", json={"map_name": "standard"})
    assert r_create.status_code == 200
    game_id = r_create.json()["game_id"]

    # List games
    r_list = client.get("/games")
    assert r_list.status_code == 200
    games = r_list.json()["games"]
    assert any(str(g["id"]) == str(game_id) for g in games)

    # Fetch state
    r_state = client.get(f"/games/{game_id}/state")
    assert r_state.status_code == 200
    body = r_state.json()
    for key in ["game_id", "current_year", "current_phase", "current_turn", "powers", "units", "orders", "supply_centers", "status", "phase_code"]:
        assert key in body


