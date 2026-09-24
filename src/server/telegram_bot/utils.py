"""
Utility functions for Telegram bot, including Markdown escaping.
"""
from typing import Union

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
