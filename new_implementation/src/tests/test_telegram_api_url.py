import importlib
import os
import sys
import types

import pytest


@pytest.mark.unit
def test_telegram_bot_reads_api_url_from_env(monkeypatch):
    # Ensure fresh import
    if 'server.telegram_bot' in sys.modules:
        del sys.modules['server.telegram_bot']
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', '12345:abcdefghijklmnopqrstuvwxyz')
    monkeypatch.setenv('DIPLOMACY_API_URL', 'https://api.example.com')

    mod = importlib.import_module('server.telegram_bot')
    assert getattr(mod, 'API_URL', None) == 'https://api.example.com'
