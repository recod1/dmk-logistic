from __future__ import annotations

from unittest import TestCase

from mobile_api.push_notification_format import (
    brief_point_address,
    build_push_body,
    format_push_context_line,
)


class PushNotificationFormatTests(TestCase):
    def test_brief_point_address_prefers_point_name(self) -> None:
        self.assertEqual(
            brief_point_address(point_name="Склад А", place_point="г. Москва, ул. Ленина 1"),
            "Склад А",
        )

    def test_brief_point_address_truncates_long_place(self) -> None:
        long_place = "г. " + "Москва " * 30
        result = brief_point_address(place_point=long_place, max_len=40)
        self.assertLessEqual(len(result), 40)
        self.assertTrue(result.endswith("…"))

    def test_format_push_context_line_joins_parts(self) -> None:
        line = format_push_context_line(
            driver_fio="Иванов И.И.",
            vehicle_no="А123ВС77",
            point_address="Москва, склад 5",
        )
        self.assertEqual(line, "Иванов И.И. · ТС А123ВС77 · Москва, склад 5")

    def test_build_push_body_appends_context_on_new_line(self) -> None:
        body = build_push_body("Рейс R-1 · Назначен", "Иванов · ТС А111АА77 · Адрес")
        self.assertEqual(body, "Рейс R-1 · Назначен\nИванов · ТС А111АА77 · Адрес")
