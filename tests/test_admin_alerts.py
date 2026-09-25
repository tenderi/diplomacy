"""Error alerts to the maintainer (``telegram_bot/alerting.py``) and the API's
5xx logging (``api/error_log.py``): an error either process logs reaches the
maintainer's Telegram, throttled, and a 500 a route returns is logged at all."""
from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from server.api.error_log import ServerErrorLogMiddleware
from server.telegram_bot import app as bot_app
from server.telegram_bot.alerting import MAX_ALERT_CHARS, AdminAlertHandler, admin_telegram_id

pytestmark = pytest.mark.unit


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _logger(handler: logging.Handler, name: str = "diplomacy.test.alerts") -> logging.Logger:
    log = logging.getLogger(name)
    log.handlers = [handler]
    log.propagate = False
    log.setLevel(logging.DEBUG)
    return log


def _handler(sent: list[str], clock: Clock, **kw: object) -> AdminAlertHandler:
    return AdminAlertHandler(sent.append, source="Test", clock=clock, **kw)  # type: ignore[arg-type]


def test_an_error_is_sent_with_its_exception_and_a_warning_is_not() -> None:
    sent: list[str] = []
    log = _logger(_handler(sent, Clock()))
    log.warning("just a warning")
    try:
        raise KeyError("FRANCE")
    except KeyError:
        log.exception("Failed to process game %s", 12)
    assert sent == ["⚠️ Test error\ndiplomacy.test.alerts: Failed to process game 12\nKeyError: 'FRANCE'"]


def test_one_kind_alerts_once_per_window_then_says_how_many_were_held_back() -> None:
    sent: list[str] = []
    clock = Clock()
    log = _logger(_handler(sent, clock, per_key_seconds=900))
    log.error("Failed to snapshot game 12")
    log.error("Failed to snapshot game 13")  # same kind: digits do not count
    log.error("Something else broke")  # another kind is not held back
    assert len(sent) == 2
    clock.now = 901
    log.error("Failed to snapshot game 14")
    assert sent[-1].endswith("Failed to snapshot game 14\n(+1 more like this since the last alert)")


def test_no_more_than_the_hourly_cap_in_all() -> None:
    sent: list[str] = []
    clock = Clock()
    log = _logger(_handler(sent, clock, max_per_hour=3))
    for kind in "abcde":
        log.error("broken %s", kind)
    assert len(sent) == 3
    clock.now = 3600
    log.error("broken f")
    assert len(sent) == 4


def test_sending_never_raises_into_the_caller_or_alerts_about_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(logging, "raiseExceptions", False)
    calls: list[str] = []

    def send(text: str) -> None:
        calls.append(text)
        log.error("database down while alerting")  # would recurse without the guard
        raise RuntimeError("database down")

    log = _logger(AdminAlertHandler(send, source="Test", clock=Clock()))
    log.error("first")  # must not raise
    assert len(calls) == 1


def test_a_long_message_is_cut_to_fit_one_telegram_message() -> None:
    sent: list[str] = []
    _logger(_handler(sent, Clock())).error("x" * 5000)
    assert len(sent[0]) == MAX_ALERT_CHARS and sent[0].endswith("…")


@pytest.mark.parametrize(("raw", "expected"), [("12345", 12345), (" 42 ", 42), ("", None), (None, None), ("me", None)])
def test_admin_telegram_id_is_a_number_or_nothing(raw: str | None, expected: int | None) -> None:
    assert admin_telegram_id(raw) == expected


# -- the API: every 5xx is logged --------------------------------------------


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ServerErrorLogMiddleware)

    @app.get("/caught")
    def caught() -> None:
        raise HTTPException(status_code=500, detail="boom")

    @app.get("/uncaught/{game_id}")
    def uncaught(game_id: int) -> None:
        raise ValueError(f"bad game {game_id}")

    @app.get("/missing")
    def missing() -> None:
        raise HTTPException(status_code=404, detail="nope")

    return app


def test_a_500_a_route_raises_on_purpose_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="diplomacy.server.errors"):
        assert client.get("/caught").status_code == 500
        assert client.get("/missing").status_code == 404
    assert [r.getMessage() for r in caplog.records] == ["HTTP 500 on GET /caught"]


def test_an_uncaught_exception_is_logged_with_its_traceback(caplog: pytest.LogCaptureFixture) -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="diplomacy.server.errors"):
        assert client.get("/uncaught/7").status_code == 500
    [record] = caplog.records
    assert record.getMessage() == "Unhandled error on GET /uncaught/7"
    assert record.exc_info is not None and str(record.exc_info[1]) == "bad game 7"


# -- the bot: sends its own alerts, and names what failed ---------------------


def test_the_bot_sends_its_alerts_straight_to_the_maintainer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot_app, "ADMIN_TELEGRAM_ID", 999)
    telegram_app = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    root = logging.getLogger()

    async def scenario() -> None:
        handler = bot_app.install_bot_alerts(telegram_app)  # type: ignore[arg-type]
        assert handler is not None
        try:
            logging.getLogger("diplomacy.telegram_bot.notifications").error("Outbox poll failed")
            for _ in range(3):
                await asyncio.sleep(0)
        finally:
            root.removeHandler(handler)

    asyncio.run(scenario())
    telegram_app.bot.send_message.assert_awaited_once_with(
        chat_id=999, text="⚠️ Diplomacy bot error\ndiplomacy.telegram_bot.notifications: Outbox poll failed"
    )


def test_no_admin_id_means_no_bot_alerts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot_app, "ADMIN_TELEGRAM_ID", None)
    assert bot_app.install_bot_alerts(Mock()) is None


def test_a_failing_handler_is_logged_with_the_command_not_the_message(caplog: pytest.LogCaptureFixture) -> None:
    update = Mock(spec=bot_app.Update)
    update.callback_query = None
    update.effective_message = Mock(text="/feedback my secret plan")
    context = Mock(error=RuntimeError("boom"))
    with caplog.at_level(logging.ERROR, logger="diplomacy.telegram_bot.main"):
        asyncio.run(bot_app._on_handler_error(update, context))
    [record] = caplog.records
    assert record.getMessage() == "Error handling /feedback"
    assert record.exc_info is not None and record.exc_info[1] is context.error


def test_the_api_process_still_prints_its_errors_once_with_alerts_on() -> None:
    """A root handler switches off Python's last-resort output, which is how most
    API loggers reached the journal. Run as production does -- a fresh process
    with no logging configured -- and check an error still prints, exactly once
    (the CLI ``Server`` once added a second handler on ``diplomacy.server``)."""
    import os
    import subprocess
    import sys

    script = (
        "import logging\n"
        "from server.api import shared\n"
        "shared.ADMIN_TELEGRAM_ID = 1\n"
        "shared.db_service.enqueue_bot_notification = lambda *a, **k: 1\n"
        "assert shared.install_admin_alerts() is not None\n"
        "logging.getLogger('diplomacy.server.errors').error('HTTP 500 on GET /probe')\n"
        "logging.getLogger('persistence.probe').warning('a warning from elsewhere')\n"
    )
    env = {**os.environ, "PYTHONPATH": "src", "DIPLOMACY_BOT_SECRET": "x"}
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stderr.count("HTTP 500 on GET /probe") == 1, result.stderr
    assert result.stderr.count("a warning from elsewhere") == 1, result.stderr
