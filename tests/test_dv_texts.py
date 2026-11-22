"""DV2: the deadline-left text."""
from datetime import datetime, timedelta

import pytest

from server.api import shared as api_shared

NOW = datetime(2026, 11, 22, 12, 0, 0)


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (timedelta(hours=6, seconds=-20), "6h"),
        (timedelta(days=1, hours=2), "1d 2h"),
        (timedelta(minutes=45), "45m"),
        (timedelta(hours=2, minutes=30), "2h 30m"),
        (timedelta(days=2), "2d"),
        (timedelta(seconds=10), "under a minute"),
    ],
)
def test_time_left_text(delta: timedelta, expected: str) -> None:
    assert api_shared.time_left_text(NOW + delta, NOW) == expected
