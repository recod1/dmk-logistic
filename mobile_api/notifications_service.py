from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.models import Notification, Point, Route, User
from mobile_api.notifications_realtime import notifications_realtime_hub

POINT_STATUS_LABELS_RU: dict[str, str] = {
    "new": "Новая",
    "process": "Выехал на точку",
    "registration": "Зарегистрировался",
    "load": "На воротах",
    "docs": "Забрал документы",
    "success": "Выехал с точки",
}


def create_notification_for_users(
    db: Session,
    *,
    user_ids: Iterable[int | None],
    event_type: str,
    title: str,
    message: str,
    route_id: str | None = None,
    point_id: int | None = None,
    payload: dict[str, Any] | None = None,
    skip_user_ids: Iterable[int] | None = None,
) -> None:
    skip = {int(x) for x in skip_user_ids or []}
    unique_ids = sorted({int(user_id) for user_id in user_ids if user_id and int(user_id) not in skip})
    if not unique_ids:
        return

    payload_json = json.dumps(payload, ensure_ascii=False) if payload else None
    created_at = datetime.now(timezone.utc)
    created_items: list[dict[str, Any]] = []
    for user_id in unique_ids:
        item = Notification(
            user_id=user_id,
            route_id=route_id,
            point_id=point_id,
            event_type=event_type,
            title=title,
            message=message,
            payload_json=payload_json,
            is_read=False,
            created_at=created_at,
        )
        db.add(item)
        created_items.append({"user_id": user_id, "row": item})

    db.flush()
    realtime_payloads: list[tuple[int, dict[str, Any]]] = []
    for created in created_items:
        row: Notification = created["row"]
        parsed_payload: dict[str, Any] | None = None
        if row.payload_json:
            try:
                raw = json.loads(row.payload_json)
                if isinstance(raw, dict):
                    parsed_payload = raw
            except (TypeError, ValueError, json.JSONDecodeError):
                parsed_payload = None
        realtime_payloads.append(
            (
                created["user_id"],
                {
                    "type": "notification_created",
                    "item": {
                        "id": row.id,
                        "event_type": row.event_type,
                        "title": row.title,
                        "message": row.message,
                        "route_id": row.route_id,
                        "point_id": row.point_id,
                        "is_read": row.is_read,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "payload": parsed_payload,
                    },
                },
            )
        )

    if realtime_payloads:
        _publish_realtime_notifications(realtime_payloads)

    from mobile_api.web_push_service import collect_subscriptions_for_users, send_web_push_to_users

    subs_by_user: dict[int, list[tuple[int, str, str, str]]] = {}
    for sub_id, user_id, endpoint, p256dh, auth in collect_subscriptions_for_users(db, unique_ids):
        subs_by_user.setdefault(user_id, []).append((sub_id, endpoint, p256dh, auth))

    for created in created_items:
        row: Notification = created["row"]
        subs = subs_by_user.get(created["user_id"], [])
        if subs:
            send_web_push_to_users(
                subscriptions=subs,
                title=title,
                body=message,
                notification_id=row.id,
            )


def _publish_realtime_notifications(payloads: list[tuple[int, dict[str, Any]]]) -> None:
    def _run() -> None:
        for user_id, payload in payloads:
            try:
                asyncio.run(notifications_realtime_hub.publish_to_user(user_id, payload))
            except Exception:
                continue

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def _route_recipients(db: Session, route: Route) -> list[int]:
    recipients: set[int] = set()
    if route.created_by_user_id:
        recipients.add(route.created_by_user_id)
    if route.assigned_user_id:
        recipients.add(route.assigned_user_id)
    manager_ids = db.scalars(
        select(User.id).where(User.role_code.in_(["admin", "superadmin", "logistic", "accountant"]))
    ).all()
    recipients.update(int(user_id) for user_id in manager_ids)
    return sorted(recipients)


def notify_route_created(db: Session, *, route: Route, actor_user: User | None) -> None:
    actor_name = (actor_user.full_name or actor_user.login) if actor_user else "Система"
    create_notification_for_users(
        db,
        user_ids=_route_recipients(db, route),
        event_type="route_created",
        title=f"Создан рейс {route.id}",
        message=f"{actor_name} создал(а) рейс {route.id}.",
        route_id=route.id,
        payload={"route_id": route.id},
        skip_user_ids=[actor_user.id] if actor_user else [],
    )


def notify_route_assigned(db: Session, *, route: Route, assigned_user: User | None, actor_user: User | None = None) -> None:
    assignee_name = (assigned_user.full_name or assigned_user.login) if assigned_user else "Водитель"
    create_notification_for_users(
        db,
        user_ids=_route_recipients(db, route),
        event_type="route_assigned",
        title=f"Назначение рейса {route.id}",
        message=f"Рейс {route.id} принят/назначен: {assignee_name}.",
        route_id=route.id,
        payload={"route_id": route.id, "assigned_user_id": assigned_user.id if assigned_user else None},
        skip_user_ids=[actor_user.id] if actor_user else [],
    )


def notify_route_cancelled(db: Session, *, route: Route, actor_user: User | None) -> None:
    actor_name = (actor_user.full_name or actor_user.login) if actor_user else "Система"
    create_notification_for_users(
        db,
        user_ids=_route_recipients(db, route),
        event_type="route_cancelled",
        title=f"Рейс {route.id} отменён",
        message=f"{actor_name} отменил(а) рейс {route.id}.",
        route_id=route.id,
        payload={"route_id": route.id},
        skip_user_ids=[actor_user.id] if actor_user else [],
    )


def notify_route_completed(db: Session, *, route: Route, actor_user: User | None) -> None:
    actor_name = (actor_user.full_name or actor_user.login) if actor_user else "Система"
    create_notification_for_users(
        db,
        user_ids=_route_recipients(db, route),
        event_type="route_completed",
        title=f"Рейс {route.id} завершён",
        message=f"{actor_name} завершил(а) рейс {route.id}.",
        route_id=route.id,
        payload={"route_id": route.id},
        skip_user_ids=[actor_user.id] if actor_user else [],
    )


def notify_point_status_changed(
    db: Session,
    *,
    route: Route,
    point: Point,
    actor_user: User | None,
    new_status: str,
) -> None:
    actor_name = (actor_user.full_name or actor_user.login) if actor_user else "Водитель"
    status_label = POINT_STATUS_LABELS_RU.get(new_status, new_status)
    point_label = point.point_name.strip() if point.point_name else point.place_point
    create_notification_for_users(
        db,
        user_ids=_route_recipients(db, route),
        event_type="point_status_changed",
        title=f"Точка рейса {route.id}: {status_label}",
        message=f"{actor_name} обновил(а) статус точки '{point_label}' до '{status_label}'.",
        route_id=route.id,
        point_id=point.id,
        payload={
            "route_id": route.id,
            "point_id": point.id,
            "point_label": point_label,
            "status": new_status,
        },
        skip_user_ids=[actor_user.id] if actor_user else [],
    )
