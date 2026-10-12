from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase
from zoneinfo import ZoneInfo

from mobile_api.daily_mileage_calc import is_correction, suggested_days_from_readings

MSK = ZoneInfo("Europe/Moscow")


class DailyMileageTests(TestCase):
    def test_groups_by_moscow_calendar_day_and_carries_start(self) -> None:
        readings = [
            (datetime(2026, 10, 11, 20, 0, tzinfo=timezone.utc), 1000.0),  # 23:00 MSK 11th
            (datetime(2026, 10, 11, 21, 30, tzinfo=timezone.utc), 1010.0),  # 00:30 MSK 12th
            (datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc), 1200.0),  # 13:00 MSK 12th
        ]
        days = suggested_days_from_readings(readings)
        self.assertEqual([item["day_msk"] for item in days], ["2026-10-11", "2026-10-12"])
        first, second = days
        self.assertEqual(first["odometer_start"], 1000.0)
        self.assertEqual(first["odometer_end"], 1000.0)
        self.assertEqual(first["km"], 0)
        self.assertEqual(second["odometer_start"], 1000.0)
        self.assertEqual(second["odometer_end"], 1200.0)
        self.assertEqual(second["km"], 200)

    def test_naive_utc_datetimes_use_moscow_day(self) -> None:
        readings = [
            (datetime(2026, 10, 11, 21, 0), 5000.0),  # naive treated as UTC → 00:00 MSK 12th
            (datetime(2026, 10, 12, 18, 0), 5300.0),
        ]
        days = suggested_days_from_readings(readings)
        self.assertEqual([item["day_msk"] for item in days], ["2026-10-12"])
        self.assertEqual(days[0]["km"], 300)

    def test_explicit_msk_wall_times(self) -> None:
        readings = [
            (datetime(2026, 10, 12, 1, 0, tzinfo=MSK), 10.0),
            (datetime(2026, 10, 12, 23, 50, tzinfo=MSK), 90.0),
        ]
        days = suggested_days_from_readings(readings)
        self.assertEqual(len(days), 1)
        self.assertEqual(days[0]["day_msk"], "2026-10-12")
        self.assertEqual(days[0]["km"], 80)

    def test_correction_detects_changed_km(self) -> None:
        suggested = {"odometer_start": 100.0, "odometer_end": 150.0, "km": 50}
        self.assertFalse(is_correction(suggested, 100.0, 150.0, 50))
        self.assertTrue(is_correction(suggested, 100.0, 160.0, 60))
        self.assertTrue(is_correction(suggested, 100.0, 150.0, 40))
