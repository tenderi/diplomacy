"""Weekly deadline schedules: "Mon, Wed, Fri at 16:00".

A game may carry a standing schedule (``games.deadline_schedule``). While it
does, every phase's deadline is armed to the next scheduled slot: when the
game fills, when the schedule is set, and after every processed turn. The
functions here are pure (no I/O); ``api.shared`` does the arming.

Stored shape (``to_json``), sorted and de-duplicated::

    {"timezone": "Europe/Helsinki",
     "slots": [{"day": "MON", "time": "16:00"}, {"day": "WED", "time": "16:00"}]}

Slot times are wall-clock times in the schedule's timezone, so "16:00
Helsinki" stays 16:00 across a daylight-saving change.
"""
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any, Optional

import pytz

DAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_DAY_ALIASES = {
    **{d.lower(): i for i, d in enumerate(DAYS)},
    **{full: i for i, full in enumerate(
        ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    )},
    "tues": 1, "wednes": 2, "thur": 3, "thurs": 3,
}
_EVERY_DAY = ("daily", "everyday", "every-day")

# A slot closer than this to the moment a phase is armed is skipped for the one
# after it, so a turn processed at 15:55 is not given a five-minute phase.
MIN_NOTICE = timedelta(hours=1)
MAX_SLOTS = 21


class ScheduleError(ValueError):
    """A schedule that cannot be parsed or stored; the message is player-ready."""


@dataclass(frozen=True, order=True)
class Slot:
    weekday: int  # 0 = Monday, as datetime.weekday()
    at: time


@dataclass(frozen=True)
class DeadlineSchedule:
    slots: tuple[Slot, ...]
    tz_name: str

    def to_json(self) -> dict[str, Any]:
        return {
            "timezone": self.tz_name,
            "slots": [{"day": DAYS[s.weekday], "time": f"{s.at:%H:%M}"} for s in self.slots],
        }

    def describe(self) -> str:
        """``"Mon, Wed, Fri at 16:00 (Europe/Helsinki)"``; days sharing a time are grouped."""
        by_time: dict[time, list[int]] = {}
        for s in self.slots:
            by_time.setdefault(s.at, []).append(s.weekday)
        groups = sorted(by_time.items(), key=lambda kv: (kv[1][0], kv[0]))
        parts = [
            f"{', '.join(_DAY_NAMES[d] for d in days)} at {at:%H:%M}" for at, days in groups
        ]
        return f"{'; '.join(parts)} ({self.tz_name})"

    def next_deadline(self, now: datetime, min_notice: timedelta = MIN_NOTICE) -> datetime:
        """The first slot at least ``min_notice`` after ``now``, as aware UTC.

        ``now`` may be naive (read as UTC) or aware.
        """
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        earliest = now + min_notice
        tz = pytz.timezone(self.tz_name)
        local_today = earliest.astimezone(tz).date()
        # Two weeks always contains a slot at least a week past ``earliest``.
        for offset in range(15):
            day = local_today + timedelta(days=offset)
            for s in self.slots:
                if s.weekday != day.weekday():
                    continue
                candidate = tz.localize(datetime.combine(day, s.at)).astimezone(timezone.utc)
                if candidate >= earliest:
                    return candidate
        raise AssertionError("a non-empty weekly schedule always has a slot within two weeks")


def _check_timezone(name: str) -> str:
    try:
        return str(pytz.timezone(name.strip()).zone)
    except pytz.UnknownTimeZoneError as e:
        raise ScheduleError(
            f"Unknown timezone {name!r}; use an IANA name such as UTC or Europe/Helsinki."
        ) from e


def _parse_time(text: str) -> time:
    try:
        hours, minutes = text.split(":")
        return time(int(hours), int(minutes))
    except ValueError as e:
        raise ScheduleError(f"{text!r} is not a time; write it as HH:MM, e.g. 16:00.") from e


def _parse_day(text: str) -> int:
    day = _DAY_ALIASES.get(text.strip().lower())
    if day is None:
        raise ScheduleError(f"{text!r} is not a day of the week; use Mon, Tue, ... Sun.")
    return day


def _parse_days(text: str) -> list[int]:
    if text.strip().lower() in _EVERY_DAY:
        return list(range(7))
    days: list[int] = []
    for part in text.split(","):
        if not part.strip():
            continue
        if "-" in part:
            first, last = (_parse_day(p) for p in part.split("-", 1))
            days.extend((first + i) % 7 for i in range((last - first) % 7 + 1))
        else:
            days.append(_parse_day(part))
    return days


def parse_schedule(text: str, tz_name: str = "UTC") -> DeadlineSchedule:
    """Parse ``"mon,wed,fri 16:00"``; groups separated by ``;`` may use
    different times (``"mon-fri 18:00; sun 12:00"``). Days are names or
    three-letter abbreviations, ``a-b`` ranges, or ``daily``.
    """
    slots: set[Slot] = set()
    for group in text.split(";"):
        if not group.strip():
            continue
        words = group.split()
        if len(words) < 2:
            raise ScheduleError(
                f"{group.strip()!r} needs days and a time, e.g. 'Mon,Wed,Fri 16:00'."
            )
        at = _parse_time(words[-1])
        slots.update(Slot(day, at) for day in _parse_days(" ".join(words[:-1]).replace(" ", "")))
    if not slots:
        raise ScheduleError("A schedule needs at least one day and time, e.g. 'Mon,Wed,Fri 16:00'.")
    if len(slots) > MAX_SLOTS:
        raise ScheduleError(f"A schedule may have at most {MAX_SLOTS} slots a week.")
    return DeadlineSchedule(tuple(sorted(slots)), _check_timezone(tz_name))


def from_json(data: Optional[dict[str, Any]]) -> Optional[DeadlineSchedule]:
    """The stored form back into a schedule; ``None`` (or no slots) is no schedule."""
    if not data or not data.get("slots"):
        return None
    slots = tuple(sorted(
        Slot(DAYS.index(s["day"]), _parse_time(s["time"])) for s in data["slots"]
    ))
    return DeadlineSchedule(slots, _check_timezone(data.get("timezone") or "UTC"))
