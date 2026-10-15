from __future__ import annotations

from datetime import datetime, timezone

from utils.onec_datetime import planned_wall_datetime


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def stale_anchor_started(
    *,
    status_value: str,
    fact: datetime | None,
    date_point: str | None = None,
    point_time: str | None = None,
    fallback: datetime | None = None,
) -> datetime | None:
    """Moment from which the 1-hour stale wait is counted."""
    fact_aware = _aware(fact)
    fallback_aware = _aware(fallback)
    if status_value == "registration":
        planned = planned_wall_datetime(date_point, point_time)
        if planned is not None:
            planned_utc = planned.astimezone(timezone.utc)
            if fact_aware is not None:
                return max(fact_aware, planned_utc)
            return planned_utc
    return fact_aware or fallback_aware
