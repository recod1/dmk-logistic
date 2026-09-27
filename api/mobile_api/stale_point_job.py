from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.db import SessionLocal
from mobile_api.models import Notification, Point, Route, RoutePoint
from mobile_api.notifications_service import create_notification_for_users
from mobile_api.route_notification_logic import (
    POINT_STATUS_LABELS_RU,
    _manager_ids,
    _point_event_time,
)

logger = logging.getLogger(__name__)

STALE_STATUSES = frozenset({"process", "registration", "load"})
STALE_AFTER = timedelta(minutes=60)
DEDUP_WINDOW = timedelta(minutes=55)
LOOP_INTERVAL_SEC = 300


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _duration_label(delta: timedelta) -> str:
    total_min = max(int(delta.total_seconds() // 60), 0)
    hours, minutes = divmod(total_min, 60)
    if hours and minutes:
        return f"{hours} ч {minutes} мин"
    if hours:
        return f"{hours} ч"
    return f"{minutes} мин"


def _payload_status(payload_json: str | None) -> str:
    if not payload_json:
        return ""
    try:
        raw = json.loads(payload_json)
    except json.JSONDecodeError:
        return ""
    if isinstance(raw, dict):
        return str(raw.get("status") or "")
    return ""


def _recent_stale_exists(db: Session, *, route_id: str, point_id: int, status_value: str, since: datetime) -> bool:
    rows = db.scalars(
        select(Notification).where(
            Notification.event_type == "point_status_stale",
            Notification.route_id == route_id,
            Notification.point_id == point_id,
            Notification.created_at >= since,
        )
    ).all()
    return any(_payload_status(row.payload_json) == status_value for row in rows)


def _active_points(db: Session, route_id: str) -> list[Point]:
    point_ids = list(db.scalars(select(RoutePoint.point_id).where(RoutePoint.route_id == route_id)).all())
    if not point_ids:
        return []
    return list(
        db.scalars(
            select(Point)
            .where(Point.id.in_(point_ids), Point.route_id == route_id)
            .order_by(Point.order_index.asc(), Point.id.asc())
        ).all()
    )


def scan_stale_points(db: Session, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    cutoff = now - STALE_AFTER
    dedup_since = now - DEDUP_WINDOW
    routes = db.scalars(select(Route).where(Route.status == "process")).all()
    sent = 0
    manager_ids = _manager_ids(db)
    for route in routes:
        points = _active_points(db, route.id)
        active = next((p for p in points if (p.status or "") in STALE_STATUSES), None)
        if active is None:
            continue
        started = _aware(_point_event_time(active, active.status))
        if started is None or started > cutoff:
            continue
        if _recent_stale_exists(db, route_id=route.id, point_id=int(active.id), status_value=active.status, since=dedup_since):
            continue
        recipients = list(manager_ids)
        if route.created_by_user_id:
            recipients.append(int(route.created_by_user_id))
        skip = [int(route.assigned_user_id)] if route.assigned_user_id else []
        status_label = POINT_STATUS_LABELS_RU.get(active.status, active.status)
        duration = _duration_label(now - started)
        point_type = "загрузка" if (active.type_point or "") == "loading" else "выгрузка"
        address = (active.place_point or "").strip() or (active.point_name or "").strip() or "точка"
        create_notification_for_users(
            db,
            user_ids=recipients,
            event_type="point_status_stale",
            title="Водитель стоит на этапе",
            message=(
                f"Рейс {route.id} · водитель стоит на {status_label} · {duration} · {point_type} · {address}"
            ),
            route_id=route.id,
            point_id=int(active.id),
            payload={
                "route_id": route.id,
                "point_id": int(active.id),
                "status": active.status,
                "point_name": (active.point_name or "").strip(),
                "place_point": (active.place_point or "").strip(),
                "duration": duration,
            },
            skip_user_ids=skip,
        )
        sent += 1
    if sent:
        db.commit()
    return sent


async def run_stale_point_loop() -> None:
    await asyncio.sleep(20)
    while True:
        try:
            with SessionLocal() as db:
                sent = scan_stale_points(db)
                if sent:
                    logger.info("point_status_stale sent=%s", sent)
        except Exception:
            logger.exception("point_status_stale scan failed")
        await asyncio.sleep(LOOP_INTERVAL_SEC)
