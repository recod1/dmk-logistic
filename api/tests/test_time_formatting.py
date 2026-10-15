from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase
from zoneinfo import ZoneInfo

from mobile_api.time_formatting import format_dt_for_app, format_pressed_if_differs

MOSCOW = ZoneInfo("Europe/Moscow")


class TimeFormattingTests(TestCase):
    def test_pressed_omitted_when_same_minute(self) -> None:
        occurred = datetime(2026, 10, 15, 6, 5, tzinfo=timezone.utc)
        pressed = datetime(2026, 10, 15, 6, 5, 40, tzinfo=timezone.utc)
        self.assertIsNone(format_pressed_if_differs(occurred, pressed))

    def test_pressed_shown_when_differs(self) -> None:
        occurred = datetime(2026, 10, 15, 5, 50, tzinfo=timezone.utc)
        pressed = datetime(2026, 10, 15, 6, 5, tzinfo=timezone.utc)
        self.assertEqual(format_pressed_if_differs(occurred, pressed), "15.10.2026 09:05")

    def test_moscow_wall_from_utc(self) -> None:
        instant = datetime(2026, 10, 15, 6, 5, tzinfo=timezone.utc)
        self.assertEqual(format_dt_for_app(instant), "15.10.2026 09:05")
