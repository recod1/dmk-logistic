from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from mobile_api.route_notification_logic import (
    build_point_status_changed_notifications,
    build_route_cancelled_notifications,
)


class PointStatusNotificationTests(TestCase):
    def test_process_status_includes_ovp(self) -> None:
        route = SimpleNamespace(id="R-1", created_by_user_id=2, assigned_user_id=5)
        point = SimpleNamespace(
            estimated_arrival="14:30",
            departure_time=None,
            time_accepted=None,
            registration_time=None,
            time_registration=None,
            gate_time=None,
            time_put_on_gate=None,
            docs_time=None,
            time_docs=None,
        )
        actor = SimpleNamespace(id=5)
        items = build_point_status_changed_notifications(
            route=route,  # type: ignore[arg-type]
            point=point,  # type: ignore[arg-type]
            actor_user=actor,  # type: ignore[arg-type]
            new_status="process",
        )
        self.assertEqual(len(items), 1)
        self.assertIn("ОВП 14:30", items[0]["message"])
        self.assertEqual(items[0]["payload"].get("ovp"), "14:30")

    def test_other_status_omits_ovp(self) -> None:
        route = SimpleNamespace(id="R-1", created_by_user_id=2, assigned_user_id=5)
        point = SimpleNamespace(
            estimated_arrival="14:30",
            departure_time=None,
            time_accepted=None,
            registration_time=None,
            time_registration=None,
            gate_time=None,
            time_put_on_gate=None,
            docs_time=None,
            time_docs=None,
        )
        actor = SimpleNamespace(id=5)
        items = build_point_status_changed_notifications(
            route=route,  # type: ignore[arg-type]
            point=point,  # type: ignore[arg-type]
            actor_user=actor,  # type: ignore[arg-type]
            new_status="registration",
        )
        self.assertNotIn("ОВП", items[0]["message"])

    def test_late_risk_payload(self) -> None:
        route = SimpleNamespace(id="R-1", created_by_user_id=2, assigned_user_id=5)
        point = SimpleNamespace(
            estimated_arrival="19:00",
            date_point="22.10.2026",
            point_time="18:30",
            late_reason="Причина опоздания (ОВП): пробки",
            departure_time=None,
            time_accepted=None,
            registration_time=None,
            time_registration=None,
            gate_time=None,
            time_put_on_gate=None,
            docs_time=None,
            time_docs=None,
        )
        actor = SimpleNamespace(id=5)
        items = build_point_status_changed_notifications(
            route=route,  # type: ignore[arg-type]
            point=point,  # type: ignore[arg-type]
            actor_user=actor,  # type: ignore[arg-type]
            new_status="process",
        )
        self.assertEqual(items[0]["payload"].get("late_kind"), "risk")
        self.assertIn("пробки", items[0]["payload"].get("late_reason", ""))
        self.assertIn("пробки", items[0]["message"])


class RouteCancelledNotificationTests(TestCase):
    def test_cancel_reason_is_included(self) -> None:
        route = SimpleNamespace(id="R-9", created_by_user_id=2, assigned_user_id=5, status="cancelled", updated_at=None)
        assigned = SimpleNamespace(id=5)
        actor = SimpleNamespace(id=3)
        items = build_route_cancelled_notifications(
            route=route,  # type: ignore[arg-type]
            assigned_user=assigned,  # type: ignore[arg-type]
            actor_user=actor,  # type: ignore[arg-type]
            reason="Заказчик снял рейс",
        )
        self.assertEqual(len(items), 1)
        self.assertIn("Причина: Заказчик снял рейс", items[0]["message"])
        self.assertEqual(items[0]["payload"].get("cancel_reason"), "Заказчик снял рейс")
