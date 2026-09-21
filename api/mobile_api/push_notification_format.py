from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from mobile_api.models import Point

COMPLETED_POINT_STATUSES = {"docs", "success"}
_PUSH_POINT_ADDRESS_MAX_LEN = 60


def brief_point_address(
    *,
    point_name: str | None = None,
    place_point: str | None = None,
    max_len: int = _PUSH_POINT_ADDRESS_MAX_LEN,
) -> str:
    label = (point_name or "").strip() or (place_point or "").strip()
    label = " ".join(label.split())
    if not label:
        return ""
    if len(label) <= max_len:
        return label
    return f"{label[: max_len - 1]}…"


def format_push_context_line(
    *,
    driver_fio: str | None = None,
    vehicle_no: str | None = None,
    point_address: str | None = None,
) -> str:
    parts: list[str] = []
    fio = (driver_fio or "").strip()
    if fio:
        parts.append(fio)
    vehicle = (vehicle_no or "").strip()
    if vehicle:
        parts.append(f"ТС {vehicle}")
    address = (point_address or "").strip()
    if address:
        parts.append(address)
    return " · ".join(parts)


def build_push_body(message: str, context_line: str | None = None) -> str:
    base = (message or "").strip()
    ctx = (context_line or "").strip()
    if not ctx:
        return base
    if not base:
        return ctx
    return f"{base}\n{ctx}"


def _ordered_points(db: "Session", route_id: str) -> "list[Point]":
    from sqlalchemy import select

    from mobile_api.models import Point, RoutePoint
    point_ids = db.scalars(
        select(RoutePoint.point_id).where(RoutePoint.route_id == route_id).order_by(RoutePoint.order_index.asc())
    ).all()
    if point_ids:
        rows = db.scalars(select(Point).where(Point.id.in_(point_ids))).all()
        by_id = {row.id: row for row in rows}
        return [by_id[pid] for pid in point_ids if pid in by_id]
    return list(db.scalars(select(Point).where(Point.route_id == route_id).order_by(Point.id.asc())).all())


def _active_point_for_route(db: "Session", route_id: str) -> "Point | None":
    points = _ordered_points(db, route_id)
    active = next((point for point in points if point.status not in COMPLETED_POINT_STATUSES), None)
    return active or (points[-1] if points else None)


def resolve_push_context_line(db: "Session", *, route_id: str | None, point_id: int | None = None) -> str:
    from mobile_api.models import Point, Route, User
    from services.wialon_service import vehicle_number_for_wialon

    if not route_id:
        return ""
    route = db.get(Route, route_id)
    if route is None:
        return ""

    driver_fio = ""
    if route.assigned_user_id:
        driver = db.get(User, route.assigned_user_id)
        if driver:
            driver_fio = (driver.full_name or driver.login or "").strip()

    vehicle_no = vehicle_number_for_wialon(route.number_auto, route.registration_number)

    point: "Point | None" = None
    if point_id is not None:
        point = db.get(Point, point_id)
    if point is None:
        point = _active_point_for_route(db, route_id)

    point_address = ""
    if point is not None:
        point_address = brief_point_address(point_name=point.point_name, place_point=point.place_point)

    return format_push_context_line(
        driver_fio=driver_fio,
        vehicle_no=vehicle_no,
        point_address=point_address,
    )
