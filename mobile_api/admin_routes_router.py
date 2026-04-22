from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_route_manager
from mobile_api.db import get_db
from mobile_api.models import Notification, Point, PointDocumentImage, Route, RouteEvent, RoutePoint, User
from mobile_api.route_notification_logic import (
    notify_route_assigned,
    notify_route_cancelled,
    notify_route_completed,
    notify_route_deleted,
)
from mobile_api.onec_routes import parse_onec_message
from mobile_api.roles import RoleCode, role_label_ru
from mobile_api.time_formatting import format_dt_for_app


router = APIRouter(prefix="/v1/admin/routes", tags=["admin-routes"])

ROUTE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "new": {"process", "cancelled"},
    "process": {"success", "cancelled"},
    "success": set(),
    "cancelled": set(),
}


def _format_datetime_ru(value: datetime | None) -> str | None:
    return format_dt_for_app(value)


class AdminRoutePointCreate(BaseModel):
    type_point: str = Field(min_length=1, max_length=32)
    place_point: str = Field(min_length=1, max_length=2000)
    date_point: str = Field(min_length=1, max_length=64)
    point_name: str = Field(default="", max_length=255)
    point_contacts: str = Field(default="", max_length=255)
    point_time: str = Field(default="", max_length=128)
    point_note: str = Field(default="", max_length=2000)
    order_index: int | None = Field(default=None, ge=0)


class AdminRouteCreatePayload(BaseModel):
    route_id: str = Field(min_length=1, max_length=64)
    driver_fio: str = Field(default="", max_length=255)
    driver_user_id: int | None = None
    number_auto: str = ""
    temperature: str = ""
    dispatcher_contacts: str = ""
    registration_number: str = ""
    trailer_number: str = ""
    points: list[AdminRoutePointCreate] = Field(default_factory=list, max_items=200)


class AdminRouteCreateFromOnecPayload(BaseModel):
    raw_text: str = Field(min_length=1, max_length=20000)
    driver_user_id: int | None = None


class AssignDriverPayload(BaseModel):
    driver_user_id: int


class UpdateRouteStatusPayload(BaseModel):
    status: str = Field(min_length=1, max_length=32)

class UpdateAdminRoutePayload(BaseModel):
    number_auto: str | None = Field(default=None, max_length=64)
    temperature: str | None = Field(default=None, max_length=64)
    dispatcher_contacts: str | None = Field(default=None, max_length=2000)
    registration_number: str | None = Field(default=None, max_length=64)
    trailer_number: str | None = Field(default=None, max_length=64)
    points: list[AdminRoutePointCreate] | None = Field(default=None, max_items=200)


class AdminPointPatchPayload(BaseModel):
    type_point: str | None = Field(default=None, max_length=32)
    place_point: str | None = Field(default=None, max_length=2000)
    date_point: str | None = Field(default=None, max_length=64)
    point_name: str | None = Field(default=None, max_length=255)
    point_contacts: str | None = Field(default=None, max_length=255)
    point_time: str | None = Field(default=None, max_length=128)
    point_note: str | None = Field(default=None, max_length=2000)


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


def _point_out(db: Session, point: Point, order_index: int) -> dict:
    docs_rows = db.scalars(
        select(PointDocumentImage)
        .where(PointDocumentImage.point_id == point.id)
        .order_by(PointDocumentImage.id.asc())
    ).all()
    docs_images = [{"id": row.id, "content_type": row.content_type} for row in docs_rows]
    return {
        "id": point.id,
        "order_index": order_index,
        "type_point": point.type_point,
        "place_point": point.place_point,
        "date_point": point.date_point,
        "point_name": point.point_name,
        "point_contacts": point.point_contacts,
        "point_time": point.point_time,
        "point_note": point.point_note,
        "status": point.status,
        "time_accepted": _format_datetime_ru(point.time_accepted),
        "time_registration": _format_datetime_ru(point.time_registration),
        "time_put_on_gate": _format_datetime_ru(point.time_put_on_gate),
        "time_docs": _format_datetime_ru(point.time_docs),
        "time_departure": _format_datetime_ru(point.time_departure),
        "departure_time": _format_datetime_ru(point.departure_time),
        "departure_odometer": point.departure_odometer,
        "departure_coordinates": {"lat": point.departure_lat, "lng": point.departure_lng},
        "registration_time": _format_datetime_ru(point.registration_time),
        "registration_odometer": point.registration_odometer,
        "registration_coordinates": {"lat": point.registration_lat, "lng": point.registration_lng},
        "gate_time": _format_datetime_ru(point.gate_time),
        "gate_odometer": point.gate_odometer,
        "gate_coordinates": {"lat": point.gate_lat, "lng": point.gate_lng},
        "docs_time": _format_datetime_ru(point.docs_time),
        "docs_odometer": point.docs_odometer,
        "docs_coordinates": {"lat": point.docs_lat, "lng": point.docs_lng},
        "odometer": point.odometer,
        "coordinates": {"lat": point.lat, "lng": point.lng},
        "docs_images": docs_images,
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
        "points": [_point_out(db, point, idx) for idx, point in enumerate(points)] if include_points else None,
    }


