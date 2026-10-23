"""Late arrival vs planned point time. Grace is minutes after plan; 0 means any later clock is late."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from utils.onec_datetime import normalize_planned_time, planned_wall_datetime

LATE_GRACE_MINUTES = 0
LateKind = Literal["", "risk", "fact"]


def _aware(value: datetime, fallback_tz) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=fallback_tz or timezone.utc)
    return value


def eta_datetime(date_point: str | None, point_time: str | None, eta_raw: str | None) -> datetime | None:
    planned = planned_wall_datetime(date_point, point_time)
    eta = normalize_planned_time(eta_raw)
    if planned is None or not eta:
        return None
    hour_s, minute_s = eta.split(":", 1)
    try:
        hour = int(hour_s)
        minute = int(minute_s[:2])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return planned.replace(hour=hour, minute=minute, second=0, microsecond=0)


def is_later_than_plan(actual: datetime | None, planned: datetime | None, *, grace_minutes: int = LATE_GRACE_MINUTES) -> bool:
    if actual is None or planned is None:
        return False
    left = _aware(actual, planned.tzinfo)
    right = _aware(planned, actual.tzinfo)
    return left > right + timedelta(minutes=max(0, int(grace_minutes)))


def eta_is_late(date_point: str | None, point_time: str | None, eta_raw: str | None) -> bool:
    planned = planned_wall_datetime(date_point, point_time)
    actual = eta_datetime(date_point, point_time, eta_raw)
    return is_later_than_plan(actual, planned)


def registration_is_late(
    occurred_at: datetime | None,
    date_point: str | None,
    point_time: str | None,
) -> bool:
    planned = planned_wall_datetime(date_point, point_time)
    return is_later_than_plan(occurred_at, planned)


def late_reason_required(
    *,
    to_status: str,
    date_point: str | None,
    point_time: str | None,
    eta_raw: str | None,
    occurred_at: datetime | None,
) -> bool:
    if to_status == "process":
        eta = (eta_raw or "").strip()
        return bool(eta) and eta_is_late(date_point, point_time, eta)
    if to_status == "registration":
        return registration_is_late(occurred_at, date_point, point_time)
    return False


_LATE_LINE_RE = re.compile(r"(?=Причина опоздания\s*\([^)]+\):)")
_LATE_PREFIX_RE = re.compile(r"^Причина опоздания\s*\([^)]+\):\s*")


def late_reason_lines(raw: str | None) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    lines: list[str] = []
    for chunk in re.split(r"\n+", text):
        piece = chunk.strip()
        if not piece:
            continue
        bits = [item.strip() for item in _LATE_LINE_RE.split(piece) if item.strip()]
        lines.extend(bits or [piece])
    return lines


def last_late_reason_text(raw: str | None) -> str:
    lines = late_reason_lines(raw)
    if not lines:
        return ""
    cleaned = _LATE_PREFIX_RE.sub("", lines[-1]).strip()
    return cleaned or lines[-1]


def apply_late_reason(point, reason: str, label: str) -> None:
    text = _LATE_PREFIX_RE.sub("", (reason or "").strip()).strip()
    if not text:
        text = last_late_reason_text(getattr(point, "late_reason", None))
    if not text:
        return
    line = f"{label}: {text}"
    existing = (getattr(point, "late_reason", None) or "").strip()
    if line not in existing:
        setattr(point, "late_reason", f"{existing}\n{line}".strip() if existing else line)
    note = (getattr(point, "point_note", None) or "").strip()
    if line not in note:
        setattr(point, "point_note", f"{note}\n{line}".strip() if note else line)


def point_late_kind(point) -> LateKind:
    date_point = getattr(point, "date_point", None)
    point_time = getattr(point, "point_time", None)
    eta = (getattr(point, "estimated_arrival", None) or "").strip()
    registration = getattr(point, "registration_time", None) or getattr(point, "time_registration", None)
    if registration_is_late(registration, date_point, point_time):
        return "fact"
    if eta and eta_is_late(date_point, point_time, eta) and registration is None:
        return "risk"
    return ""
