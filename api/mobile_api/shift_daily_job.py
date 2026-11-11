from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.db import SessionLocal
from mobile_api.models import DriverShift, User
from mobile_api.notifications_service import create_notification_for_users
from mobile_api.shift_daily import (
    EVENT_DAILY_CHECK,
    STATUS_PENDING,
    due_check_date,
    get_or_create_pending,
)
from mobile_api.shift_inspection import WORKFLOW_ACTIVE
from mobile_api.time_formatting import format_dt_for_app

logger = logging.getLogger(__name__)
LOOP_INTERVAL_SEC = 300


def _driver_label(db: Session, shift: DriverShift) -> str:
    name = (getattr(shift, "driver_name", None) or "").strip()
    if name:
        return name
    row = db.get(User, shift.driver_user_id)
    if row is None:
        return "Водитель"
    return (row.full_name or row.login or "Водитель").strip()


def scan_shift_daily_checks(db: Session, now: datetime | None = None) -> int:
    moment = now or datetime.now(timezone.utc)
    shifts = db.scalars(
        select(DriverShift).where(
            DriverShift.workflow_status == WORKFLOW_ACTIVE,
            DriverShift.ended_at.is_(None),
        )
    ).all()
    sent = 0
    for shift in shifts:
        check_date = due_check_date(shift.started_at, moment)
        if check_date is None:
            continue
        row = get_or_create_pending(db, shift.id, check_date)
        if row.status != STATUS_PENDING or row.notified_at is not None:
            continue
        name = _driver_label(db, shift)
        truck = (shift.truck or "").strip()
        date_label = check_date.strftime("%d.%m.%Y")
        create_notification_for_users(
            db,
            user_ids=[shift.driver_user_id],
            event_type=EVENT_DAILY_CHECK,
            title="Ежедневное техобслуживание",
            message=(
                f"Проверьте ТС за {date_label}"
                + (f" · {truck}" if truck else "")
                + f" · {name}"
            ).strip(" ·"),
            payload={
                "shift_id": shift.id,
                "check_id": row.id,
                "check_date": check_date.isoformat(),
                "driver_user_id": shift.driver_user_id,
                "driver_full_name": name,
            },
        )
        row.notified_at = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
        sent += 1
    if sent:
        db.commit()
    return sent


async def run_shift_daily_check_loop() -> None:
    await asyncio.sleep(25)
    while True:
        try:
            with SessionLocal() as db:
                sent = scan_shift_daily_checks(db)
                if sent:
                    logger.info("shift_daily_check sent=%s at %s", sent, format_dt_for_app(datetime.now(timezone.utc)))
        except Exception:
            logger.exception("shift_daily_check scan failed")
        await asyncio.sleep(LOOP_INTERVAL_SEC)
