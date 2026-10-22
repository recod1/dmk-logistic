"""Create PWA routes from the legacy 1C endpoint POST /api/route."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mobile_api.models import Route, User
from mobile_api.roles import RoleCode
from mobile_api.route_notification_logic import notify_route_assigned
from utils.onec_datetime import planned_wall_fields

logger = logging.getLogger(__name__)


def _find_driver(db: Session, *, driver_name: str | None, driver_tg_id: int | None) -> User:
    if driver_tg_id is not None:
        user = db.scalar(
            select(User).where(
                User.legacy_tg_id == str(driver_tg_id),
                User.is_active.is_(True),
            )
        )
        if user is None:
            raise HTTPException(status_code=404, detail=f"Driver with tg_id {driver_tg_id} not found")
        if user.role_code != RoleCode.DRIVER.value:
            raise HTTPException(status_code=400, detail="User must be a driver")
        return user

    name = (driver_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Provide driver_name or driver_tg_id")
    rows = db.scalars(
        select(User).where(
            User.role_code == RoleCode.DRIVER.value,
            User.is_active.is_(True),
            func.lower(func.coalesce(User.full_name, "")) == name.lower(),
        )
    ).all()
    if len(rows) == 1:
        return rows[0]
    if not rows:
        raise HTTPException(status_code=404, detail=f"Driver with name '{name}' not found")
    raise HTTPException(
        status_code=400,
        detail=f"Driver with name '{name}' is not unique. Use driver_tg_id.",
    )


def create_route_from_integration(db: Session, route_data: Any) -> dict:
    from mobile_api.admin_routes_router import (
        AdminRoutePointCreate,
        _apply_points_replace,
        _default_logist_contacts,
        _route_out,
        _store_route_plates,
    )

    route_id = (route_data.route_id or "").strip()
    if not route_id:
        raise HTTPException(status_code=400, detail="route_id is required")

    existing = db.get(Route, route_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Route with id '{route_id}' already exists")

    driver = _find_driver(
        db,
        driver_name=getattr(route_data, "driver_name", None),
        driver_tg_id=getattr(route_data, "driver_tg_id", None),
    )
    legacy_driver_tg_id = int(driver.legacy_tg_id) if (driver.legacy_tg_id or "").isdigit() else None
    number_auto, trailer_number = _store_route_plates(
        db,
        number_auto=(getattr(route_data, "number_auto", None) or "").strip(),
        trailer_number=(getattr(route_data, "trailer_number", None) or "").strip(),
        strict=False,
    )

    stored_points: list[dict[str, str]] = []
    points_payload: list[AdminRoutePointCreate] = []
    for index, point in enumerate(getattr(route_data, "points", None) or []):
        raw_date = getattr(point, "date_point", None)
        raw_time = getattr(point, "point_time", None)
        date_point, point_time = planned_wall_fields(raw_date, raw_time)
        type_point = (getattr(point, "type_point", None) or "").strip().lower()
        if type_point not in {"loading", "unloading"}:
            type_point = "loading"
        logger.info(
            "legacy /api/route %s point[%s] raw date_point=%r point_time=%r stored date=%s time=%s",
            route_id,
            index,
            raw_date,
            raw_time,
            date_point,
            point_time,
        )
        stored_points.append(
            {
                "type_point": type_point,
                "date_raw": "" if raw_date is None else str(raw_date),
                "time_raw": "" if raw_time is None else str(raw_time),
                "date_point": date_point,
                "point_time": point_time,
            }
        )
        points_payload.append(
            AdminRoutePointCreate(
                type_point=type_point,
                place_point=(getattr(point, "place_point", None) or "").strip() or "—",
                date_point=date_point or (str(raw_date or "").strip()[:64] or "—"),
                point_time=point_time,
                order_index=index,
            )
        )

    route = Route(
        id=route_id,
        legacy_driver_tg_id=legacy_driver_tg_id,
        assigned_user_id=driver.id,
        created_by_user_id=None,
        status="new",
        number_auto=number_auto,
        temperature=(getattr(route_data, "temperature", None) or "").strip(),
        dispatcher_contacts=(getattr(route_data, "dispatcher_contacts", None) or "").strip(),
        logist_contacts=_default_logist_contacts(db),
        registration_number=(getattr(route_data, "registration_number", None) or "").strip(),
        trailer_number=trailer_number,
    )
    db.add(route)
    db.flush()
    if points_payload:
        _apply_points_replace(db, route, points_payload)
    notify_route_assigned(db, route=route, assigned_user=driver, actor_user=None)
    db.flush()
    out = _route_out(db, route, include_points=True)
    return {
        "id": route_id,
        "message": "Route created successfully",
        "points_count": len(points_payload),
        "points": stored_points,
        "route": {"id": out.get("id"), "status": out.get("status")},
    }
