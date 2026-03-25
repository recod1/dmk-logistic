from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase

from mobile_api.driver_trip_rules import DriverRouteState, can_accept_route, pick_active_route


class DriverTripRulesTests(TestCase):
    def test_pick_active_prefers_process_route(self) -> None:
        routes = [
            DriverRouteState(id="r-new-1", status="new", created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
            DriverRouteState(id="r-proc-1", status="process", created_at=datetime(2026, 1, 3, tzinfo=timezone.utc)),
        ]
        active = pick_active_route(routes)
        self.assertIsNotNone(active)
        self.assertEqual(active.id, "r-proc-1")

    def test_can_accept_rejects_when_another_route_already_process(self) -> None:
        routes = [
            DriverRouteState(id="r-proc", status="process", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
            DriverRouteState(id="r-new", status="new", created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        ]
        allowed, reason = can_accept_route("r-new", routes)
        self.assertFalse(allowed)
        self.assertEqual(reason, "Another route is already accepted")

    def test_can_accept_requires_creation_order(self) -> None:
        routes = [
            DriverRouteState(id="r-new-1", status="new", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
            DriverRouteState(id="r-new-2", status="new", created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        ]
        allowed, reason = can_accept_route("r-new-2", routes)
        self.assertFalse(allowed)
        self.assertEqual(reason, "Routes must be accepted in creation order")

    def test_can_accept_first_new_route(self) -> None:
        routes = [
            DriverRouteState(id="r-new-1", status="new", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
            DriverRouteState(id="r-new-2", status="new", created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        ]
        allowed, reason = can_accept_route("r-new-1", routes)
        self.assertTrue(allowed)
        self.assertIsNone(reason)
