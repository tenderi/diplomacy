"""
Utility functions for Telegram bot, including Markdown escaping.
"""
from typing import List, Optional, Union

# Legacy Markdown (``parse_mode='Markdown'``, which every caller uses) honours a backslash
# only before these four; anywhere else Telegram shows the backslash itself.
_LEGACY_MARKDOWN_SPECIALS = ('_', '*', '`', '[')


def escape_markdown(text: Union[str, None]) -> Union[str, None]:
    """
    Escape text for a message sent with ``parse_mode='Markdown'`` (legacy mode).

    Only ``_ * ` [`` are escaped: escaping MarkdownV2's wider set (``. - ! ( )`` ...)
    here would print "Ann\\-Marie" for a player called Ann-Marie. Empty or ``None``
    input is returned unchanged, so callers can write ``escape_markdown(x) or 'N/A'``.
    """
    if not text:
        return text
    for char in _LEGACY_MARKDOWN_SPECIALS:
        text = text.replace(char, f'\\{char}')
    return text


_SEASON_NAMES = {"S": "Spring", "F": "Fall", "W": "Winter"}
_PHASE_NAMES = {"M": "movement", "R": "retreats", "A": "builds"}


def phase_label(phase_code: object) -> str:
    """``"S1901M"`` -> ``"Spring 1901 movement"``; anything else is returned as text.

    The bot cannot import the server's helper of the same name (it ships with
    ``requests`` and python-telegram-bot only)."""
    code = str(phase_code)
    season, year, kind = code[:1], code[1:-1], code[-1:]
    if season in _SEASON_NAMES and kind in _PHASE_NAMES and year.isdigit():
        return f"{_SEASON_NAMES[season]} {year} {_PHASE_NAMES[kind]}"
    return code


def phase_text(phase_code: object) -> str:
    """The label with the code in brackets, for a player who types it: ``Fall 1903 movement (F1903M)``."""
    label = phase_label(phase_code)
    return label if label == str(phase_code) else f"{label} ({phase_code})"


def ending_outcome(how: Optional[str], winners: List[str]) -> str:
    """How a game that a power leaving play ended reads ("a draw shared by
    ENGLAND, GERMANY"): ``how`` is the API's (``GameService.ending``)."""
    if how == "draw":
        return f"a draw shared by {', '.join(winners)}"
    if how == "only_dummies":
        return "only civil-disorder powers are left, so nobody wins"
    if winners:
        return f"{winners[0]} is the last power standing and wins"
    return "no power is left, so nobody wins"


def game_end_line(view: dict) -> Optional[str]:
    """``"Game ended: won by France"`` for a finished game's state view, else ``None``."""
    if str(view.get("status", "")).upper() != "COMPLETED":
        return None
    winners = [str(w).title() for w in (view.get("winners") or [])]
    if not winners:
        return "Game ended with no winner"
    if len(winners) == 1:
        return f"Game ended: won by {winners[0]}"
    return f"Game ended in a draw shared by {', '.join(winners)}"


def game_over_note(game_id: object) -> str:
    """The refusal for an action on a finished game."""
    return f"Game {game_id} has ended."
