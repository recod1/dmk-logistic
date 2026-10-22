"""Driver app presence (last seen + last coordinates)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from mobile_api.db import SessionLocal
from mobile_api.models import DriverPresenceSample, User
from mobile_api.roles import RoleCode
from mobile_api.time_formatting import format_dt_for_app

ONLINE_AFTER = timedelta(seconds=90)
RECENT_AFTER = timedelta(minutes=3)
_last_presence_ping_at: dict[int, datetime] = {}
PRESENCE_PING_COOLDOWN = timedelta(seconds=20)
HISTORY_KEEP = timedelta(days=14)
SAMPLE_INTERVAL_SEC = 300
logger = logging.getLogger(__name__)


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


def availability_status(status: str) -> str:
    if status in {"online", "recent"}:
        return "online"
    return "offline"


def connection_label(status: str) -> str:
    if availability_status(status) == "online":
        return "Доступен"
    return "Недоступен"


def queue_presence_probes(db: Session, drivers: list[User]) -> None:
    """Wake driver apps (even minimized) so last_seen reflects real internet, not UI activity."""
    now = now_utc()
    stale_ids: list[int] = []
    for driver in drivers:
        if connection_status(driver.last_seen_at, now=now) == "online":
            continue
        prev = _last_presence_ping_at.get(int(driver.id))
        if prev and now - prev < PRESENCE_PING_COOLDOWN:
            continue
        _last_presence_ping_at[int(driver.id)] = now
        stale_ids.append(int(driver.id))
    if not stale_ids:
        return
    from mobile_api.web_push_service import collect_subscriptions_for_users, send_web_push_to_users

    rows = collect_subscriptions_for_users(db, stale_ids)
    subs = [(sub_id, endpoint, p256dh, auth) for sub_id, _user_id, endpoint, p256dh, auth in rows]
    if not subs:
        return
    send_web_push_to_users(
        subscriptions=subs,
        title="",
        body="",
        extra={"event_type": "presence_ping", "silent": True, "sync": "presence"},
        ttl=45,
    )


def presence_fields(user: User) -> dict:
    status = availability_status(connection_status(user.last_seen_at))
    return {
        "last_seen_at": format_dt_for_app(user.last_seen_at),
        "connection_status": status,
        "connection_label": connection_label(status),
        "last_lat": user.last_lat,
        "last_lng": user.last_lng,
        "last_location_at": format_dt_for_app(user.last_location_at),
    }


def _sample_out(row: DriverPresenceSample) -> dict:
    status = availability_status(row.connection_status)
    return {
        "id": int(row.id),
        "recorded_at": format_dt_for_app(row.recorded_at),
        "connection_status": status,
        "connection_label": connection_label(status),
        "last_seen_at": format_dt_for_app(row.last_seen_at),
        "lat": row.lat,
        "lng": row.lng,
        "location_at": format_dt_for_app(row.location_at),
    }


def list_presence_history(db: Session, user_id: int, *, limit: int = 500) -> list[dict]:
    rows = db.scalars(
        select(DriverPresenceSample)
        .where(DriverPresenceSample.user_id == int(user_id))
        .order_by(DriverPresenceSample.recorded_at.desc(), DriverPresenceSample.id.desc())
        .limit(limit)
    ).all()
    return [_sample_out(row) for row in rows]


def snapshot_all_drivers(db: Session) -> int:
    drivers = db.scalars(
        select(User).where(User.role_code == RoleCode.DRIVER.value, User.is_active.is_(True))
    ).all()
    now = now_utc()
    db.execute(delete(DriverPresenceSample).where(DriverPresenceSample.recorded_at < now - HISTORY_KEEP))
    for driver in drivers:
        status = availability_status(connection_status(driver.last_seen_at, now=now))
        db.add(
            DriverPresenceSample(
                user_id=int(driver.id),
                recorded_at=now,
                connection_status=status,
                last_seen_at=driver.last_seen_at,
                lat=driver.last_lat,
                lng=driver.last_lng,
                location_at=driver.last_location_at,
            )
        )
    queue_presence_probes(db, list(drivers))
    db.commit()
    return len(drivers)


async def run_presence_history_loop() -> None:
    await asyncio.sleep(25)
    while True:
        try:
            with SessionLocal() as db:
                count = snapshot_all_drivers(db)
                logger.info("driver presence snapshot count=%s", count)
        except Exception:
            logger.exception("driver presence snapshot failed")
        await asyncio.sleep(SAMPLE_INTERVAL_SEC)
