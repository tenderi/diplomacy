# -*- coding: utf-8 -*-
import os
import pytest

# Load environment variables from .env file if it exists
try:
	from dotenv import load_dotenv
	project_root = os.path.join(os.path.dirname(__file__), '..', '..')
	env_path = os.path.join(project_root, '.env')
	if os.path.exists(env_path):
		load_dotenv(env_path)
except ImportError:
	pass

try:
	from fastapi.testclient import TestClient
	from server.api import app
	from server.models import GameStateOut
except Exception:
	pytest.skip("FastAPI app not importable; skipping API tests", allow_module_level=True)


@pytest.fixture(scope="module")
def client():
	return TestClient(app)


def _has_db_url() -> bool:
	"""Check if database URL is configured. Supports .env file loading."""
	return bool(os.environ.get("SQLALCHEMY_DATABASE_URL") or os.environ.get("DIPLOMACY_DATABASE_URL"))


@pytest.mark.skipif(not _has_db_url(), reason="Database URL not configured. Set SQLALCHEMY_DATABASE_URL or DIPLOMACY_DATABASE_URL environment variable, or create a .env file in the project root.")
class TestApiSpecShapes:
	def test_games_list_and_state_shape(self, client: TestClient):
		# Ensure list endpoint works and returns structure
		lst = client.get("/games")
		assert lst.status_code == 200
		data = lst.json()
		assert "games" in data
		# If there is at least one game, query its state shape
		games = data.get("games", [])
		if games:
			gid = str(games[0]["id"])
			state = client.get(f"/games/{gid}/state")
			assert state.status_code == 200
			# Validate minimal required keys
			payload = state.json()
			for key in ("game_id", "map_name", "current_turn", "current_year", "current_season", "current_phase", "phase_code", "status"):
				assert key in payload
