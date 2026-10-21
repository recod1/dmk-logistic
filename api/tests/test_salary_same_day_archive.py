from __future__ import annotations

from unittest import TestCase

from mobile_api.salary_logic import should_archive_same_day_salary


class SameDaySalaryArchiveTests(TestCase):
    def test_archives_when_plates_match(self) -> None:
        self.assertTrue(should_archive_same_day_salary("А111АА22", "ЕН068477", "а111аа22", "ен068477"))

    def test_keeps_both_when_vehicle_differs(self) -> None:
        self.assertFalse(should_archive_same_day_salary("А111АА22", "ЕН068477", "В222ВВ33", "ЕН068477"))

    def test_keeps_both_when_trailer_differs(self) -> None:
        self.assertFalse(should_archive_same_day_salary("А111АА22", "ЕН068477", "А111АА22", "ЕН000001"))

    def test_empty_plates_count_as_same(self) -> None:
        self.assertTrue(should_archive_same_day_salary("", "", " ", None))
