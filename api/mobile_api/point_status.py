"""Effective point status: stored field plus filled stage timestamps."""

from __future__ import annotations

COMPLETED_POINT_STATUSES = frozenset({"docs", "success"})

POINT_STATUS_RANK = {
    "new": 0,
    "process": 1,
    "registration": 2,
    "load": 3,
    "docs": 4,
    "success": 4,
}


def normalize_point_status(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw == "success":
        return "docs"
    if raw in POINT_STATUS_RANK:
        return raw
    return "new"


def inferred_point_status(point) -> str:
    status = "new"
    if (
        getattr(point, "departure_time", None)
        or getattr(point, "time_accepted", None)
        or getattr(point, "time_departure", None)
    ):
        status = "process"
    if getattr(point, "registration_time", None) or getattr(point, "time_registration", None):
        status = "registration"
    if getattr(point, "gate_time", None) or getattr(point, "time_put_on_gate", None):
        status = "load"
    if getattr(point, "docs_time", None) or getattr(point, "time_docs", None):
        status = "docs"
    return status


def effective_point_status(point) -> str:
    stored = normalize_point_status(getattr(point, "status", None))
    inferred = inferred_point_status(point)
    if POINT_STATUS_RANK.get(inferred, 0) > POINT_STATUS_RANK.get(stored, 0):
        return inferred
    return stored


def point_is_completed(point) -> bool:
    return effective_point_status(point) in COMPLETED_POINT_STATUSES
