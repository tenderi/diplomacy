import os
import pytest

from fastapi.testclient import TestClient

# Load environment variables from .env file if it exists
try:
	from dotenv import load_dotenv
	project_root = os.path.join(os.path.dirname(__file__), '..', '..')
	env_path = os.path.join(project_root, '.env')
	if os.path.exists(env_path):
		load_dotenv(env_path)
except ImportError:
	pass

os.environ.setdefault("DIPLOMACY_MAP_PATH", "maps/standard.svg")


def _has_db_url() -> bool:
	"""Check if database URL is configured. Supports .env file loading."""
	return bool(os.environ.get("SQLALCHEMY_DATABASE_URL") or os.environ.get("DIPLOMACY_DATABASE_URL"))


@pytest.mark.skipif(not _has_db_url(), reason="Database URL not configured. Set SQLALCHEMY_DATABASE_URL or DIPLOMACY_DATABASE_URL environment variable, or create a .env file in the project root.")
@pytest.mark.integration
def test_list_games_and_state_import_ok():
    """Test game creation, listing, and state retrieval via API."""
    # Import app with proper PYTHONPATH during pytest via pytest.ini
    from server.api import app

    client = TestClient(app)

    # Create a game
    r_create = client.post("/games/create", json={"map_name": "standard"})
    if r_create.status_code != 200:
        # Debug: print the actual error
        error_detail = r_create.json().get("detail", "Unknown error") if r_create.status_code != 200 else None
        print(f"Error response: {r_create.status_code} - {error_detail}")
    assert r_create.status_code == 200, f"Expected 200, got {r_create.status_code}: {r_create.json().get('detail', 'Unknown error') if r_create.status_code != 200 else 'OK'}"
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


