"""Nicknames: the only name the system holds for a player.

The system stores no real names. A nickname is optional and chosen by the player
(web registration, ``PATCH /auth/me``, the bot's ``/nickname``); nothing is ever
copied from a Telegram profile. It is unique ignoring case, so nobody can pose as
another player in "X has joined" notices.
"""
from __future__ import annotations

import re
from typing import Any, Optional

MIN_LENGTH = 2
MAX_LENGTH = 24
_ALLOWED = re.compile(r"^[\w .\-]+$")

RULES = f"{MIN_LENGTH}-{MAX_LENGTH} characters: letters, digits, spaces, '.', '_' or '-'"


def normalize_nickname(raw: Optional[str]) -> Optional[str]:
    """``raw`` trimmed with inner whitespace collapsed; ``None`` for blank.

    Raises ``ValueError`` (message fit for the player) if it breaks the rules.
    """
    if raw is None:
        return None
    nickname = " ".join(raw.split())
    if not nickname:
        return None
    if not MIN_LENGTH <= len(nickname) <= MAX_LENGTH or not _ALLOWED.match(nickname):
        raise ValueError(f"A nickname is {RULES}.")
    return nickname


def display_name(user: Any, fallback: str = "A player") -> str:
    """How to call ``user`` in a message: their nickname, or ``fallback``."""
    return (getattr(user, "nickname", None) if user is not None else None) or fallback


def sender_label(player: Any, user: Any) -> str:
    """Who a message is from: the power, with the nickname if there is one --
    ``"FRANCE"`` or ``"FRANCE (Talleyrand)"``."""
    power = str(getattr(player, "power_name", "") or "A player")
    nickname = getattr(user, "nickname", None) if user is not None else None
    return f"{power} ({nickname})" if nickname else power
