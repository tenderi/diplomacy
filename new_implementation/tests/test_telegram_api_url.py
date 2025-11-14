import importlib
import os
import sys
import types

import pytest


@pytest.mark.unit
def test_telegram_bot_reads_api_url_from_env(monkeypatch):
    # Ensure fresh import
    modules_to_clear = [
        'server.telegram_bot.config',
        'server.telegram_bot.api_client',
    ]
    for mod_name in modules_to_clear:
        if mod_name in sys.modules:
            del sys.modules[mod_name]
    
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', '12345:abcdefghijklmnopqrstuvwxyz')
    monkeypatch.setenv('DIPLOMACY_API_URL', 'https://api.example.com')

    mod = importlib.import_module('server.telegram_bot.config')
    assert getattr(mod, 'API_URL', None) == 'https://api.example.com'