def _normalize_route_status(status_value: str) -> str:
    status_norm = (status_value or "").strip().lower()
    return status_norm


def _assert_route_status_transition(current_status: str, next_status: str) -> None:
    allowed = ROUTE_STATUS_TRANSITIONS.get(current_status, set())
    if next_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid route status transition: {current_status} -> {next_status}",
        )


def _can_mark_success(db: Session, route_id: str) -> bool:
    statuses = db.scalars(select(Point.status).where(Point.route_id == route_id)).all()
    if not statuses:
        return False
    return all(point_status in {"docs", "success"} for point_status in statuses)


def _ensure_driver(db: Session, driver_user_id: int) -> User:
    user = db.get(User, driver_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
    if user.role_code != RoleCode.DRIVER.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned user must have role 'driver'")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Driver is inactive")
    return user


def _try_find_driver_by_fio(db: Session, fio: str) -> User | None:
    text = (fio or "").strip()
    if not text:
        return None
    q = f"%{text.lower()}%"
    rows = db.scalars(
        select(User).where(
            User.role_code == RoleCode.DRIVER.value,
            User.is_active.is_(True),
            func.coalesce(func.lower(User.full_name), "").like(q),
        )
    ).all()
    if len(rows) == 1:
        return rows[0]
    return None


def _apply_points_replace(db: Session, route: Route, points_in: list[AdminRoutePointCreate]) -> None:
    existing_ids = db.scalars(select(RoutePoint.point_id).where(RoutePoint.route_id == route.id)).all()
    if existing_ids:
        db.query(RoutePoint).filter(RoutePoint.route_id == route.id).delete(synchronize_session=False)
        db.query(Point).filter(Point.id.in_(existing_ids)).delete(synchronize_session=False)

    if not points_in:
        return

    next_point_id = db.scalar(select(func.coalesce(func.max(Point.id), 0))) or 0
    sorted_points = sorted(
        enumerate(points_in),
        key=lambda item: item[1].order_index if item[1].order_index is not None else item[0],
    )
    for order_index, (_, point_in) in enumerate(sorted_points):
        next_point_id += 1
        type_point = (point_in.type_point or "").strip().lower()
        if type_point not in {"loading", "unloading"}:
            type_point = "loading"
        point = Point(
            id=next_point_id,
            route_id=route.id,
            type_point=type_point,
            place_point=(point_in.place_point or "").strip(),
            date_point=(point_in.date_point or "").strip(),
            point_name=(point_in.point_name or "").strip(),
            point_contacts=(point_in.point_contacts or "").strip(),
            point_time=(point_in.point_time or "").strip(),
            point_note=(point_in.point_note or "").strip(),
            status="new",
        )
        db.add(point)
        db.flush()
        db.add(RoutePoint(route_id=route.id, point_id=point.id, order_index=order_index))


def _route_id_by_point_id(db: Session, point_id: int) -> str | None:
    route_id = db.scalar(select(RoutePoint.route_id).where(RoutePoint.point_id == point_id).limit(1))
    if route_id:
        return route_id
    point = db.get(Point, point_id)
    return point.route_id if point else None


def _normalize_type_point(value: str) -> str:
    text = value.strip().lower()
    if text in {"loading", "загрузка"}:
        return "loading"
    if text in {"unloading", "выгрузка"}:
        return "unloading"
    return "loading"


def _point_order_index(db: Session, route_id: str, point_id: int) -> int:
    order_idx = db.scalar(
        select(RoutePoint.order_index).where(RoutePoint.route_id == route_id, RoutePoint.point_id == point_id).limit(1)
    )
    return int(order_idx) if order_idx is not None else 0


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

    driver: User | None = None
    if payload.driver_user_id is not None:
        driver = _ensure_driver(db, payload.driver_user_id)
    else:
        driver = _try_find_driver_by_fio(db, payload.driver_fio)
        if driver is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Не удалось однозначно определить водителя по ФИО. Проверьте ФИО или выберите водителя вручную.",
            )
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
        _apply_points_replace(db, route, payload.points)

    notify_route_assigned(
        db,
        route=route,
        assigned_user=driver,
        actor_user=current_user,
    )
    db.commit()
    db.refresh(route)
    return _route_out(db, route, include_points=True)


