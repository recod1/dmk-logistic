from __future__ import annotations

from datetime import datetime
from unittest import TestCase
from zoneinfo import ZoneInfo

from mobile_api.shifts_router import shift_title
from mobile_api.time_formatting import format_dt_for_app

MOSCOW = ZoneInfo("Europe/Moscow")


class ShiftTitleTests(TestCase):
    def test_active_shift_uses_now_label(self) -> None:
        started = datetime(2026, 10, 22, 8, 0, tzinfo=MOSCOW)
        title = shift_title("Иванов Иван", started, None)
        self.assertTrue(title.startswith("Иванов Иван · "))
        self.assertIn("сейчас", title)
        self.assertIn(format_dt_for_app(started) or "", title)

    def test_ended_shift_shows_range(self) -> None:
        started = datetime(2026, 10, 22, 8, 0, tzinfo=MOSCOW)
        ended = datetime(2026, 10, 24, 20, 15, tzinfo=MOSCOW)
        title = shift_title("Петров П. П.", started, ended)
        self.assertIn("Петров П. П.", title)
        self.assertIn(format_dt_for_app(started) or "", title)
        self.assertIn(format_dt_for_app(ended) or "", title)
        self.assertNotIn("сейчас", title)
