# -*- coding: utf-8 -*-
import os
import pytest

# FastAPI test client
try:
	from fastapi.testclient import TestClient
	from server.api import app
except Exception:
	pytest.skip("FastAPI app not importable; skipping integration tests", allow_module_level=True)


@pytest.fixture(scope="module")
def client():
	return TestClient(app)


def _has_db_url() -> bool:
	return bool(os.environ.get("SQLALCHEMY_DATABASE_URL") or os.environ.get("DIPLOMACY_DATABASE_URL"))


@pytest.mark.skipif(not _has_db_url(), reason="Database URL not configured for integration tests")
class TestSpecOnlyFlow:
	def test_create_join_submit_process_state(self, client: TestClient):
		# 1) Create game
		resp = client.post("/games/create", json={"map_name": "standard"})
		assert resp.status_code == 200
		game_id = resp.json()["game_id"]
		assert game_id
		# 2) Register user and join as FRANCE
		telegram_id = "999001"
		reg = client.post("/users/persistent_register", json={"telegram_id": telegram_id, "full_name": "Tester"})
		assert reg.status_code == 200
		join = client.post(f"/games/{game_id}/join", json={"telegram_id": telegram_id, "game_id": int(game_id), "power": "FRANCE"})
		assert join.status_code == 200
		# 3) Submit a simple hold order
		orders = ["A PAR H"]
		set_resp = client.post("/games/set_orders", json={
			"game_id": str(game_id),
			"power": "FRANCE",
			"orders": orders,
			"telegram_id": telegram_id,
		})
		assert set_resp.status_code == 200
		body = set_resp.json()
		assert "results" in body
		assert any(r.get("success") for r in body["results"])  # at least one order accepted
		# 4) Process turn
		proc = client.post(f"/games/{game_id}/process_turn")
		assert proc.status_code == 200
		# 5) Get state and ensure spec fields exist
		state = client.get(f"/games/{game_id}/state")
		assert state.status_code == 200
		payload = state.json()
		for key in ("game_id", "map_name", "current_turn", "current_year", "current_season", "current_phase", "phase_code", "status", "powers", "orders"):
			assert key in payload
		assert isinstance(payload["powers"], dict)
