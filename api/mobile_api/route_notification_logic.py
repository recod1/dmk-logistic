from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.models import Point, Route, User
from mobile_api.notifications_service import create_notification_for_users
from mobile_api.roles import RoleCode
from mobile_api.time_formatting import format_dt_for_app

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
    return format_dt_for_app(value) or ""


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
    return f"Рейс {route_id} · {action} · {_format_event_time(at)}"


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
    skip = [actor_user.id] if actor_user else []
    return [
        {
            "user_ids": [assigned_user.id, route.created_by_user_id],
            "skip_user_ids": skip,
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
    skip = [actor_user.id]
    return [
        {
            "user_ids": recipients,
            "skip_user_ids": skip,
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
    skip = [actor_user.id]
    return [
        {
            "user_ids": recipients,
            "skip_user_ids": skip,
            "event_type": "route_completed",
            "title": action,
            "message": _format_notification_message(action, route.id, route.updated_at),
            "route_id": route.id,
            "point_id": None,
            "payload": {"route_status": route.status},
        }
    ]


def build_route_deleted_notifications(
    *,
    route: Route,
    assigned_user: User | None,
    actor_user: User,
) -> list[dict]:
    recipients: list[int | None] = [route.created_by_user_id]
    if assigned_user is not None:
        recipients.append(assigned_user.id)
    action = "Рейс удален"
    skip = [actor_user.id]
    return [
        {
            "user_ids": recipients,
            "skip_user_ids": skip,
            "event_type": "route_deleted",
            "title": action,
            "message": _format_notification_message(action, route.id, route.updated_at),
            "route_id": None,
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
    skip = [actor_user.id]
    return [
        {
            "user_ids": recipients,
            "skip_user_ids": skip,
            "event_type": "point_status_changed",
            "title": action,
            "message": _format_notification_message(action, route.id, _point_event_time(point, new_status)),
            "route_id": route.id,
            "point_id": point.id,
            "payload": {"point_status": new_status},
        }
    ]


def build_point_status_reverted_notifications(
    *,
    route: Route,
    point: Point,
    actor_user: User,
    previous_status: str,
) -> list[dict]:
    prev_label = POINT_STATUS_LABELS_RU.get(previous_status, previous_status)
    action = f"Откат к этапу: {prev_label}"
    point_label = point.point_name.strip() if point.point_name else point.place_point
    recipients = [route.created_by_user_id, route.assigned_user_id]
    skip = [actor_user.id]
    return [
        {
            "user_ids": recipients,
            "skip_user_ids": skip,
            "event_type": "point_status_reverted",
            "title": action,
            "message": f"Водитель откатил точку «{point_label}» рейса {route.id} к «{prev_label}». {_format_event_time()}",
            "route_id": route.id,
            "point_id": point.id,
            "payload": {"previous_status": previous_status},
        }
    ]


def persist_notifications(db: Session, notifications: list[dict]) -> None:
    for item in notifications:
        skip_raw = item.get("skip_user_ids") or []
        skip_user_ids = [int(x) for x in skip_raw if x is not None]
        create_notification_for_users(
            db,
            user_ids=item["user_ids"],
            event_type=item["event_type"],
            title=item["title"],
            message=item["message"],
            route_id=item.get("route_id"),
            point_id=item.get("point_id"),
            payload=item.get("payload"),
            skip_user_ids=skip_user_ids,
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


def notify_route_accepted_by_driver(
    db: Session,
    *,
    route: Route,
    driver_user: User,
    actor_user: User | None = None,
) -> None:
    """Только админы и логисты; водитель не получает."""
    manager_ids = _manager_ids(db)
    recipients: list[int] = []
    if route.created_by_user_id:
        recipients.append(route.created_by_user_id)
    recipients = sorted(set(recipients + manager_ids))
    driver_name = (driver_user.full_name or driver_user.login or "").strip() or "Водитель"
    action = "Рейс принят водителем"
    skip = [actor_user.id] if actor_user else []
    at = route.accepted_at or datetime.now(timezone.utc)
    message = f"{driver_name} принял(а) рейс {route.id} · {_format_event_time(at)}"
    persist_notifications(
        db,
        [
            {
                "user_ids": recipients,
                "skip_user_ids": skip,
                "event_type": "route_accepted",
                "title": action,
                "message": message,
                "route_id": route.id,
                "point_id": None,
                "payload": {"route_status": route.status},
            }
        ],
    )


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


def notify_route_deleted(
    db: Session,
    *,
    route: Route,
    assigned_user: User | None,
    actor_user: User,
) -> None:
    notifications = build_route_deleted_notifications(
        route=route,
        assigned_user=assigned_user,
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


def notify_point_status_reverted(
    db: Session,
    *,
    route: Route,
    point: Point,
    actor_user: User,
    previous_status: str,
) -> None:
    notifications = build_point_status_reverted_notifications(
        route=route,
        point=point,
        actor_user=actor_user,
        previous_status=previous_status,
    )
    manager_ids = _manager_ids(db)
    for item in notifications:
        base_recipients = [user_id for user_id in item.get("user_ids", []) if user_id]
        item["user_ids"] = sorted(set(base_recipients + manager_ids))
    persist_notifications(db, notifications)
