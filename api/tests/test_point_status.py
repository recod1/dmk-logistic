from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from mobile_api.point_status import effective_point_status, point_is_completed


def _point(**kwargs):
    defaults = {
        "status": "new",
        "departure_time": None,
        "time_accepted": None,
        "time_departure": None,
        "registration_time": None,
        "time_registration": None,
        "gate_time": None,
        "time_put_on_gate": None,
        "docs_time": None,
        "time_docs": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class EffectivePointStatusTests(TestCase):
    def test_stored_status_when_no_timestamps(self) -> None:
        self.assertEqual(effective_point_status(_point(status="new")), "new")
        self.assertEqual(effective_point_status(_point(status="load")), "load")

    def test_gate_time_beats_stale_new(self) -> None:
        point = _point(status="new", gate_time="filled")
        self.assertEqual(effective_point_status(point), "load")
        self.assertFalse(point_is_completed(point))

    def test_docs_time_completes_stale_new(self) -> None:
        point = _point(status="new", docs_time="filled")
        self.assertEqual(effective_point_status(point), "docs")
        self.assertTrue(point_is_completed(point))

    def test_does_not_downgrade_stored_status(self) -> None:
        self.assertEqual(effective_point_status(_point(status="load", departure_time="filled")), "load")
