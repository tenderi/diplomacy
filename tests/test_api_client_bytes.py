"""Tests for ``server.telegram_bot.api_client.api_get_bytes``.

Pure unit test: ``requests.get`` is mocked, no network and no API server needed.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from server.telegram_bot import api_client

pytestmark = pytest.mark.unit


def test_api_get_bytes_returns_raw_content():
    fake_resp = MagicMock()
    fake_resp.content = b"\x89PNG\r\n\x1a\nfakebytes"
    fake_resp.raise_for_status = MagicMock()
    with patch.object(api_client.requests, "get", return_value=fake_resp) as mock_get:
        result = api_client.api_get_bytes("/games/1/map")

    assert result == b"\x89PNG\r\n\x1a\nfakebytes"
    mock_get.assert_called_once()
    called_url = mock_get.call_args.args[0]
    assert called_url == f"{api_client.API_URL}/games/1/map"


def test_api_get_bytes_sends_bot_secret_header(monkeypatch):
    monkeypatch.setattr(api_client, "BOT_SECRET", "shh")
    fake_resp = MagicMock()
    fake_resp.content = b"data"
    fake_resp.raise_for_status = MagicMock()
    with patch.object(api_client.requests, "get", return_value=fake_resp) as mock_get:
        api_client.api_get_bytes("/games/1/map/history/3")

    headers = mock_get.call_args.kwargs["headers"]
    assert headers == {"X-Bot-Secret": "shh"}


def test_api_get_bytes_raises_on_http_error():
    fake_resp = MagicMock()
    fake_resp.raise_for_status.side_effect = api_client.requests.HTTPError("boom")
    with patch.object(api_client.requests, "get", return_value=fake_resp):
        with pytest.raises(api_client.requests.HTTPError):
            api_client.api_get_bytes("/games/1/map")
