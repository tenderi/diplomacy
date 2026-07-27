"""
Entry point for `python -m server.telegram_bot`.

Allows the Telegram bot package to be run directly, e.g.:

    PYTHONPATH=src python -m server.telegram_bot
"""
from server.telegram_bot.app import main

if __name__ == "__main__":
    main()
