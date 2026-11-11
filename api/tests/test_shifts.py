from __future__ import annotations

from datetime import datetime
from unittest import TestCase
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from mobile_api.shifts_router import resolve_shift_fleet_plate, shift_title
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


class ShiftFleetPlateTests(TestCase):
    def test_accepts_plate_from_admin_list(self) -> None:
        plate = resolve_shift_fleet_plate("а123вс 77", allowed={"А123ВС77"}, label="тягач")
        self.assertEqual(plate, "А123ВС77")

    def test_allows_empty_when_optional(self) -> None:
        self.assertEqual(
            resolve_shift_fleet_plate("", allowed={"А123ВС77"}, empty_ok=True, label="прицеп"),
            "",
        )

    def test_keeps_current_plate_if_removed_from_list(self) -> None:
        plate = resolve_shift_fleet_plate("А123ВС77", allowed=set(), current="А123ВС77", label="тягач")
        self.assertEqual(plate, "А123ВС77")

    def test_rejects_unknown_plate(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            resolve_shift_fleet_plate("А999АА77", allowed={"А123ВС77"}, label="тягач")
        self.assertEqual(ctx.exception.status_code, 400)
