"""A ``TestClient`` for tests that act as the Telegram bot.

Many tests build the bot's request bodies with a shared helper that puts the bot
secret next to the ``telegram_id`` (``{"telegram_id": tg, "bot_secret": SECRET}``).
The API reads the secret only from the ``X-Bot-Secret`` header (4.0.0 removed the
body field), so this client moves a ``bot_secret`` found in a JSON body into that
header before sending, unless the request already carries the header, as the bot
itself does. A test about the body field itself uses a plain ``TestClient``
(``tests/test_bot_secret_header.py``).
"""
from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


class BotTestClient(TestClient):
    def request(self, method: str, url: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        body = kwargs.get("json")
        if isinstance(body, dict) and "bot_secret" in body:
            body = dict(body)
            secret = body.pop("bot_secret")
            headers = dict(kwargs.get("headers") or {})
            if not any(k.lower() == "x-bot-secret" for k in headers) and secret is not None:
                headers["X-Bot-Secret"] = secret
            kwargs["json"], kwargs["headers"] = body, headers
        return super().request(method, url, **kwargs)
