"""Driver app presence (last seen + last coordinates)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from mobile_api.db import SessionLocal
from mobile_api.models import User
from mobile_api.time_formatting import format_dt_for_app

ONLINE_AFTER = timedelta(seconds=45)
RECENT_AFTER = timedelta(minutes=5)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def apply_user_presence(
    db: Session,
    user: User,
    *,
    lat: float | None = None,
    lng: float | None = None,
) -> None:
    stamp = now_utc()
    user.last_seen_at = stamp
    if lat is not None and lng is not None:
        user.last_lat = float(lat)
        user.last_lng = float(lng)
        user.last_location_at = stamp
    db.add(user)


def touch_user_seen(user_id: int, *, lat: float | None = None, lng: float | None = None) -> None:
    try:
        with SessionLocal() as db:
            user = db.get(User, int(user_id))
            if user is None:
                return
            apply_user_presence(db, user, lat=lat, lng=lng)
            db.commit()
    except Exception:
        return


def connection_status(last_seen_at: datetime | None, *, now: datetime | None = None) -> str:
    if last_seen_at is None:
        return "offline"
    stamp = last_seen_at
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    age = (now or now_utc()) - stamp
    if age <= ONLINE_AFTER:
        return "online"
    if age <= RECENT_AFTER:
        return "recent"
    return "offline"


def connection_label(status: str) -> str:
    if status == "online":
        return "В сети"
    if status == "recent":
        return "Недавно"
    return "Не в сети"


def presence_fields(user: User) -> dict:
    status = connection_status(user.last_seen_at)
    return {
        "last_seen_at": format_dt_for_app(user.last_seen_at),
        "connection_status": status,
        "connection_label": connection_label(status),
        "last_lat": user.last_lat,
        "last_lng": user.last_lng,
        "last_location_at": format_dt_for_app(user.last_location_at),
    }
