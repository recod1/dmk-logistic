from __future__ import annotations

from sqlalchemy.orm import Session

from mobile_api.models import Point, Route, User
from mobile_api.notifications_service import create_notification_for_users

POINT_STATUS_LABELS_RU: dict[str, str] = {
    "new": "Новая",
    "process": "Выехал на точку",
    "registration": "Регистрация",
    "load": "На воротах",
    "docs": "Документы",
    "success": "Выехал с точки",
}


def _format_driver_name(user: User | None) -> str:
    if user is None:
        return "Неизвестный водитель"
    if user.full_name:
        return user.full_name
    return user.login


def build_route_assigned_notifications(
    *,
    route: Route,
    assigned_user: User,
    actor_user: User | None = None,
) -> list[dict]:
    actor_label = _format_driver_name(actor_user) if actor_user else "Система"
    return [
        {
            "user_ids": [assigned_user.id],
            "event_type": "route_assigned",
            "title": "Назначен рейс",
            "message": f"Вам назначен рейс #{route.id}. Источник: {actor_label}.",
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
    actor_label = _format_driver_name(actor_user)
    return [
        {
            "user_ids": recipients,
            "event_type": "route_cancelled",
            "title": "Рейс отменён",
            "message": f"Рейс #{route.id} отменён. Инициатор: {actor_label}.",
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
    actor_label = _format_driver_name(actor_user)
    recipients = [route.created_by_user_id, route.assigned_user_id]
    return [
        {
            "user_ids": recipients,
            "event_type": "route_completed",
            "title": "Рейс завершён",
            "message": f"Рейс #{route.id} завершён. Завершил: {actor_label}.",
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
    actor_label = _format_driver_name(actor_user)
    recipients = [route.created_by_user_id, route.assigned_user_id]
    return [
        {
            "user_ids": recipients,
            "event_type": "point_status_changed",
            "title": "Изменение статуса точки",
            "message": (
                f"Рейс #{route.id}, точка #{point.id}: статус «{status_label}». "
                f"Адрес: {point.place_point}. Инициатор: {actor_label}."
            ),
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
    persist_notifications(
        db,
        build_route_assigned_notifications(
            route=route,
            assigned_user=assigned_user,
            actor_user=actor_user,
        ),
    )


def notify_route_cancelled(
    db: Session,
    *,
    route: Route,
    assigned_user: User | None,
    actor_user: User,
) -> None:
    persist_notifications(
        db,
        build_route_cancelled_notifications(
            route=route,
            assigned_user=assigned_user,
            actor_user=actor_user,
        ),
    )


def notify_route_completed(
    db: Session,
    *,
    route: Route,
    actor_user: User,
) -> None:
    persist_notifications(
        db,
        build_route_completed_notifications(
            route=route,
            actor_user=actor_user,
        ),
    )


def notify_point_status_changed(
    db: Session,
    *,
    route: Route,
    point: Point,
    actor_user: User,
    new_status: str,
) -> None:
    persist_notifications(
        db,
        build_point_status_changed_notifications(
            route=route,
            point=point,
            actor_user=actor_user,
            new_status=new_status,
        ),
    )
