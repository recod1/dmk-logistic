from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase
from zoneinfo import ZoneInfo

from utils.stale_anchor import stale_anchor_started

MOSCOW = ZoneInfo("Europe/Moscow")


class StaleAnchorTests(TestCase):
    def test_registration_early_arrival_uses_planned(self) -> None:
        fact = datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc)  # 05:00 Moscow
        started = stale_anchor_started(
            status_value="registration",
            fact=fact,
            date_point="14.10.2026",
            point_time="08:00",
        )
        self.assertEqual(started, datetime(2026, 10, 14, 8, 0, tzinfo=MOSCOW).astimezone(timezone.utc))

    def test_registration_late_arrival_uses_fact(self) -> None:
        fact = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)  # 09:00 Moscow
        started = stale_anchor_started(
            status_value="registration",
            fact=fact,
            date_point="14.10.2026",
            point_time="08:00",
        )
        self.assertEqual(started, fact)

    def test_process_ignores_planned(self) -> None:
        fact = datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc)
        started = stale_anchor_started(
            status_value="process",
            fact=fact,
            date_point="14.10.2026",
            point_time="08:00",
        )
        self.assertEqual(started, fact)