@router.post("/onec", status_code=status.HTTP_201_CREATED)
def create_route_from_onec(
    payload: AdminRouteCreateFromOnecPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_route_manager),
) -> dict:
    parsed = parse_onec_message(payload.raw_text)
    if not parsed.route_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Не найден номер рейса в тексте 1С")

    existing = db.get(Route, parsed.route_id)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Route id already exists")

    driver: User | None = None
    if payload.driver_user_id is not None:
        driver = _ensure_driver(db, payload.driver_user_id)
    else:
        driver = _try_find_driver_by_fio(db, parsed.driver_fio)
        if driver is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Не удалось однозначно определить водителя по ФИО. Выберите водителя вручную.",
            )

    legacy_driver_tg_id = int(driver.legacy_tg_id) if (driver.legacy_tg_id or "").isdigit() else None
    route = Route(
        id=parsed.route_id,
        legacy_driver_tg_id=legacy_driver_tg_id,
        assigned_user_id=driver.id,
        created_by_user_id=current_user.id,
        status="new",
        number_auto=(parsed.number_auto or "").strip(),
        temperature=(parsed.temperature or "").strip(),
        dispatcher_contacts=(parsed.dispatcher_contacts or "").strip(),
        registration_number=(parsed.registration_number or "").strip(),
        trailer_number=(parsed.trailer_number or "").strip(),
    )
    db.add(route)
    db.flush()

    if parsed.points:
        points_payload = [
            AdminRoutePointCreate(
                type_point=p.type_point,
                place_point=p.place_point,
                date_point=p.date_point,
                point_name="",
                point_contacts="",
                point_time="",
                point_note="",
                order_index=i,
            )
            for i, p in enumerate(parsed.points)
        ]
        _apply_points_replace(db, route, points_payload)

    notify_route_assigned(db, route=route, assigned_user=driver, actor_user=current_user)
    db.commit()
    db.refresh(route)
    return _route_out(db, route, include_points=True)


@router.get("")
def list_routes(
    status_filter: str | None = Query(default=None, alias="status"),
    driver_user_id: int | None = Query(default=None),
    route_id: str | None = Query(default=None),
    number_auto: str | None = Query(default=None),
    driver_query: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_route_manager),
) -> dict:
    query = select(Route).order_by(Route.created_at.desc())
    if status_filter:
        statuses = [item.strip() for item in status_filter.split(",") if item.strip()]
        if statuses:
            query = query.where(Route.status.in_(statuses))
    if route_id:
        query = query.where(Route.id == route_id.strip())
    if number_auto:
        query = query.where(func.lower(Route.number_auto) == number_auto.strip().lower())
    if driver_user_id is not None:
        query = query.where(Route.assigned_user_id == driver_user_id)
    elif driver_query:
        q = f"%{driver_query.strip().lower()}%"
        driver_ids = db.scalars(
            select(User.id).where(
                User.role_code == RoleCode.DRIVER.value,
                func.coalesce(func.lower(User.full_name), "").like(q) | func.coalesce(func.lower(User.login), "").like(q),
            )
        ).all()
        if not driver_ids:
            return {"items": []}
        query = query.where(Route.assigned_user_id.in_(driver_ids))
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
    current_user: User = Depends(get_current_route_manager),
) -> dict:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    driver = _ensure_driver(db, payload.driver_user_id)
    route.assigned_user_id = driver.id
    route.legacy_driver_tg_id = int(driver.legacy_tg_id) if (driver.legacy_tg_id or "").isdigit() else None
    db.add(route)
    notify_route_assigned(
        db,
        route=route,
        assigned_user=driver,
        actor_user=current_user,
    )
    db.commit()
    db.refresh(route)
    return _route_out(db, route, include_points=True)


@router.post("/{route_id}/cancel")
def cancel_route(
    route_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_route_manager),
) -> dict:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

    _assert_route_status_transition(route.status, "cancelled")
    route.status = "cancelled"
    db.add(route)
    assigned_user = db.get(User, route.assigned_user_id) if route.assigned_user_id else None
    notify_route_cancelled(
        db,
        route=route,
        assigned_user=assigned_user,
        actor_user=current_user,
    )
    db.commit()
    db.refresh(route)
    return _route_out(db, route, include_points=True)


@router.post("/{route_id}/complete")
def complete_route(
    route_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_route_manager),
) -> dict:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

    _assert_route_status_transition(route.status, "success")
    if not _can_mark_success(db, route.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot complete route: not all points are in success status",
        )

    route.status = "success"
    db.add(route)
    notify_route_completed(
        db,
        route=route,
        actor_user=current_user,
    )
    db.commit()
    db.refresh(route)
    return _route_out(db, route, include_points=True)


