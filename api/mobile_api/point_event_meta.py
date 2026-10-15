from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.models import RouteEvent
from mobile_api.time_formatting import format_pressed_if_differs

STAGE_STATUSES = frozenset({"process", "registration", "load", "docs"})


def load_point_event_meta(db: Session, point_ids: list[int]) -> dict[int, dict[str, dict[str, str]]]:
    """point_id -> status -> {time_source, pressed_at} from the latest applied event."""
    out: dict[int, dict[str, dict[str, str]]] = defaultdict(dict)
    if not point_ids:
        return out
    rows = db.scalars(
        select(RouteEvent)
        .where(
            RouteEvent.point_id.in_(point_ids),
            RouteEvent.applied.is_(True),
        )
        .order_by(RouteEvent.server_received_at.desc(), RouteEvent.id.desc())
    ).all()
    for ev in rows:
        if ev.point_id is None or ev.to_status not in STAGE_STATUSES:
            continue
        bucket = out[int(ev.point_id)]
        status = str(ev.to_status)
        if status in bucket:
            continue
        meta: dict[str, str] = {}
        source = str(ev.time_source or "").strip()
        # device / Moscow clock is the default — only non-default sources go to the UI.
        if source and source != "device":
            meta["time_source"] = source
        pressed = format_pressed_if_differs(ev.occurred_at_client, getattr(ev, "pressed_at_client", None))
        if pressed:
            meta["pressed_at"] = pressed
        bucket[status] = meta
    return out


def stage_meta_fields(meta: dict[str, dict[str, str]] | None) -> dict[str, str | None]:
    data = meta or {}
    process = data.get("process") or {}
    registration = data.get("registration") or {}
    load = data.get("load") or {}
    docs = data.get("docs") or {}
    return {
        "departure_time_source": process.get("time_source"),
        "departure_pressed_at": process.get("pressed_at"),
        "registration_time_source": registration.get("time_source"),
        "registration_pressed_at": registration.get("pressed_at"),
        "gate_time_source": load.get("time_source"),
        "gate_pressed_at": load.get("pressed_at"),
        "docs_time_source": docs.get("time_source"),
        "docs_pressed_at": docs.get("pressed_at"),
    }
