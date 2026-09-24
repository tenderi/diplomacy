"""The bot's configuration: the token (read verbatim, never logged) and the API URL."""

from unittest.mock import patch

from server.telegram_bot.config import get_telegram_token


class TestToken:

    def test_get_telegram_token_from_env(self):
        """Test getting Telegram token from environment."""
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': 'test_token'}):
            result = get_telegram_token()
            assert result == 'test_token'
    
    def test_get_telegram_token_is_taken_verbatim(self):
        """No JSON unwrapping (that was the AWS Secrets Manager form, gone with
        the AWS layout); surrounding whitespace from a hand-edited .env is dropped."""
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': ' 123:abc \n'}):
            assert get_telegram_token() == '123:abc'
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': '{"TELEGRAM_BOT_TOKEN": "x"}'}):
            assert get_telegram_token() == '{"TELEGRAM_BOT_TOKEN": "x"}'

    def test_importing_config_never_logs_the_token(self, caplog):
        import importlib
        import logging as _logging
        from server.telegram_bot import config as cfg
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': '999999:SECRET-TOKEN-VALUE'}), caplog.at_level(_logging.DEBUG):
            importlib.reload(cfg)
        assert 'SECRET-TOKEN-VALUE' not in caplog.text
        assert '999999' not in caplog.text
    
    def test_get_telegram_token_empty(self):
        """Test getting Telegram token when not set."""
        with patch.dict('os.environ', {}, clear=True):
            result = get_telegram_token()
            assert result == ''


# `TestProcessWaitingList` was removed with G5. It tested
# `telegram_bot.games.process_waiting_list`, the bot-side queue-filling function
# that has moved server-side (the queue is now a Postgres table owned by
# `/waiting_list/*`, so it survives the restart that a deploy performs and its
# entries are claimed atomically). Coverage lives in `tests/test_waiting_list.py`
# and `tests/test_telegram_waiting_list.py`.


def test_bot_silences_httpx_so_the_token_never_reaches_the_log():
    """httpx logs every request URL at INFO, and python-telegram-bot's base URL
    embeds the token (``https://api.telegram.org/bot<token>/...``). The fix
    (3b6452e) lived only on the deployed ``vps-split`` branch and was missing
    from main; the first deploy-on-merge would have brought the leak back.
    A source check because ``main()`` starts the real polling loop."""
    from pathlib import Path
    src = (Path(__file__).parent.parent / "src" / "server" / "telegram_bot" / "app.py").read_text()
    basic = src.index("logging.basicConfig(")
    silence = src.index('logging.getLogger("httpx").setLevel(logging.WARNING)')
    assert silence > basic, "httpx must be silenced *after* basicConfig(force=True), which resets levels"


def test_the_api_url_comes_from_the_environment(monkeypatch):
    import importlib
    from server.telegram_bot import config as cfg
    monkeypatch.setenv("DIPLOMACY_API_URL", "https://api.example.com")
    assert importlib.reload(cfg).API_URL == "https://api.example.com"
    monkeypatch.delenv("DIPLOMACY_API_URL")
    importlib.reload(cfg)
