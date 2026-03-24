from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_route_manager
from mobile_api.db import get_db
from mobile_api.models import Point, Route, RoutePoint, User
from mobile_api.roles import RoleCode, role_label_ru


router = APIRouter(prefix="/v1/admin/routes", tags=["admin-routes"])


class AdminRoutePointCreate(BaseModel):
    type_point: str = Field(min_length=1, max_length=32)
    place_point: str = Field(min_length=1, max_length=2000)
    date_point: str = Field(min_length=1, max_length=64)
    order_index: int | None = Field(default=None, ge=0)


class AdminRouteCreatePayload(BaseModel):
    route_id: str = Field(min_length=1, max_length=64)
    driver_user_id: int
    number_auto: str = ""
    temperature: str = ""
    dispatcher_contacts: str = ""
    registration_number: str = ""
    trailer_number: str = ""
    points: list[AdminRoutePointCreate] = Field(default_factory=list, max_items=200)


class AssignDriverPayload(BaseModel):
    driver_user_id: int


def _route_points(db: Session, route_id: str) -> list[Point]:
    ordered_ids = db.scalars(
        select(RoutePoint.point_id).where(RoutePoint.route_id == route_id).order_by(RoutePoint.order_index.asc())
    ).all()
    if not ordered_ids:
        return []
    points = db.scalars(select(Point).where(Point.id.in_(ordered_ids))).all()
    points_map = {point.id: point for point in points}
    return [points_map[point_id] for point_id in ordered_ids if point_id in points_map]


def _driver_out(user: User | None) -> dict | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "login": user.login,
        "full_name": user.full_name,
        "phone": user.phone,
        "role_code": user.role_code,
        "role_label": role_label_ru(user.role_code),
        "is_active": user.is_active,
    }


def _point_out(point: Point, order_index: int) -> dict:
    return {
        "id": point.id,
        "order_index": order_index,
        "type_point": point.type_point,
        "place_point": point.place_point,
        "date_point": point.date_point,
        "status": point.status,
        "time_accepted": point.time_accepted.isoformat() if point.time_accepted else None,
        "time_registration": point.time_registration.isoformat() if point.time_registration else None,
        "time_put_on_gate": point.time_put_on_gate.isoformat() if point.time_put_on_gate else None,
        "time_docs": point.time_docs.isoformat() if point.time_docs else None,
        "time_departure": point.time_departure.isoformat() if point.time_departure else None,
    }


def _route_out(db: Session, route: Route, include_points: bool = False) -> dict:
    driver = db.get(User, route.assigned_user_id) if route.assigned_user_id else None
    creator = db.get(User, route.created_by_user_id) if route.created_by_user_id else None
    points = _route_points(db, route.id) if include_points else []
    points_count = len(points)
    if not include_points:
        points_count = db.scalar(select(func.count()).select_from(RoutePoint).where(RoutePoint.route_id == route.id)) or 0
    return {
        "id": route.id,
        "status": route.status,
        "number_auto": route.number_auto,
        "temperature": route.temperature,
        "dispatcher_contacts": route.dispatcher_contacts,
        "registration_number": route.registration_number,
        "trailer_number": route.trailer_number,
        "accepted_at": route.accepted_at.isoformat() if route.accepted_at else None,
        "created_at": route.created_at.isoformat() if isinstance(route.created_at, datetime) else None,
        "driver": _driver_out(driver),
        "created_by": _driver_out(creator),
        "points_count": points_count,
        "points": [_point_out(point, idx) for idx, point in enumerate(points)] if include_points else None,
    }


def _ensure_driver(db: Session, driver_user_id: int) -> User:
    user = db.get(User, driver_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
    if user.role_code != RoleCode.DRIVER.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned user must have role 'driver'")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Driver is inactive")
    return user


@router.get("/drivers")
def list_drivers(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_route_manager),
) -> dict:
    drivers = db.scalars(
        select(User).where(User.role_code == RoleCode.DRIVER.value, User.is_active.is_(True)).order_by(User.id.asc())
    ).all()
    return {"items": [_driver_out(driver) for driver in drivers]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_route(
    payload: AdminRouteCreatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_route_manager),
) -> dict:
    route_id = payload.route_id.strip()
    if not route_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="route_id is required")

    existing = db.get(Route, route_id)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Route id already exists")

    driver = _ensure_driver(db, payload.driver_user_id)
    legacy_driver_tg_id = int(driver.legacy_tg_id) if (driver.legacy_tg_id or "").isdigit() else None

    route = Route(
        id=route_id,
        legacy_driver_tg_id=legacy_driver_tg_id,
        assigned_user_id=driver.id,
        created_by_user_id=current_user.id,
        status="new",
        number_auto=(payload.number_auto or "").strip(),
        temperature=(payload.temperature or "").strip(),
        dispatcher_contacts=(payload.dispatcher_contacts or "").strip(),
        registration_number=(payload.registration_number or "").strip(),
        trailer_number=(payload.trailer_number or "").strip(),
    )
    db.add(route)
    db.flush()

    if payload.points:
        next_point_id = db.scalar(select(func.coalesce(func.max(Point.id), 0))) or 0
        sorted_points = sorted(
            enumerate(payload.points),
            key=lambda item: item[1].order_index if item[1].order_index is not None else item[0],
        )
        for order_index, (_, point_in) in enumerate(sorted_points):
            next_point_id += 1
            type_point = point_in.type_point.strip().lower()
            if type_point not in {"loading", "unloading"}:
                type_point = "loading"
            point = Point(
                id=next_point_id,
                route_id=route.id,
                type_point=type_point,
                place_point=point_in.place_point.strip(),
                date_point=point_in.date_point.strip(),
                status="new",
            )
            db.add(point)
            db.flush()
            db.add(RoutePoint(route_id=route.id, point_id=point.id, order_index=order_index))

    db.commit()
    db.refresh(route)
    return _route_out(db, route, include_points=True)


@router.get("")
def list_routes(
    status_filter: str | None = Query(default=None, alias="status"),
    driver_user_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_route_manager),
) -> dict:
    query = select(Route).order_by(Route.created_at.desc())
    if status_filter:
        query = query.where(Route.status == status_filter.strip())
    if driver_user_id is not None:
        query = query.where(Route.assigned_user_id == driver_user_id)
    routes = db.scalars(query).all()
    return {"items": [_route_out(db, route, include_points=False) for route in routes]}


@router.get("/{route_id}")
def get_route(
    route_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_route_manager),
) -> dict:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    return _route_out(db, route, include_points=True)


@router.post("/{route_id}/assign")
def assign_route_driver(
    route_id: str,
    payload: AssignDriverPayload,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_route_manager),
) -> dict:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    driver = _ensure_driver(db, payload.driver_user_id)
    route.assigned_user_id = driver.id
    route.legacy_driver_tg_id = int(driver.legacy_tg_id) if (driver.legacy_tg_id or "").isdigit() else None
    db.add(route)
    db.commit()
    db.refresh(route)
    return _route_out(db, route, include_points=True)

