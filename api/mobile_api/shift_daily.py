"""Daily technical maintenance checks during an active driver shift."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mobile_api.models import DriverShiftDailyCheck
from mobile_api.time_formatting import display_zone

STATUS_PENDING = "pending"
STATUS_DONE = "done"
STATUS_SKIPPED = "skipped"
NOTIFY_HOUR = 7
EVENT_DAILY_CHECK = "shift_daily_check"
EVENT_DAILY_FAULT = "shift_daily_fault"

DAILY_CHECKS: list[dict[str, str]] = [
    {"key": "tires", "name": "Шины"},
    {"key": "lights", "name": "Световые приборы"},
    {"key": "oil", "name": "Масло"},
    {"key": "coolant", "name": "Антифриз"},
    {"key": "brakes", "name": "Тормоза"},
    {"key": "clutch", "name": "Сцепление"},
    {"key": "tacho", "name": "Тахограф"},
    {"key": "reefer", "name": "Рефрижератор"},
]
DAILY_CHECK_KEYS = tuple(item["key"] for item in DAILY_CHECKS)
DAILY_CHECK_NAMES = {item["key"]: item["name"] for item in DAILY_CHECKS}


def empty_items() -> list[dict[str, Any]]:
    return [{"key": item["key"], "name": item["name"], "st": None, "note": ""} for item in DAILY_CHECKS]


def dump_items(items: list[dict[str, Any]]) -> str:
    return json.dumps(items, ensure_ascii=False)


def items_from_json(raw: str | None) -> list[dict[str, Any]]:
    if not (raw or "").strip():
        return empty_items()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return empty_items()
    if not isinstance(parsed, list) or not parsed:
        return empty_items()
    by_key = {str(item.get("key") or ""): item for item in parsed if isinstance(item, dict)}
    out: list[dict[str, Any]] = []
    for spec in DAILY_CHECKS:
        src = by_key.get(spec["key"]) or {}
        st = src.get("st")
        if st not in ("ok", "bad"):
            st = None
        out.append(
            {
                "key": spec["key"],
                "name": spec["name"],
                "st": st,
                "note": str(src.get("note") or "").strip(),
            }
        )
    return out


def normalize_complete_items(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError("Отметьте все пункты проверки")
    by_key: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if key not in DAILY_CHECK_NAMES:
            continue
        st = item.get("st")
        if st not in ("ok", "bad"):
            raise ValueError("Отметьте каждый пункт: норма или неисправно")
        note = str(item.get("note") or "").strip()
        if st == "bad" and not note:
            note = ""
        by_key[key] = {
            "key": key,
            "name": DAILY_CHECK_NAMES[key],
            "st": st,
            "note": note,
        }
    if len(by_key) != len(DAILY_CHECK_KEYS):
        raise ValueError("Отметьте все пункты проверки")
    return [
        by_key[spec["key"]]
        if spec["key"] in by_key
        else {"key": spec["key"], "name": spec["name"], "st": None, "note": ""}
        for spec in DAILY_CHECKS
    ]


def fault_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if item.get("st") == "bad"]


def local_now(now: datetime | None = None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(display_zone())


def due_check_date(shift_started_at: datetime | None, now: datetime | None = None) -> date | None:
    """Calendar day for a daily check: next local days after intake, from 07:00 Moscow."""
    if shift_started_at is None:
        return None
    local = local_now(now)
    started = shift_started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    start_date = started.astimezone(display_zone()).date()
    today = local.date()
    if today <= start_date:
        return None
    if local.hour < NOTIFY_HOUR:
        return None
    return today


def daily_check_out(row: DriverShiftDailyCheck) -> dict[str, Any]:
    items = items_from_json(row.checks_json)
    return {
        "id": row.id,
        "shift_id": row.shift_id,
        "check_date": row.check_date.isoformat() if row.check_date else None,
        "status": row.status,
        "items": items,
        "notified_at": row.notified_at.isoformat() if row.notified_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "skipped_at": row.skipped_at.isoformat() if row.skipped_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "has_fault": bool(fault_items(items)) if row.status == STATUS_DONE else False,
    }


def get_by_shift_date(db: Session, shift_id: int, check_date: date) -> DriverShiftDailyCheck | None:
    return db.scalars(
        select(DriverShiftDailyCheck).where(
            DriverShiftDailyCheck.shift_id == shift_id,
            DriverShiftDailyCheck.check_date == check_date,
        )
    ).first()


def list_for_shift(db: Session, shift_id: int) -> list[DriverShiftDailyCheck]:
    return list(
        db.scalars(
            select(DriverShiftDailyCheck)
            .where(DriverShiftDailyCheck.shift_id == shift_id)
            .order_by(DriverShiftDailyCheck.check_date.desc(), DriverShiftDailyCheck.id.desc())
        ).all()
    )


def oldest_pending(db: Session, shift_id: int) -> DriverShiftDailyCheck | None:
    return db.scalars(
        select(DriverShiftDailyCheck)
        .where(
            DriverShiftDailyCheck.shift_id == shift_id,
            DriverShiftDailyCheck.status == STATUS_PENDING,
        )
        .order_by(DriverShiftDailyCheck.check_date.asc(), DriverShiftDailyCheck.id.asc())
        .limit(1)
    ).first()


def get_or_create_pending(db: Session, shift_id: int, check_date: date) -> DriverShiftDailyCheck:
    existing = get_by_shift_date(db, shift_id, check_date)
    if existing:
        return existing
    row = DriverShiftDailyCheck(
        shift_id=shift_id,
        check_date=check_date,
        status=STATUS_PENDING,
        checks_json=dump_items(empty_items()),
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
        return row
    except IntegrityError:
        found = get_by_shift_date(db, shift_id, check_date)
        if found:
            return found
        raise
