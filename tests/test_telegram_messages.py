"""``escape_markdown``: text from players (names, messages, channel titles) goes out with
``parse_mode='Markdown'`` -- the legacy mode, whose escaping rules are narrower than
MarkdownV2's."""
import pytest
from telegram.helpers import escape_markdown as ptb_escape_markdown

from server.telegram_bot.utils import escape_markdown

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "escaped"),
    [
        ("Al_ice*", "Al\\_ice\\*"),
        ("`code`", "\\`code\\`"),
        ("[link](evil)", "\\[link](evil)"),  # an unopened "[" is enough to stop the link
        ("Ann-Marie O.K.!", "Ann-Marie O.K.!"),  # no stray backslashes a player would see
        ("café 🎬 #1 (+2) = {3} | 4 > 5 ~", "café 🎬 #1 (+2) = {3} | 4 > 5 ~"),
    ],
)
def test_escapes_exactly_what_legacy_markdown_treats_as_markup(raw: str, escaped: str) -> None:
    assert escape_markdown(raw) == escaped


@pytest.mark.parametrize("raw", ["Al_ice*", "a [b] `c` *d* _e_", "Ann-Marie O.K.!", "\\_ already"])
def test_matches_python_telegram_bots_own_legacy_escaper(raw: str) -> None:
    assert escape_markdown(raw) == ptb_escape_markdown(raw, version=1)


@pytest.mark.parametrize("empty", ["", None])
def test_empty_passes_through_so_callers_can_fall_back(empty: str | None) -> None:
    assert (escape_markdown(empty) or "N/A") == "N/A"
