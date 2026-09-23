from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from utils.route_point_changes import diff_route_points


def _point(**kwargs):
    defaults = {
        "id": 1,
        "type_point": "unloading",
        "place_point": "Склад",
        "date_point": "23.09.2026",
        "point_time": "09:00",
        "order_index": 0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class RoutePointChangeTests(TestCase):
    def test_date_change_phrase(self) -> None:
        phrases = diff_route_points(
            [_point()],
            [_point(date_point="24.09.2026", point_time="12:00")],
        )
        self.assertEqual(phrases, ["Выгрузка · дата: 23.09.2026 09:00 → 24.09.2026 12:00"])

    def test_address_change_phrase(self) -> None:
        phrases = diff_route_points(
            [_point(type_point="loading", place_point="Старый склад")],
            [_point(type_point="loading", place_point="Новый склад")],
        )
        self.assertEqual(phrases, ["Загрузка · адрес: Старый склад → Новый склад"])

    def test_same_points_no_generic_line(self) -> None:
        phrases = diff_route_points(
            [_point()],
            [_point(date_point="2026-09-23", point_time="09:00")],
        )
        self.assertEqual(phrases, [])
