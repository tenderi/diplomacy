"""Weekly deadline schedules (``server.deadline_schedule``): parsing, the stored
form, and which slot a phase beginning at a given moment gets."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

import pytest

from server.deadline_schedule import (
    DeadlineSchedule,
    ScheduleError,
    Slot,
    from_json,
    parse_schedule,
)

pytestmark = pytest.mark.unit

UTC = timezone.utc
MWF_16 = parse_schedule("Mon,Wed,Fri 16:00")


class TestParse:
    def test_days_and_one_time(self):
        assert MWF_16.slots == (Slot(0, time(16)), Slot(2, time(16)), Slot(4, time(16)))
        assert MWF_16.tz_name == "UTC"

    def test_spaces_full_names_and_case_are_accepted(self):
        assert parse_schedule("monday, WEDNESDAY, fri 16:00").slots == MWF_16.slots

    def test_ranges_wrap_around_the_week(self):
        days = [s.weekday for s in parse_schedule("fri-mon 09:30").slots]
        assert days == [0, 4, 5, 6]

    def test_daily(self):
        assert [s.weekday for s in parse_schedule("daily 20:00").slots] == list(range(7))

    def test_groups_may_use_different_times(self):
        sched = parse_schedule("mon-fri 18:00; sun 12:00")
        assert sched.slots[-1] == Slot(6, time(12))
        assert len(sched.slots) == 6

    def test_duplicates_collapse(self):
        assert parse_schedule("mon 16:00; mon 16:00").slots == (Slot(0, time(16)),)

    def test_timezone_is_kept(self):
        assert parse_schedule("mon 16:00", "Europe/Helsinki").tz_name == "Europe/Helsinki"

    @pytest.mark.parametrize(
        ("text", "tz", "message"),
        [
            ("mon", "UTC", "'mon' needs days and a time, e.g. 'Mon,Wed,Fri 16:00'."),
            ("funday 16:00", "UTC", "'funday' is not a day of the week; use Mon, Tue, ... Sun."),
            ("mon 25:00", "UTC", "'25:00' is not a time; write it as HH:MM, e.g. 16:00."),
            ("mon 4pm", "UTC", "'4pm' is not a time; write it as HH:MM, e.g. 16:00."),
            (" ; ", "UTC", "A schedule needs at least one day and time, e.g. 'Mon,Wed,Fri 16:00'."),
            ("mon 16:00", "Mars/Olympus", "Unknown timezone 'Mars/Olympus'; use an IANA name such as UTC or Europe/Helsinki."),
            (
                "daily 01:00; daily 02:00; daily 03:00; daily 04:00",
                "UTC",
                "A schedule may have at most 21 slots a week.",
            ),
        ],
    )
    def test_errors_say_what_is_wrong(self, text: str, tz: str, message: str):
        with pytest.raises(ScheduleError) as e:
            parse_schedule(text, tz)
        assert str(e.value) == message


class TestStoredForm:
    def test_round_trip(self):
        sched = parse_schedule("mon-fri 18:00; sun 12:00", "Europe/Helsinki")
        data = sched.to_json()
        assert data["timezone"] == "Europe/Helsinki"
        assert data["slots"][0] == {"day": "MON", "time": "18:00"}
        assert from_json(data) == sched

    def test_none_and_empty_are_no_schedule(self):
        assert from_json(None) is None
        assert from_json({"timezone": "UTC", "slots": []}) is None

    def test_describe_groups_days_sharing_a_time(self):
        assert MWF_16.describe() == "Mon, Wed, Fri at 16:00 (UTC)"
        assert parse_schedule("sun 12:00; mon,tue 18:00").describe() == (
            "Mon, Tue at 18:00; Sun at 12:00 (UTC)"
        )


class TestNextDeadline:
    # 2026-09-28 is a Monday.
    def test_later_the_same_day(self):
        assert MWF_16.next_deadline(datetime(2026, 9, 28, 9, 0, tzinfo=UTC)) == datetime(
            2026, 9, 28, 16, 0, tzinfo=UTC
        )

    def test_a_turn_processed_at_the_slot_gets_the_next_one(self):
        assert MWF_16.next_deadline(datetime(2026, 9, 28, 16, 0, tzinfo=UTC)) == datetime(
            2026, 9, 30, 16, 0, tzinfo=UTC
        )

    def test_a_slot_within_the_minimum_notice_is_skipped(self):
        assert MWF_16.next_deadline(datetime(2026, 9, 28, 15, 30, tzinfo=UTC)) == datetime(
            2026, 9, 30, 16, 0, tzinfo=UTC
        )
        assert MWF_16.next_deadline(datetime(2026, 9, 28, 15, 0, tzinfo=UTC)) == datetime(
            2026, 9, 28, 16, 0, tzinfo=UTC
        )

    def test_wraps_to_next_week(self):
        assert MWF_16.next_deadline(datetime(2026, 10, 2, 17, 0, tzinfo=UTC)) == datetime(
            2026, 10, 5, 16, 0, tzinfo=UTC
        )

    def test_naive_now_is_utc(self):
        assert MWF_16.next_deadline(datetime(2026, 9, 28, 9, 0)) == datetime(
            2026, 9, 28, 16, 0, tzinfo=UTC
        )

    def test_single_weekly_slot_a_week_out(self):
        weekly = DeadlineSchedule((Slot(0, time(16)),), "UTC")
        assert weekly.next_deadline(datetime(2026, 9, 28, 16, 0, tzinfo=UTC)) == datetime(
            2026, 10, 5, 16, 0, tzinfo=UTC
        )

    def test_local_time_holds_across_daylight_saving(self):
        helsinki = parse_schedule("mon 16:00", "Europe/Helsinki")
        # Summer time (UTC+3), then winter time (UTC+2) after 2026-10-25.
        assert helsinki.next_deadline(datetime(2026, 10, 19, 0, 0, tzinfo=UTC)) == datetime(
            2026, 10, 19, 13, 0, tzinfo=UTC
        )
        assert helsinki.next_deadline(datetime(2026, 10, 26, 0, 0, tzinfo=UTC)) == datetime(
            2026, 10, 26, 14, 0, tzinfo=UTC
        )

    def test_local_day_is_the_schedules_not_utcs(self):
        # 23:30 UTC Sunday is already Monday 02:30 in Helsinki.
        helsinki = parse_schedule("mon 16:00", "Europe/Helsinki")
        assert helsinki.next_deadline(datetime(2026, 9, 27, 23, 30, tzinfo=UTC)) == datetime(
            2026, 9, 28, 13, 0, tzinfo=UTC
        )

    def test_custom_notice(self):
        assert MWF_16.next_deadline(
            datetime(2026, 9, 28, 15, 59, tzinfo=UTC), min_notice=timedelta(0)
        ) == datetime(2026, 9, 28, 16, 0, tzinfo=UTC)
