from __future__ import annotations

from unittest import TestCase

from utils.onec_datetime import (
    normalize_planned_date,
    normalize_planned_time,
    planned_wall_fields,
    split_onec_wall_datetime,
)


class OnecDatetimeTests(TestCase):
    def test_splits_24h_dmy(self) -> None:
        self.assertEqual(split_onec_wall_datetime("21.09.2026 16:30"), ("21.09.2026", "16:30"))

    def test_keeps_morning(self) -> None:
        self.assertEqual(split_onec_wall_datetime("21.09.2026 09:00"), ("21.09.2026", "09:00"))

    def test_midnight(self) -> None:
        self.assertEqual(split_onec_wall_datetime("21.09.2026 00:30"), ("21.09.2026", "00:30"))

    def test_pm_token(self) -> None:
        self.assertEqual(split_onec_wall_datetime("21.09.2026 4:30 PM"), ("21.09.2026", "16:30"))

    def test_iso_without_tz_shift(self) -> None:
        self.assertEqual(split_onec_wall_datetime("2026-09-21T16:30:00"), ("21.09.2026", "16:30"))

    def test_date_only_iso_input(self) -> None:
        self.assertEqual(normalize_planned_date("2026-09-21"), "21.09.2026")

    def test_time_only_input(self) -> None:
        self.assertEqual(normalize_planned_time("16:30"), "16:30")

    def test_combined_leftover_splits_for_api(self) -> None:
        self.assertEqual(planned_wall_fields("21.09.2026 16:30", ""), ("21.09.2026", "16:30"))

    def test_does_not_flip_afternoon_without_ampm(self) -> None:
        self.assertEqual(split_onec_wall_datetime("21.09.2026 16:30"), ("21.09.2026", "16:30"))
        self.assertNotEqual(split_onec_wall_datetime("21.09.2026 16:30")[1], "04:30")

    def test_keeps_1700_dmy_and_iso(self) -> None:
        self.assertEqual(split_onec_wall_datetime("21.09.2026 17:00"), ("21.09.2026", "17:00"))
        self.assertEqual(split_onec_wall_datetime("2026-09-21T17:00:00"), ("21.09.2026", "17:00"))
        self.assertNotEqual(split_onec_wall_datetime("21.09.2026 17:00")[1], "05:00")


class OnecParseTests(TestCase):
    def test_parse_loading_keeps_1630(self) -> None:
        from mobile_api.onec_routes import parse_onec_message

        parsed = parse_onec_message(
            "R-1\nФИО водителя: Тест\nЗагр: 21.09.2026 16:30 Организация: Склад\n"
        )
        self.assertEqual(len(parsed.points), 1)
        self.assertEqual(parsed.points[0].date_point, "21.09.2026")
        self.assertEqual(parsed.points[0].point_time, "16:30")

    def test_keeps_1700_and_dispatcher_from_dmk_not_placeholder(self) -> None:
        from mobile_api.onec_routes import parse_onec_message

        raw = (
            "00ЭК-036813\n"
            "ФИО водителя: Иванов Иван\n"
            "Логист: Петров Пётр\n"
            "Контакты логистов: +7 999 123-45-67\n"
            "Контакты ООО ДМК: +7 915 170-05-89\n"
            "Загр: 21.09.2026 17:00 Организация: Склад ДМК\n"
        )
        parsed = parse_onec_message(raw)
        self.assertEqual(parsed.route_id, "00ЭК-036813")
        self.assertEqual(parsed.logistic_name, "Петров Пётр")
        self.assertEqual(parsed.dispatcher_contacts, "+7 915 170-05-89")
        self.assertNotIn("999 123", parsed.dispatcher_contacts)
        self.assertEqual(parsed.points[0].date_point, "21.09.2026")
        self.assertEqual(parsed.points[0].point_time, "17:00")

    def test_iso_1700_without_tz_shift(self) -> None:
        from mobile_api.onec_routes import parse_onec_message

        parsed = parse_onec_message(
            "00ЭК-036813\nКонтакты: +79151700589\nЗагр: 2026-09-21T17:00:00 Организация: Склад\n"
        )
        self.assertEqual(parsed.dispatcher_contacts, "+79151700589")
        self.assertEqual(parsed.points[0].date_point, "21.09.2026")
        self.assertEqual(parsed.points[0].point_time, "17:00")

    def test_empty_contacts_stay_empty(self) -> None:
        from mobile_api.onec_routes import parse_onec_message

        parsed = parse_onec_message("00ЭК-1\nЗагр: 21.09.2026 17:00 Организация: Склад\n")
        self.assertEqual(parsed.dispatcher_contacts, "")
        self.assertEqual(parsed.logistic_name, "")
