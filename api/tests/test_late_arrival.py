from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest import TestCase
from zoneinfo import ZoneInfo

from utils.late_arrival import (
    apply_late_reason,
    eta_is_late,
    last_late_reason_text,
    late_reason_lines,
    late_reason_required,
    point_has_delay,
    point_late_kind,
    registration_is_late,
)

MOSCOW = ZoneInfo("Europe/Moscow")


class LateArrivalTests(TestCase):
    def test_eta_before_plan_is_not_late(self) -> None:
        self.assertFalse(eta_is_late("22.10.2026", "18:30", "18:00"))
        self.assertFalse(eta_is_late("22.10.2026", "18:30", "18:30"))

    def test_eta_after_plan_is_late(self) -> None:
        self.assertTrue(eta_is_late("22.10.2026", "18:30", "18:31"))
        self.assertTrue(eta_is_late("22.10.2026", "18:30", "19:00"))

    def test_no_eta_is_not_late(self) -> None:
        self.assertFalse(eta_is_late("22.10.2026", "18:30", ""))
        self.assertFalse(eta_is_late("22.10.2026", "18:30", None))

    def test_registration_after_plan_is_late(self) -> None:
        fact = datetime(2026, 10, 22, 18, 45, tzinfo=MOSCOW)
        self.assertTrue(registration_is_late(fact, "22.10.2026", "18:30"))
        on_time = datetime(2026, 10, 22, 18, 30, tzinfo=MOSCOW)
        self.assertFalse(registration_is_late(on_time, "22.10.2026", "18:30"))

    def test_risk_then_fact(self) -> None:
        risk = SimpleNamespace(
            date_point="22.10.2026",
            point_time="18:30",
            estimated_arrival="19:00",
            registration_time=None,
            time_registration=None,
        )
        self.assertEqual(point_late_kind(risk), "risk")
        fact = SimpleNamespace(
            date_point="22.10.2026",
            point_time="18:30",
            estimated_arrival="19:00",
            registration_time=datetime(2026, 10, 22, 19, 10, tzinfo=MOSCOW),
            time_registration=None,
        )
        self.assertEqual(point_late_kind(fact), "fact")
        on_time = SimpleNamespace(
            date_point="22.10.2026",
            point_time="18:30",
            estimated_arrival="18:00",
            registration_time=datetime(2026, 10, 22, 18, 20, tzinfo=MOSCOW),
            time_registration=None,
        )
        self.assertEqual(point_late_kind(on_time), "")

    def test_late_reason_required_only_when_late(self) -> None:
        self.assertFalse(
            late_reason_required(
                to_status="process",
                date_point="22.10.2026",
                point_time="18:30",
                eta_raw="18:00",
                occurred_at=None,
            )
        )
        self.assertFalse(
            late_reason_required(
                to_status="process",
                date_point="22.10.2026",
                point_time="18:30",
                eta_raw="",
                occurred_at=None,
            )
        )
        self.assertTrue(
            late_reason_required(
                to_status="process",
                date_point="22.10.2026",
                point_time="18:30",
                eta_raw="19:00",
                occurred_at=None,
            )
        )
        fact = datetime(2026, 10, 22, 18, 45, tzinfo=MOSCOW)
        self.assertTrue(
            late_reason_required(
                to_status="registration",
                date_point="22.10.2026",
                point_time="18:30",
                eta_raw="",
                occurred_at=fact,
            )
        )

    def test_apply_late_reason_writes_note(self) -> None:
        point = SimpleNamespace(late_reason="", point_note="Склад")
        apply_late_reason(point, "пробки", "Причина опоздания (ОВП)")
        self.assertIn("пробки", point.late_reason)
        self.assertIn("Склад", point.point_note)
        self.assertIn("пробки", point.point_note)

    def test_empty_late_reason_does_not_change_point(self) -> None:
        point = SimpleNamespace(late_reason="", point_note="Склад")
        apply_late_reason(point, "  ", "Причина опоздания (регистрация)")
        self.assertEqual(point.late_reason, "")
        self.assertEqual(point.point_note, "Склад")

    def test_late_reason_lines_split_same_line(self) -> None:
        raw = "Причина опоздания (ОВП): Только что прислали задание Причина опоздания (регистрация): Поздно прислали задание"
        self.assertEqual(
            late_reason_lines(raw),
            [
                "Причина опоздания (ОВП): Только что прислали задание",
                "Причина опоздания (регистрация): Поздно прислали задание",
            ],
        )
        self.assertEqual(last_late_reason_text(raw), "Поздно прислали задание")

    def test_apply_late_reason_reuses_existing_text(self) -> None:
        point = SimpleNamespace(late_reason="Причина опоздания (ОВП): пробки", point_note="")
        apply_late_reason(point, "", "Причина опоздания (регистрация)")
        self.assertIn("Причина опоздания (ОВП): пробки", point.late_reason)
        self.assertIn("Причина опоздания (регистрация): пробки", point.late_reason)

    def test_point_has_delay_includes_automatic_late(self) -> None:
        risk = SimpleNamespace(
            date_point="22.10.2026",
            point_time="18:30",
            estimated_arrival="19:00",
            registration_time=None,
            time_registration=None,
            late_reason="",
        )
        on_time = SimpleNamespace(
            date_point="22.10.2026",
            point_time="18:30",
            estimated_arrival="18:00",
            registration_time=datetime(2026, 10, 22, 18, 20, tzinfo=MOSCOW),
            time_registration=None,
            late_reason="",
        )
        recorded = SimpleNamespace(
            date_point="22.10.2026",
            point_time="18:30",
            estimated_arrival="18:00",
            registration_time=datetime(2026, 10, 22, 18, 20, tzinfo=MOSCOW),
            time_registration=None,
            late_reason="Причина опоздания (ОВП): пробки",
        )
        self.assertTrue(point_has_delay(risk))
        self.assertFalse(point_has_delay(on_time))
        self.assertTrue(point_has_delay(recorded))

    def test_gates_never_require_late_reason(self) -> None:
        fact = datetime(2026, 10, 22, 19, 10, tzinfo=MOSCOW)
        self.assertFalse(
            late_reason_required(
                to_status="load",
                date_point="22.10.2026",
                point_time="18:30",
                eta_raw="",
                occurred_at=fact,
            )
        )
