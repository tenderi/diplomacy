"""
Advanced server tests for multiple concurrent games, isolation, and new commands.
"""
import os
import tempfile
from typing import List
from server.server import Server
from fastapi.testclient import TestClient
from server.api import app


def test_persistent_user_registration_and_multi_game():
    # Clear cache before test to ensure clean state
    from server.response_cache import clear_response_cache
    clear_response_cache()
    
    client = TestClient(app)
    import time as _t
    _email2 = f"multi_game_{int(_t.time()*1000)}@example.com"
    _reg2 = client.post("/auth/register", json={"email": _email2, "password": "testpass123"})
    _auth_headers2 = {"Authorization": f"Bearer {_reg2.json()['access_token']}"}
    # Register user
    resp = client.post("/users/persistent_register", json={"bot_secret": "test_bot_secret_for_tests", "telegram_id": "12345", "full_name": "Test User"})
    assert resp.status_code == 200
    # Create two games
    resp1 = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=_auth_headers2)
    resp2 = client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"}, headers=_auth_headers2)
    game_id1 = resp1.json()["game_id"]
    game_id2 = resp2.json()["game_id"]
    # Join both games as different powers
    resp = client.post(f"/games/{game_id1}/join", json={"telegram_id": "12345", "bot_secret": "test_bot_secret_for_tests", "game_id": int(game_id1), "power": "FRANCE"})
    assert resp.status_code == 200
    resp = client.post(f"/games/{game_id2}/join", json={"telegram_id": "12345", "bot_secret": "test_bot_secret_for_tests", "game_id": int(game_id2), "power": "GERMANY"})
    assert resp.status_code == 200
    # List user games
    resp = client.get("/users/12345/games")
    assert resp.status_code == 200
    games = resp.json()["games"]
    assert any(str(g["game_id"]) == str(game_id1) and g["power"] == "FRANCE" for g in games)
    assert any(str(g["game_id"]) == str(game_id2) and g["power"] == "GERMANY" for g in games)
    # Quit one game
    resp = client.post(f"/games/{game_id1}/quit", json={"bot_secret": "test_bot_secret_for_tests", "telegram_id": "12345", "game_id": int(game_id1)})
    assert resp.status_code == 200
    # List user games again
    resp = client.get("/users/12345/games")
    games = resp.json()["games"]
    assert not any(str(g["game_id"]) == str(game_id1) for g in games)
    assert any(str(g["game_id"]) == str(game_id2) for g in games)
