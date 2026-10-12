from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.daily_mileage_calc import (
    DAY_RE,
    aware,
    day_label_ru,
    is_correction,
    odo_km,
    suggested_days_from_readings,
    values_close,
)
from mobile_api.models import Point, RouteDailyMileage, User


def _point_readings(point: Point) -> list[tuple[datetime, float]]:
    pairs = [
        (aware(point.departure_time or point.time_accepted or point.time_departure), odo_km(point.departure_odometer)),
        (aware(point.registration_time or point.time_registration), odo_km(point.registration_odometer)),
        (aware(point.gate_time or point.time_put_on_gate), odo_km(point.gate_odometer)),
        (aware(point.docs_time or point.time_docs), odo_km(point.docs_odometer or point.odometer)),
    ]
    return [(dt, km) for dt, km in pairs if dt is not None and km is not None]


def collect_readings(points: list[Point]) -> list[tuple[datetime, float]]:
    rows: list[tuple[datetime, float]] = []
    for point in points:
        rows.extend(_point_readings(point))
    return rows


def suggested_days_from_points(points: list[Point]) -> list[dict[str, Any]]:
    return suggested_days_from_readings(collect_readings(points))


def _parse_edits(raw: str | None) -> list[dict[str, Any]]:
    text = (raw or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _day_out(suggested: dict[str, Any], row: RouteDailyMileage | None) -> dict[str, Any]:
    start = row.odometer_start if row is not None else suggested["odometer_start"]
    end = row.odometer_end if row is not None else suggested["odometer_end"]
    km = row.km if row is not None else suggested["km"]
    return {
        "day_msk": suggested["day_msk"],
        "day_label": day_label_ru(suggested["day_msk"]),
        "suggested_odometer_start": suggested["odometer_start"],
        "suggested_odometer_end": suggested["odometer_end"],
        "suggested_km": suggested["km"],
        "odometer_start": start,
        "odometer_end": end,
        "km": km,
        "status": row.status if row is not None else "pending",
        "confirmed_at": row.confirmed_at.isoformat() if row is not None and row.confirmed_at else None,
        "confirmed_by_user_id": row.confirmed_by_user_id if row is not None else None,
        "edits": _parse_edits(row.edits_json if row is not None else None),
    }


def daily_mileage_payload(db: Session, route_id: str, points: list[Point]) -> list[dict[str, Any]]:
    suggested = suggested_days_from_points(points)
    if not suggested:
        return []
    saved = {
        item.day_msk: item
        for item in db.scalars(
            select(RouteDailyMileage).where(RouteDailyMileage.route_id == route_id)
        ).all()
    }
    return [_day_out(item, saved.get(item["day_msk"])) for item in suggested]


def save_daily_mileage_confirmation(
    db: Session,
    *,
    route_id: str,
    points: list[Point],
    user: User,
    day_msk: str,
    odometer_start: float,
    odometer_end: float,
    km: int | None,
) -> tuple[RouteDailyMileage, dict[str, Any], bool]:
    day = (day_msk or "").strip()
    if not DAY_RE.match(day):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid day")

    suggested_list = suggested_days_from_points(points)
    suggested = next((item for item in suggested_list if item["day_msk"] == day), None)
    if suggested is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No odometer data for this day")

    start = float(odometer_start)
    end = float(odometer_end)
    if start < 0 or end < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Odometer cannot be negative")
    if end < start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End-of-day odometer is less than start-of-day",
        )
    km_value = int(round(end - start)) if km is None else int(km)
    if km_value < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Daily km cannot be negative")

    corrected = is_correction(suggested, start, end, km_value)
    row_status = "corrected" if corrected else "confirmed"
    now = datetime.now(timezone.utc)
    row = db.scalar(
        select(RouteDailyMileage).where(
            RouteDailyMileage.route_id == route_id,
            RouteDailyMileage.day_msk == day,
        )
    )
    unchanged = (
        row is not None
        and values_close(row.odometer_start, start)
        and values_close(row.odometer_end, end)
        and row.km == km_value
        and row.status == row_status
    )
    edit = {
        "at": now.isoformat(),
        "user_id": user.id,
        "odometer_start": start,
        "odometer_end": end,
        "km": km_value,
        "status": row_status,
        "suggested_odometer_start": suggested["odometer_start"],
        "suggested_odometer_end": suggested["odometer_end"],
        "suggested_km": suggested["km"],
    }
    if row is None:
        row = RouteDailyMileage(route_id=route_id, day_msk=day, edits_json=json.dumps([edit], ensure_ascii=False))
        db.add(row)
    elif not unchanged:
        history = _parse_edits(row.edits_json)
        history.append(edit)
        row.edits_json = json.dumps(history, ensure_ascii=False)

    row.suggested_odometer_start = suggested["odometer_start"]
    row.suggested_odometer_end = suggested["odometer_end"]
    row.suggested_km = suggested["km"]
    row.odometer_start = start
    row.odometer_end = end
    row.km = km_value
    row.status = row_status
    row.confirmed_by_user_id = user.id
    row.confirmed_at = now
    db.add(row)
    db.flush()
    return row, suggested, corrected and not unchanged