@router.patch("/{route_id}/status")
def update_route_status(
    route_id: str,
    payload: UpdateRouteStatusPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_route_manager),
) -> dict:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

    next_status = _normalize_route_status(payload.status)
    if next_status not in ROUTE_STATUS_TRANSITIONS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported route status")

    if route.status == next_status:
        return _route_out(db, route, include_points=True)

    _assert_route_status_transition(route.status, next_status)
    if next_status == "success" and not _can_mark_success(db, route.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot complete route: not all points are in success status",
        )

    route.status = next_status
    db.add(route)
    if next_status == "cancelled":
        assigned_user = db.get(User, route.assigned_user_id) if route.assigned_user_id else None
        notify_route_cancelled(
            db,
            route=route,
            assigned_user=assigned_user,
            actor_user=current_user,
        )
    elif next_status == "success":
        notify_route_completed(
            db,
            route=route,
            actor_user=current_user,
        )
    db.commit()
    db.refresh(route)
    return _route_out(db, route, include_points=True)


@router.patch("/{route_id}")
def update_route(
    route_id: str,
    payload: UpdateAdminRoutePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_route_manager),
) -> dict:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

    if payload.number_auto is not None:
        route.number_auto = payload.number_auto.strip()
    if payload.temperature is not None:
        route.temperature = payload.temperature.strip()
    if payload.dispatcher_contacts is not None:
        route.dispatcher_contacts = payload.dispatcher_contacts.strip()
    if payload.registration_number is not None:
        route.registration_number = payload.registration_number.strip()
    if payload.trailer_number is not None:
        route.trailer_number = payload.trailer_number.strip()
    if payload.points is not None:
        _apply_points_replace(db, route, payload.points)
        route.status = "new"

    db.add(route)
    assigned_user = db.get(User, route.assigned_user_id) if route.assigned_user_id else None
    if assigned_user is not None:
        notify_route_assigned(
            db,
            route=route,
            assigned_user=assigned_user,
            actor_user=current_user,
        )
    db.commit()
    db.refresh(route)
    return _route_out(db, route, include_points=True)


@router.patch("/points/{point_id}")
def update_route_point(
    point_id: int,
    payload: AdminPointPatchPayload,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_route_manager),
) -> dict:
    point = db.get(Point, point_id)
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Point not found")

    if payload.type_point is not None:
        point.type_point = _normalize_type_point(payload.type_point)
    if payload.place_point is not None:
        point.place_point = payload.place_point.strip()
    if payload.date_point is not None:
        point.date_point = payload.date_point.strip()
    if payload.point_name is not None:
        point.point_name = payload.point_name.strip()
    if payload.point_contacts is not None:
        point.point_contacts = payload.point_contacts.strip()
    if payload.point_time is not None:
        point.point_time = payload.point_time.strip()
    if payload.point_note is not None:
        point.point_note = payload.point_note.strip()

    db.add(point)
    db.commit()
    db.refresh(point)
    route_id = _route_id_by_point_id(db, point.id)
    order_index = _point_order_index(db, route_id, point.id) if route_id else 0
    return _point_out(db, point, order_index)


@router.delete("/points/{point_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route_point(
    point_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_route_manager),
) -> None:
    point = db.get(Point, point_id)
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Point not found")
    route_id = _route_id_by_point_id(db, point_id)
    db.query(RoutePoint).filter(RoutePoint.point_id == point_id).delete(synchronize_session=False)
    db.delete(point)
    if route_id:
        ordered = (
            db.query(RoutePoint)
            .filter(RoutePoint.route_id == route_id)
            .order_by(RoutePoint.order_index.asc(), RoutePoint.id.asc())
            .all()
        )
        for idx, link in enumerate(ordered):
            link.order_index = idx
            db.add(link)
    db.commit()


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route(
    route_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_route_manager),
) -> None:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

    assigned_user = db.get(User, route.assigned_user_id) if route.assigned_user_id else None
    notify_route_deleted(
        db,
        route=route,
        assigned_user=assigned_user,
        actor_user=current_user,
    )

    point_ids = db.scalars(select(Point.id).where(Point.route_id == route.id)).all()
    if point_ids:
        db.query(Notification).filter(Notification.point_id.in_(point_ids)).delete(synchronize_session=False)
        db.query(RouteEvent).filter(RouteEvent.point_id.in_(point_ids)).delete(synchronize_session=False)
    db.query(RouteEvent).filter(RouteEvent.route_id == route.id).delete(synchronize_session=False)
    db.query(Notification).filter(
        or_(
            Notification.route_id == route.id,
            Notification.point_id.in_(point_ids) if point_ids else False,
        )
    ).delete(synchronize_session=False)
    db.query(RoutePoint).filter(RoutePoint.route_id == route.id).delete(synchronize_session=False)
    db.query(Point).filter(Point.route_id == route.id).delete(synchronize_session=False)
    db.delete(route)
    db.commit()

