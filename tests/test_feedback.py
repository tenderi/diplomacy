"""Player feedback (``routes/feedback.py``, the bot's ``/feedback``): a report is
stored with the game's phase, reaches the maintainer's Telegram, and cannot be
sent anonymously, empty, oversized or in a flood. Also the API's error alerts,
which travel the same outbox."""
from __future__ import annotations

import asyncio
import logging
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from server.api import ADMIN_TOKEN, app
from server.api import shared as api_shared
from server.api.routes.feedback import MAX_FEEDBACK_CHARS, MAX_FEEDBACK_PER_HOUR
from persistence.database import BotOutboxModel
from server.api.shared import db_service
from server.telegram_bot import feedback as bot_feedback
from tests.conftest import _get_db_url
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

ADMIN = {"X-Admin-Token": ADMIN_TOKEN}
BOT = {"X-Bot-Secret": BOT_SECRET}
ADMIN_CHAT = 424242

db = pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def admin_chat(monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setattr(api_shared, "ADMIN_TELEGRAM_ID", ADMIN_CHAT)
    return ADMIN_CHAT


def _admin_dms() -> list[str]:
    with db_service.session_factory() as session:
        rows = (
            session.query(BotOutboxModel)
            .filter(BotOutboxModel.telegram_id == str(ADMIN_CHAT))
            .order_by(BotOutboxModel.id)
            .all()
        )
        return [row.message for row in rows]


@db
@pytest.mark.unit
def test_a_telegram_report_is_stored_with_the_phase_and_dmed_to_the_maintainer(
    client: TestClient, admin_chat: int
) -> None:
    tg = _telegram_user(client, "Feedback France")
    game_id = str(client.post("/games/create", json=_as(tg, map_name="standard"), headers=BOT).json()["game_id"])
    before = len(_admin_dms())

    resp = client.post("/feedback", json=_as(tg, text="  the map is wrong  ", game_id=game_id, source="telegram"))

    assert resp.status_code == 200, resp.text
    feedback_id = resp.json()["id"]
    [stored] = [f for f in client.get("/admin/feedback", headers=ADMIN).json()["feedback"] if f["id"] == feedback_id]
    assert (stored["text"], stored["game_id"], stored["phase_code"], stored["source"], stored["telegram_id"]) == (
        "the map is wrong", game_id, "S1901M", "telegram", tg,
    )
    assert _admin_dms()[before:] == [
        f"💬 Feedback #{feedback_id} from Feedback France (telegram, game {game_id} (S1901M)):\n\nthe map is wrong"
    ]


@db
@pytest.mark.unit
def test_a_web_report_without_a_game(client: TestClient, admin_chat: int) -> None:
    email = f"fb_{uuid.uuid4().hex[:10]}@example.com"
    token = client.post("/auth/register", json={"email": email, "password": "testpass123"}).json()["access_token"]
    resp = client.post("/feedback", json={"text": "love it"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    [stored] = [f for f in db_service.list_feedback() if f["id"] == resp.json()["id"]]
    assert (stored["source"], stored["game_id"], stored["phase_code"]) == ("web", None, None)


@db
@pytest.mark.unit
def test_no_admin_id_still_stores_the_report_and_dms_nobody(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_shared, "ADMIN_TELEGRAM_ID", None)
    tg = _telegram_user(client, "Quiet Reporter")
    before = _admin_dms()
    resp = client.post("/feedback", json=_as(tg, text="hello"))
    assert resp.status_code == 200
    assert [f["text"] for f in db_service.list_feedback(limit=1)] == ["hello"]
    assert _admin_dms() == before


@db
@pytest.mark.unit
@pytest.mark.parametrize(("text", "detail"), [
    ("   ", "Feedback is empty."),
    ("x" * (MAX_FEEDBACK_CHARS + 1), f"Feedback is limited to {MAX_FEEDBACK_CHARS} characters."),
])
def test_empty_or_oversized_reports_are_refused(client: TestClient, text: str, detail: str) -> None:
    tg = _telegram_user(client, "Terse Reporter")
    resp = client.post("/feedback", json=_as(tg, text=text))
    assert (resp.status_code, resp.json()["detail"]) == (400, detail)


@db
@pytest.mark.unit
def test_a_flood_is_cut_off(client: TestClient) -> None:
    tg = _telegram_user(client, "Chatty Reporter")
    for _ in range(MAX_FEEDBACK_PER_HOUR):
        assert client.post("/feedback", json=_as(tg, text="again")).status_code == 200
    resp = client.post("/feedback", json=_as(tg, text="again"))
    assert resp.status_code == 429


@db
@pytest.mark.unit
def test_reports_need_a_signed_in_player_and_the_list_needs_admin(client: TestClient) -> None:
    assert client.post("/feedback", json={"text": "anon"}).status_code == 401
    assert client.post("/feedback", json={"text": "forged", "telegram_id": "1"}).status_code == 401
    assert client.get("/admin/feedback", headers={"X-Admin-Token": "wrong"}).status_code == 403


@db
@pytest.mark.unit
def test_the_api_dms_its_errors_to_the_maintainer(admin_chat: int) -> None:
    before = len(_admin_dms())
    handler = api_shared.install_admin_alerts()
    assert handler is not None
    try:
        logging.getLogger("diplomacy.scheduler").error("Failed to snapshot game %s", 5)
    finally:
        logging.getLogger().removeHandler(handler)
    assert _admin_dms()[before:] == ["⚠️ Diplomacy API error\ndiplomacy.scheduler: Failed to snapshot game 5"]


# -- the bot's /feedback -------------------------------------------------------


def _command(args: list[str]) -> tuple[Mock, Mock]:
    update = Mock()
    update.effective_user = Mock(id=555)
    update.message = Mock(chat_id=555, reply_text=AsyncMock())
    context = Mock(args=args)
    return update, context


@pytest.mark.unit
def test_bot_feedback_sends_the_text_and_current_game_reliably() -> None:
    update, context = _command(["the", "map", "is", "wrong"])
    delivered = SimpleNamespace(status="delivered", response={"status": "ok", "id": 1}, error=None)
    with patch.object(bot_feedback, "current_game", return_value="12"), \
         patch.object(bot_feedback, "api_post_reliable", return_value=delivered) as post:
        asyncio.run(bot_feedback.feedback(update, context))
    endpoint, body = post.call_args[0]
    assert endpoint == "/feedback"
    assert body == {"telegram_id": "555", "text": "the map is wrong", "source": "telegram", "game_id": "12"}
    update.message.reply_text.assert_awaited_once_with("🙏 Thanks -- your feedback has been sent to the maintainer.")


@pytest.mark.unit
def test_bot_feedback_without_text_explains_itself_and_sends_nothing() -> None:
    update, context = _command([])
    with patch.object(bot_feedback, "api_post_reliable") as post:
        asyncio.run(bot_feedback.feedback(update, context))
    post.assert_not_called()
    update.message.reply_text.assert_awaited_once_with(bot_feedback.USAGE)


@pytest.mark.unit
def test_bot_feedback_refused_by_the_server_says_why() -> None:
    update, context = _command(["again"])
    rejected = SimpleNamespace(status="rejected", response=None, error="That is a lot of feedback in one hour")
    with patch.object(bot_feedback, "current_game", return_value=None), \
         patch.object(bot_feedback, "api_post_reliable", return_value=rejected):
        asyncio.run(bot_feedback.feedback(update, context))
    update.message.reply_text.assert_awaited_once_with(
        "❌ Feedback was not sent: That is a lot of feedback in one hour"
    )
