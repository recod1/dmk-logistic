from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.models import Point, Route, User
from mobile_api.notifications_service import create_notification_for_users
from mobile_api.roles import RoleCode

POINT_STATUS_LABELS_RU: dict[str, str] = {
    "new": "Новая",
    "process": "Выехал на точку",
    "registration": "Зарегистрировался",
    "load": "На воротах",
    "docs": "Забрал документы",
    "success": "Забрал документы",
}


def _format_event_time(dt: datetime | None = None) -> str:
    value = dt or datetime.now(timezone.utc)
    return value.astimezone().strftime("%d.%m.%Y %H:%M")


def _manager_ids(db: Session) -> list[int]:
    rows = db.scalars(
        select(User.id).where(
            User.role_code.in_(
                [
                    RoleCode.ADMIN.value,
                    RoleCode.SUPERADMIN.value,
                    RoleCode.LOGISTIC.value,
                ]
            )
        )
    ).all()
    return [int(item) for item in rows]


def _format_notification_message(action: str, route_id: str, at: datetime | None = None) -> str:
    return f"{action} · Рейс {route_id} · {_format_event_time(at)}"


def _point_event_time(point: Point, status_value: str) -> datetime | None:
    if status_value == "process":
        return point.departure_time or point.time_accepted
    if status_value == "registration":
        return point.registration_time or point.time_registration
    if status_value == "load":
        return point.gate_time or point.time_put_on_gate
    if status_value in {"docs", "success"}:
        return point.docs_time or point.time_docs
    return None


def build_route_assigned_notifications(
    *,
    route: Route,
    assigned_user: User,
    actor_user: User | None = None,
) -> list[dict]:
    action = "Назначен рейс"
    event_time = route.accepted_at if route.status == "process" else route.created_at
    return [
        {
            "user_ids": [assigned_user.id, route.created_by_user_id],
            "event_type": "route_assigned",
            "title": action,
            "message": _format_notification_message(action, route.id, event_time),
            "route_id": route.id,
            "point_id": None,
            "payload": {"route_status": route.status},
        }
    ]


def build_route_cancelled_notifications(
    *,
    route: Route,
    assigned_user: User | None,
    actor_user: User,
) -> list[dict]:
    recipients: list[int | None] = [route.created_by_user_id]
    if assigned_user is not None:
        recipients.append(assigned_user.id)
    action = "Отменен рейс"
    return [
        {
            "user_ids": recipients,
            "event_type": "route_cancelled",
            "title": action,
            "message": _format_notification_message(action, route.id, route.updated_at),
            "route_id": route.id,
            "point_id": None,
            "payload": {"route_status": route.status},
        }
    ]


def build_route_completed_notifications(
    *,
    route: Route,
    actor_user: User,
) -> list[dict]:
    action = "Рейс завершен"
    recipients = [route.created_by_user_id, route.assigned_user_id]
    return [
        {
            "user_ids": recipients,
            "event_type": "route_completed",
            "title": action,
            "message": _format_notification_message(action, route.id, route.updated_at),
            "route_id": route.id,
            "point_id": None,
            "payload": {"route_status": route.status},
        }
    ]


def build_point_status_changed_notifications(
    *,
    route: Route,
    point: Point,
    actor_user: User,
    new_status: str,
) -> list[dict]:
    status_label = POINT_STATUS_LABELS_RU.get(new_status, new_status)
    action = status_label
    recipients = [route.created_by_user_id, route.assigned_user_id]
    return [
        {
            "user_ids": recipients,
            "event_type": "point_status_changed",
            "title": action,
            "message": _format_notification_message(action, route.id, _point_event_time(point, new_status)),
            "route_id": route.id,
            "point_id": point.id,
            "payload": {"point_status": new_status},
        }
    ]


def persist_notifications(db, notifications: list[dict]) -> None:
    for item in notifications:
        create_notification_for_users(
            db,
            user_ids=item["user_ids"],
            event_type=item["event_type"],
            title=item["title"],
            message=item["message"],
            route_id=item.get("route_id"),
            point_id=item.get("point_id"),
            payload=item.get("payload"),
        )


def notify_route_assigned(
    db: Session,
    *,
    route: Route,
    assigned_user: User,
    actor_user: User | None = None,
) -> None:
    notifications = build_route_assigned_notifications(
        route=route,
        assigned_user=assigned_user,
        actor_user=actor_user,
    )
    manager_ids = _manager_ids(db)
    for item in notifications:
        base_recipients = [user_id for user_id in item.get("user_ids", []) if user_id]
        item["user_ids"] = sorted(set(base_recipients + manager_ids))
    persist_notifications(db, notifications)


def notify_route_cancelled(
    db: Session,
    *,
    route: Route,
    assigned_user: User | None,
    actor_user: User,
) -> None:
    notifications = build_route_cancelled_notifications(
        route=route,
        assigned_user=assigned_user,
        actor_user=actor_user,
    )
    manager_ids = _manager_ids(db)
    for item in notifications:
        base_recipients = [user_id for user_id in item.get("user_ids", []) if user_id]
        item["user_ids"] = sorted(set(base_recipients + manager_ids))
    persist_notifications(db, notifications)


def notify_route_completed(
    db: Session,
    *,
    route: Route,
    actor_user: User,
) -> None:
    notifications = build_route_completed_notifications(
        route=route,
        actor_user=actor_user,
    )
    manager_ids = _manager_ids(db)
    for item in notifications:
        base_recipients = [user_id for user_id in item.get("user_ids", []) if user_id]
        item["user_ids"] = sorted(set(base_recipients + manager_ids))
    persist_notifications(db, notifications)


def notify_point_status_changed(
    db: Session,
    *,
    route: Route,
    point: Point,
    actor_user: User,
    new_status: str,
) -> None:
    notifications = build_point_status_changed_notifications(
        route=route,
        point=point,
        actor_user=actor_user,
        new_status=new_status,
    )
    manager_ids = _manager_ids(db)
    for item in notifications:
        base_recipients = [user_id for user_id in item.get("user_ids", []) if user_id]
        item["user_ids"] = sorted(set(base_recipients + manager_ids))
    persist_notifications(db, notifications)
