from __future__ import annotations

from unittest import TestCase

from mobile_api.route_id_archive import next_archived_route_id, route_id_search_like


class RouteIdArchiveTests(TestCase):
    def test_first_suffix(self) -> None:
        self.assertEqual(next_archived_route_id("00ЭК-1", set()), "00ЭК-1~1")

    def test_increments_taken_suffix(self) -> None:
        self.assertEqual(next_archived_route_id("00ЭК-1", {"00ЭК-1~1"}), "00ЭК-1~2")

    def test_search_like_keeps_original_findable(self) -> None:
        self.assertEqual(route_id_search_like("00ЭК-1"), "00ЭК-1~%")
        archived = next_archived_route_id("00ЭК-1", {"00ЭК-1"})
        self.assertTrue(archived.startswith("00ЭК-1~"))
