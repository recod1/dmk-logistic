from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase
from zoneinfo import ZoneInfo

from mobile_api.shift_daily import due_check_date, fault_items, normalize_complete_items

MOSCOW = ZoneInfo("Europe/Moscow")


class DueCheckDateTests(TestCase):
    def test_same_local_day_skips_intake_day(self) -> None:
        started = datetime(2026, 11, 10, 6, 0, tzinfo=MOSCOW)
        now = datetime(2026, 11, 10, 18, 0, tzinfo=MOSCOW)
        self.assertIsNone(due_check_date(started, now))

    def test_next_day_before_seven_is_not_due(self) -> None:
        started = datetime(2026, 11, 10, 8, 0, tzinfo=MOSCOW)
        now = datetime(2026, 11, 11, 6, 59, tzinfo=MOSCOW)
        self.assertIsNone(due_check_date(started, now))

    def test_next_day_from_seven_is_due(self) -> None:
        started = datetime(2026, 11, 10, 20, 0, tzinfo=MOSCOW)
        now = datetime(2026, 11, 11, 7, 0, tzinfo=MOSCOW)
        self.assertEqual(due_check_date(started, now).isoformat(), "2026-11-11")

    def test_utc_input_uses_moscow_calendar(self) -> None:
        started = datetime(2026, 11, 10, 21, 0, tzinfo=timezone.utc)  # 00:00 11.11 Moscow
        now = datetime(2026, 11, 11, 8, 0, tzinfo=MOSCOW)
        self.assertIsNone(due_check_date(started, now))


class NormalizeCompleteItemsTests(TestCase):
    def _all_ok(self) -> list[dict]:
        keys = ["tires", "lights", "oil", "coolant", "brakes", "clutch", "tacho", "reefer"]
        return [{"key": key, "st": "ok"} for key in keys]

    def test_requires_all_keys(self) -> None:
        with self.assertRaises(ValueError):
            normalize_complete_items(self._all_ok()[:-1])

    def test_collects_faults(self) -> None:
        items = self._all_ok()
        items[0]["st"] = "bad"
        items[0]["note"] = "прокол"
        out = normalize_complete_items(items)
        faults = fault_items(out)
        self.assertEqual(len(faults), 1)
        self.assertEqual(faults[0]["key"], "tires")
        self.assertEqual(faults[0]["note"], "прокол")
