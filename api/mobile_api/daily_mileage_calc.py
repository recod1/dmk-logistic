from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ODO_RE = re.compile(r"(-?\d+(?:[.,]\d+)?)")


def aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def odo_km(raw: str | None) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    match = ODO_RE.search(text.replace("\u00a0", " "))
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def day_label_ru(day_msk: str) -> str:
    parts = (day_msk or "").split("-")
    if len(parts) != 3:
        return day_msk
    return f"{parts[2]}.{parts[1]}.{parts[0]}"


def values_close(left: float | None, right: float | None, *, tol: float = 0.51) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    return abs(float(left) - float(right)) < tol


def suggested_days_from_readings(readings: list[tuple[datetime, float]]) -> list[dict[str, Any]]:
    rows: list[tuple[datetime, float]] = []
    for dt, km in readings:
        converted = aware(dt)
        if converted is None:
            continue
        rows.append((converted.astimezone(MSK), float(km)))
    rows.sort(key=lambda item: item[0])
    if not rows:
        return []

    days: list[datetime] = []
    seen: set[str] = set()
    for dt, _km in rows:
        key = dt.date().isoformat()
        if key not in seen:
            seen.add(key)
            days.append(dt)

    result: list[dict[str, Any]] = []
    for sample in days:
        day = sample.date()
        day_start = datetime(day.year, day.month, day.day, tzinfo=MSK)
        in_day = [(t, km) for t, km in rows if t.date() == day]
        before = [(t, km) for t, km in rows if t < day_start]
        if not in_day:
            continue
        start = before[-1][1] if before else in_day[0][1]
        end = in_day[-1][1]
        km_value = int(round(end - start)) if end >= start else None
        result.append(
            {
                "day_msk": day.isoformat(),
                "odometer_start": start,
                "odometer_end": end,
                "km": km_value,
            }
        )
    return result


def is_correction(suggested: dict[str, Any], start: float, end: float, km: int) -> bool:
    return not (
        values_close(start, suggested.get("odometer_start"))
        and values_close(end, suggested.get("odometer_end"))
        and suggested.get("km") is not None
        and int(suggested["km"]) == int(km)
    )
