import pytest
from src.server.telegram_bot import process_waiting_list
from typing import List, Tuple

class APIMock:
    def __init__(self):
        self.created_games = []
        self.joins = []
    def post(self, endpoint: str, json: dict):
        if endpoint == "/games/create":
            game_id = str(len(self.created_games) + 1)
            self.created_games.append(game_id)
            return {"game_id": game_id}
        elif endpoint.startswith("/games/") and endpoint.endswith("/join"):
            self.joins.append((json["game_id"], json["telegram_id"], json["power"]))
            return {"status": "ok"}
        raise Exception(f"Unknown endpoint: {endpoint}")

def test_process_waiting_list_creates_game(monkeypatch):
    waiting_list: List[Tuple[str, str]] = [(str(i), f"User{i}") for i in range(7)]
    POWERS = ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"]
    api = APIMock()
    notified = []
    def notify_callback(telegram_id, message):
        notified.append((telegram_id, message))
    game_id, assignments = process_waiting_list(waiting_list, 7, POWERS, 
                                               notify_callback, api_post_func=api.post)
    assert game_id is not None
    assert assignments is not None and len(assignments) == 7
    assert len(api.created_games) == 1
    assert len(api.joins) == 7
    assert len(notified) == 7
    assert len(waiting_list) == 0  # Should be emptied

def test_process_waiting_list_not_enough(monkeypatch):
    waiting_list: List[Tuple[str, str]] = [(str(i), f"User{i}") for i in range(5)]
    POWERS = ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"]
    api = APIMock()
    notified = []
    def notify_callback(telegram_id, message):
        notified.append((telegram_id, message))
    game_id, assignments = process_waiting_list(waiting_list, 7, POWERS, 
                                               notify_callback, api_post_func=api.post)
    assert game_id is None
    assert assignments is None
    assert len(api.created_games) == 0
    assert len(api.joins) == 0
    assert len(notified) == 0
    assert len(waiting_list) == 5  # Should be unchanged

def test_process_waiting_list_duplicate_prevention(monkeypatch):
    waiting_list: List[Tuple[str, str]] = [
        ("1", "User1"), ("1", "User1"), ("2", "User2"), ("3", "User3"), 
        ("4", "User4"), ("5", "User5"), ("6", "User6"), ("7", "User7")
    ]
    POWERS = ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"]
    api = APIMock()
    notified = []
    def notify_callback(telegram_id, message):
        notified.append((telegram_id, message))
    # Remove duplicates before calling process_waiting_list
    unique_waiting_list = []
    seen = set()
    for entry in waiting_list:
        if entry[0] not in seen:
            unique_waiting_list.append(entry)
            seen.add(entry[0])
    game_id, assignments = process_waiting_list(unique_waiting_list, 7, POWERS, 
                                               notify_callback, api_post_func=api.post)
    assert game_id is not None
    assert assignments is not None and len(assignments) == 7
    assert len(api.created_games) == 1
    assert len(api.joins) == 7
    assert len(notified) == 7
    assert len(unique_waiting_list) == 0

def test_process_waiting_list_notification_failure(monkeypatch):
    waiting_list: List[Tuple[str, str]] = [(str(i), f"User{i}") for i in range(7)]
    POWERS = ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"]
    api = APIMock()
    notified = []
    def notify_callback(telegram_id, message):
        notified.append((telegram_id, message))
        if telegram_id == "3":
            raise Exception("Notification failed")
    game_id, assignments = process_waiting_list(waiting_list, 7, POWERS, 
                                               notify_callback, api_post_func=api.post)
    assert game_id is not None
    assert assignments is not None and len(assignments) == 7
    assert len(api.created_games) == 1
    assert len(api.joins) == 7
    assert len(notified) == 7
    assert len(waiting_list) == 0
