from __future__ import annotations

from urllib.parse import unquote
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_route_manager
from mobile_api.db import get_db
from mobile_api.models import Notification, Point, PointDocumentImage, Route, RouteEvent, RoutePoint, User
from mobile_api.route_notification_logic import (
    notify_driver_route_updated,
    notify_route_assigned,
    notify_route_cancelled,
    notify_route_completed,
    notify_route_deleted,
    point_fact_datetime,
)
from mobile_api.onec_routes import parse_onec_message
from mobile_api.roles import RoleCode, role_label_ru
from mobile_api.time_formatting import format_dt_for_app
from utils.onec_datetime import planned_wall_fields, split_onec_wall_datetime, normalize_planned_time


router = APIRouter(prefix="/v1/admin/routes", tags=["admin-routes"])

ROUTE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "new": {"process", "cancelled"},
    "process": {"success", "cancelled"},
    "success": set(),
    "cancelled": set(),
}


def _format_datetime_ru(value: datetime | None) -> str | None:
    return format_dt_for_app(value)


def _load_manual_edits(point: Point) -> dict:
    raw = (point.manual_edits or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _mark_manual_edit(point: Point, field: str, user: User) -> None:
    edits = _load_manual_edits(point)
    edits[field] = {
        "user_id": user.id,
        "login": user.login,
        "full_name": user.full_name or "",
        "at": datetime.now(timezone.utc).isoformat(),
    }
    point.manual_edits = json.dumps(edits, ensure_ascii=False)


def _parse_optional_dt(value: str | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Некорректное время в поле {field_name}",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _dt_equal(left: datetime | None, right: datetime | None) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    left_aware = left if left.tzinfo else left.replace(tzinfo=timezone.utc)
    right_aware = right if right.tzinfo else right.replace(tzinfo=timezone.utc)
    return left_aware.astimezone(timezone.utc).replace(microsecond=0) == right_aware.astimezone(timezone.utc).replace(
        microsecond=0
    )


def _apply_str_edit(point: Point, attr: str, value: str, user: User, field: str | None = None) -> None:
    current = getattr(point, attr) or ""
    if current == value:
        return
    setattr(point, attr, value)
    _mark_manual_edit(point, field or attr, user)


def _apply_dt_edit(
    point: Point,
    attrs: tuple[str, ...],
    value: str | None,
    user: User,
    field: str,
) -> None:
    parsed = _parse_optional_dt(value, field)
    primary = attrs[0]
    if _dt_equal(getattr(point, primary), parsed):
        return
    for attr in attrs:
        setattr(point, attr, parsed)
    _mark_manual_edit(point, field, user)


def _apply_odo_edit(point: Point, attr: str, source_attr: str, value: str, user: User, field: str) -> None:
    current = getattr(point, attr) or ""
    if current == value:
        return
    setattr(point, attr, value or None)
    setattr(point, source_attr, "manual" if value else None)
    _mark_manual_edit(point, field, user)


def _apply_coord_edit(
    point: Point,
    lat_attr: str,
    lng_attr: str,
    coords: AdminPointCoordPatch,
    user: User,
    field: str,
) -> None:
    lat = coords.lat
    lng = coords.lng
    current_lat = getattr(point, lat_attr)
    current_lng = getattr(point, lng_attr)
    if current_lat == lat and current_lng == lng:
        return
    setattr(point, lat_attr, lat)
    setattr(point, lng_attr, lng)
    _mark_manual_edit(point, field, user)


def _normalize_route_id(route_id: str) -> str:
    return unquote(route_id or "").strip()


class AdminRoutePointCreate(BaseModel):
    id: int | None = Field(default=None, ge=1)
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
    created_by_user_id: int | None = None
    number_auto: str = ""
    temperature: str = ""
    dispatcher_contacts: str = ""
    registration_number: str = ""
    trailer_number: str = ""
    points: list[AdminRoutePointCreate] = Field(default_factory=list, max_items=200)


class AdminRouteCreateFromOnecPayload(BaseModel):
    raw_text: str = Field(min_length=1, max_length=20000)
    driver_user_id: int | None = None
    number_auto: str | None = Field(default=None, max_length=64)
    trailer_number: str | None = Field(default=None, max_length=64)


class AssignDriverPayload(BaseModel):
    driver_user_id: int
    number_auto: str | None = Field(default=None, max_length=64)
    trailer_number: str | None = Field(default=None, max_length=64)


class UpdateRouteStatusPayload(BaseModel):
    status: str = Field(min_length=1, max_length=32)

class UpdateAdminRoutePayload(BaseModel):
    number_auto: str | None = Field(default=None, max_length=64)
    temperature: str | None = Field(default=None, max_length=64)
    dispatcher_contacts: str | None = Field(default=None, max_length=2000)
    registration_number: str | None = Field(default=None, max_length=64)
    trailer_number: str | None = Field(default=None, max_length=64)
    created_by_user_id: int | None = None
    points: list[AdminRoutePointCreate] | None = Field(default=None, max_items=200)


class AdminPointCoordPatch(BaseModel):
    lat: float | None = None
    lng: float | None = None


class AdminPointPatchPayload(BaseModel):
    type_point: str | None = Field(default=None, max_length=32)
    place_point: str | None = Field(default=None, max_length=2000)
    date_point: str | None = Field(default=None, max_length=64)
    point_name: str | None = Field(default=None, max_length=255)
    point_contacts: str | None = Field(default=None, max_length=255)
    point_time: str | None = Field(default=None, max_length=128)
    point_note: str | None = Field(default=None, max_length=2000)
    departure_time: str | None = Field(default=None, max_length=64)
    departure_odometer: str | None = Field(default=None, max_length=64)
    departure_coordinates: AdminPointCoordPatch | None = None
    registration_time: str | None = Field(default=None, max_length=64)
    registration_odometer: str | None = Field(default=None, max_length=64)
    registration_coordinates: AdminPointCoordPatch | None = None
    gate_time: str | None = Field(default=None, max_length=64)
    gate_odometer: str | None = Field(default=None, max_length=64)
    gate_coordinates: AdminPointCoordPatch | None = None
    docs_time: str | None = Field(default=None, max_length=64)
    docs_odometer: str | None = Field(default=None, max_length=64)
    docs_coordinates: AdminPointCoordPatch | None = None
    status: str | None = Field(default=None, max_length=32)


COMPLETED_POINT_STATUSES = {"docs", "success"}


def _route_points(db: Session, route_id: str) -> list[Point]:
    ordered_ids = db.scalars(
        select(RoutePoint.point_id).where(RoutePoint.route_id == route_id).order_by(RoutePoint.order_index.asc())
    ).all()
    if not ordered_ids:
        return []
    points = db.scalars(select(Point).where(Point.id.in_(ordered_ids))).all()
    points_map = {point.id: point for point in points}
    return [points_map[point_id] for point_id in ordered_ids if point_id in points_map]


def _normalize_admin_point_status(value: str) -> str:
    raw = (value or "").strip().lower()
    if raw == "success":
        return "docs"
    if raw not in {"new", "process", "registration", "load", "docs"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported point status",
        )
    return raw


def _sync_route_status_from_points(db: Session, route: Route) -> None:
    if route.status == "cancelled":
        return
    statuses = db.scalars(select(Point.status).where(Point.route_id == route.id)).all()
    if not statuses:
        return
    all_done = all(point_status in COMPLETED_POINT_STATUSES for point_status in statuses)
    if all_done:
        if route.status != "success":
            route.status = "success"
            db.add(route)
        return
    if route.status == "success":
        route.status = "process"
        db.add(route)


def _pick_active_point(points: list[Point]) -> Point | None:
    if not points:
        return None
    return next((point for point in points if point.status not in COMPLETED_POINT_STATUSES), points[-1])


def _active_points_by_route_id(db: Session, route_ids: list[str]) -> dict[str, Point]:
    if not route_ids:
        return {}
    rows = db.execute(
        select(RoutePoint.route_id, Point)
        .join(Point, Point.id == RoutePoint.point_id)
        .where(RoutePoint.route_id.in_(route_ids))
        .order_by(RoutePoint.route_id.asc(), RoutePoint.order_index.asc())
    ).all()
    first_open: dict[str, Point] = {}
    last_by_route: dict[str, Point] = {}
    for route_id, point in rows:
        last_by_route[route_id] = point
        if route_id not in first_open and point.status not in COMPLETED_POINT_STATUSES:
            first_open[route_id] = point
    return {route_id: first_open.get(route_id) or last_by_route[route_id] for route_id in last_by_route}


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
    date_point, point_time = planned_wall_fields(point.date_point, point.point_time)
    return {
        "id": point.id,
        "order_index": order_index,
        "type_point": point.type_point,
        "place_point": point.place_point,
        "date_point": date_point,
        "point_name": point.point_name,
        "point_contacts": point.point_contacts,
        "point_time": point_time,
        "point_note": point.point_note,
        "status": point.status,
        "time_accepted": _format_datetime_ru(point.time_accepted),
        "time_registration": _format_datetime_ru(point.time_registration),
        "time_put_on_gate": _format_datetime_ru(point.time_put_on_gate),
        "time_docs": _format_datetime_ru(point.time_docs),
        "time_departure": _format_datetime_ru(point.time_departure),
        "departure_time": _format_datetime_ru(point.departure_time),
        "departure_odometer": point.departure_odometer,
        "departure_odometer_source": point.departure_odometer_source,
        "departure_coordinates": {"lat": point.departure_lat, "lng": point.departure_lng},
        "registration_time": _format_datetime_ru(point.registration_time),
        "registration_odometer": point.registration_odometer,
        "registration_odometer_source": point.registration_odometer_source,
        "registration_coordinates": {"lat": point.registration_lat, "lng": point.registration_lng},
        "gate_time": _format_datetime_ru(point.gate_time),
        "gate_odometer": point.gate_odometer,
        "gate_odometer_source": point.gate_odometer_source,
        "gate_coordinates": {"lat": point.gate_lat, "lng": point.gate_lng},
        "docs_time": _format_datetime_ru(point.docs_time),
        "docs_odometer": point.docs_odometer,
        "docs_odometer_source": point.docs_odometer_source,
        "docs_coordinates": {"lat": point.docs_lat, "lng": point.docs_lng},
        "odometer": point.odometer,
        "coordinates": {"lat": point.lat, "lng": point.lng},
        "docs_images": docs_images,
        "manual_edits": _load_manual_edits(point),
    }


def _route_out(
    db: Session,
    route: Route,
    include_points: bool = False,
    *,
    active_point: Point | None = None,
    skip_active_point_lookup: bool = False,
) -> dict:
    driver = db.get(User, route.assigned_user_id) if route.assigned_user_id else None
    creator = db.get(User, route.created_by_user_id) if route.created_by_user_id else None
    points = _route_points(db, route.id) if include_points else []
    points_count = len(points)
    if not include_points:
        points_count = db.scalar(select(func.count()).select_from(RoutePoint).where(RoutePoint.route_id == route.id)) or 0
    if include_points:
        current_point = _pick_active_point(points)
    elif skip_active_point_lookup:
        current_point = active_point
    else:
        current_point = _pick_active_point(_route_points(db, route.id))
    place = (current_point.place_point or "").strip() if current_point else ""
    name = (current_point.point_name or "").strip() if current_point else ""
    active_date, active_time = planned_wall_fields(
        current_point.date_point if current_point else "",
        current_point.point_time if current_point else "",
    ) if current_point else ("", "")
    return {
        "id": route.id,
        "status": route.status,
        "number_auto": route.number_auto,
        "temperature": route.temperature,
        "dispatcher_contacts": route.dispatcher_contacts,
        "registration_number": route.registration_number,
        "trailer_number": route.trailer_number,
        "accepted_at": route.accepted_at.isoformat() if route.accepted_at else None,
        "driver_received_at": route.driver_received_at.isoformat() if route.driver_received_at else None,
        "created_at": route.created_at.isoformat() if isinstance(route.created_at, datetime) else None,
        "driver": _driver_out(driver),
        "created_by": _driver_out(creator),
        "points_count": points_count,
        "active_point_status": current_point.status if current_point else None,
        "active_point_place": place or None,
        "active_point_name": name or None,
        "active_point_type": current_point.type_point if current_point else None,
        "active_point_date": (active_date or None) if current_point else None,
        "active_point_time": (active_time or None) if current_point else None,
        "active_point_fact_time": (
            _format_datetime_ru(point_fact_datetime(current_point)) if current_point else None
        ),
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


def _normalize_point_plan(date_raw: str, time_raw: str) -> tuple[str, str]:
    return planned_wall_fields(date_raw, time_raw)


def _point_meta_from_payload(point_in: AdminRoutePointCreate) -> tuple[str, str, str, str, str, str, str]:
    type_point = (point_in.type_point or "").strip().lower()
    if type_point not in {"loading", "unloading"}:
        type_point = "loading"
    date_point, point_time = _normalize_point_plan(point_in.date_point or "", point_in.point_time or "")
    return (
        type_point,
        (point_in.place_point or "").strip(),
        date_point,
        (point_in.point_name or "").strip(),
        (point_in.point_contacts or "").strip(),
        point_time,
        (point_in.point_note or "").strip(),
    )


LOGISTIC_SELECT_ROLES = {
    RoleCode.LOGISTIC.value,
    RoleCode.ADMIN.value,
    RoleCode.SUPERADMIN.value,
}


def _ensure_logistic(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Логист не найден")
    if user.role_code not in LOGISTIC_SELECT_ROLES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Пользователь не может быть логистом рейса")
    return user


def _changed_text(label: str, old: str | None, new: str | None) -> str | None:
    prev = (old or "").strip()
    nxt = (new or "").strip()
    if prev == nxt:
        return None
    if prev and nxt:
        return f"{label}: {prev} → {nxt}"
    return f"{label}: {nxt or '—'}"


def _apply_points_replace(
    db: Session,
    route: Route,
    points_in: list[AdminRoutePointCreate],
    *,
    preserve_progress: bool = False,
) -> None:
    existing = _route_points(db, route.id)
    existing_by_id = {point.id: point for point in existing}
    db.query(RoutePoint).filter(RoutePoint.route_id == route.id).delete(synchronize_session=False)

    if not points_in:
        for old in existing:
            db.query(Notification).filter(Notification.point_id == old.id).delete(synchronize_session=False)
            db.query(RouteEvent).filter(RouteEvent.point_id == old.id).delete(synchronize_session=False)
            db.query(PointDocumentImage).filter(PointDocumentImage.point_id == old.id).delete(synchronize_session=False)
            db.delete(old)
        return

    next_point_id = db.scalar(select(func.coalesce(func.max(Point.id), 0))) or 0
    sorted_points = sorted(
        enumerate(points_in),
        key=lambda item: item[1].order_index if item[1].order_index is not None else item[0],
    )
    keep_ids: set[int] = set()
    for order_index, (_, point_in) in enumerate(sorted_points):
        type_point, place_point, date_point, point_name, point_contacts, point_time, point_note = _point_meta_from_payload(
            point_in
        )
        point: Point | None = None
        if preserve_progress:
            if point_in.id is not None:
                point = existing_by_id.get(point_in.id)
            elif order_index < len(existing) and existing[order_index].id not in keep_ids:
                point = existing[order_index]
        if point is not None:
            point.type_point = type_point
            point.place_point = place_point
            point.date_point = date_point
            point.point_name = point_name
            point.point_contacts = point_contacts
            point.point_time = point_time
            point.point_note = point_note
            db.add(point)
        else:
            next_point_id += 1
            point = Point(
                id=next_point_id,
                route_id=route.id,
                type_point=type_point,
                place_point=place_point,
                date_point=date_point,
                point_name=point_name,
                point_contacts=point_contacts,
                point_time=point_time,
                point_note=point_note,
                status="new",
            )
            db.add(point)
            db.flush()
        keep_ids.add(point.id)
        db.add(RoutePoint(route_id=route.id, point_id=point.id, order_index=order_index))

    for old in existing:
        if old.id not in keep_ids:
            db.query(Notification).filter(Notification.point_id == old.id).delete(synchronize_session=False)
            db.query(RouteEvent).filter(RouteEvent.point_id == old.id).delete(synchronize_session=False)
            db.query(PointDocumentImage).filter(PointDocumentImage.point_id == old.id).delete(synchronize_session=False)
            db.delete(old)


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


@router.get("/logistics")
def list_logistics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_route_manager),
) -> dict:
    rows = db.scalars(
        select(User)
        .where(User.role_code.in_(list(LOGISTIC_SELECT_ROLES)), User.is_active.is_(True))
        .order_by(User.full_name.asc(), User.login.asc(), User.id.asc())
    ).all()
    return {"items": [_driver_out(user) for user in rows]}


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

    creator = current_user
    if payload.created_by_user_id:
        creator = _ensure_logistic(db, payload.created_by_user_id)

    route = Route(
        id=route_id,
        legacy_driver_tg_id=legacy_driver_tg_id,
        assigned_user_id=driver.id,
        created_by_user_id=creator.id,
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
        number_auto=((payload.number_auto or parsed.number_auto) or "").strip(),
        temperature=(parsed.temperature or "").strip(),
        dispatcher_contacts=(parsed.dispatcher_contacts or "").strip(),
        registration_number=(parsed.registration_number or "").strip(),
        trailer_number=((payload.trailer_number or parsed.trailer_number) or "").strip(),
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
                point_time=p.point_time,
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
    active_points = _active_points_by_route_id(db, [route.id for route in routes])
    return {
        "items": [
            _route_out(
                db,
                route,
                include_points=False,
                active_point=active_points.get(route.id),
                skip_active_point_lookup=True,
            )
            for route in routes
        ]
    }


@router.patch("/points/{point_id}")
def update_route_point(
    point_id: int,
    payload: AdminPointPatchPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_route_manager),
) -> dict:
    point = db.get(Point, point_id)
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Point not found")

    data = payload.model_dump(exclude_unset=True)
    before = {
        "type_point": point.type_point,
        "place_point": point.place_point,
        "date_point": point.date_point,
        "point_time": point.point_time,
        "status": point.status,
    }

    if "type_point" in data and payload.type_point is not None:
        _apply_str_edit(point, "type_point", _normalize_type_point(payload.type_point), current_user)
    if "place_point" in data and payload.place_point is not None:
        _apply_str_edit(point, "place_point", payload.place_point.strip(), current_user)
    if "date_point" in data and payload.date_point is not None:
        date_s, time_from_date = split_onec_wall_datetime(payload.date_point.strip())
        _apply_str_edit(point, "date_point", date_s or payload.date_point.strip(), current_user)
        if time_from_date and "point_time" not in data:
            _apply_str_edit(point, "point_time", time_from_date, current_user)
    if "point_name" in data and payload.point_name is not None:
        _apply_str_edit(point, "point_name", payload.point_name.strip(), current_user)
    if "point_contacts" in data and payload.point_contacts is not None:
        _apply_str_edit(point, "point_contacts", payload.point_contacts.strip(), current_user)
    if "point_time" in data and payload.point_time is not None:
        _apply_str_edit(point, "point_time", normalize_planned_time(payload.point_time.strip()) or payload.point_time.strip(), current_user)
    if "point_note" in data and payload.point_note is not None:
        _apply_str_edit(point, "point_note", payload.point_note.strip(), current_user)

    if "departure_time" in data:
        _apply_dt_edit(point, ("departure_time", "time_accepted"), payload.departure_time, current_user, "departure_time")
    if "departure_odometer" in data and payload.departure_odometer is not None:
        _apply_odo_edit(
            point, "departure_odometer", "departure_odometer_source", payload.departure_odometer.strip(), current_user, "departure_odometer"
        )
    if "departure_coordinates" in data and payload.departure_coordinates is not None:
        _apply_coord_edit(
            point, "departure_lat", "departure_lng", payload.departure_coordinates, current_user, "departure_coordinates"
        )

    if "registration_time" in data:
        _apply_dt_edit(
            point, ("registration_time", "time_registration"), payload.registration_time, current_user, "registration_time"
        )
    if "registration_odometer" in data and payload.registration_odometer is not None:
        _apply_odo_edit(
            point,
            "registration_odometer",
            "registration_odometer_source",
            payload.registration_odometer.strip(),
            current_user,
            "registration_odometer",
        )
    if "registration_coordinates" in data and payload.registration_coordinates is not None:
        _apply_coord_edit(
            point,
            "registration_lat",
            "registration_lng",
            payload.registration_coordinates,
            current_user,
            "registration_coordinates",
        )

    if "gate_time" in data:
        _apply_dt_edit(point, ("gate_time", "time_put_on_gate"), payload.gate_time, current_user, "gate_time")
    if "gate_odometer" in data and payload.gate_odometer is not None:
        _apply_odo_edit(point, "gate_odometer", "gate_odometer_source", payload.gate_odometer.strip(), current_user, "gate_odometer")
    if "gate_coordinates" in data and payload.gate_coordinates is not None:
        _apply_coord_edit(point, "gate_lat", "gate_lng", payload.gate_coordinates, current_user, "gate_coordinates")

    if "docs_time" in data:
        _apply_dt_edit(point, ("docs_time", "time_docs"), payload.docs_time, current_user, "docs_time")
    if "docs_odometer" in data and payload.docs_odometer is not None:
        _apply_odo_edit(point, "docs_odometer", "docs_odometer_source", payload.docs_odometer.strip(), current_user, "docs_odometer")
    if "docs_coordinates" in data and payload.docs_coordinates is not None:
        _apply_coord_edit(point, "docs_lat", "docs_lng", payload.docs_coordinates, current_user, "docs_coordinates")

    original_status = point.status
    if "status" in data and payload.status is not None:
        next_status = _normalize_admin_point_status(payload.status)
        if next_status != point.status:
            point.status = next_status
            _mark_manual_edit(point, "status", current_user)
    else:
        point.status = original_status

    db.add(point)
    route_id = _route_id_by_point_id(db, point.id)
    route = db.get(Route, route_id) if route_id else None
    if route is not None and "status" in data and payload.status is not None:
        _sync_route_status_from_points(db, route)
    changes: list[str] = []
    kind = "Загрузка" if (point.type_point or "") == "loading" else "Выгрузка"
    prefix = f"Точка {kind}"
    for key, label in (
        ("place_point", "адрес"),
        ("date_point", "дата"),
        ("point_time", "время"),
        ("status", "статус"),
    ):
        item = _changed_text(f"{prefix} · {label}", before.get(key), getattr(point, key, None))
        if item:
            changes.append(item)
    if route is not None:
        notify_driver_route_updated(db, route=route, actor_user=current_user, changes=changes)
    db.commit()
    db.refresh(point)
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


@router.get("/{route_id:path}")
def get_route(
    route_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_route_manager),
) -> dict:
    route_id = _normalize_route_id(route_id)
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    return _route_out(db, route, include_points=True)


@router.post("/{route_id:path}/assign")
def assign_route_driver(
    route_id: str,
    payload: AssignDriverPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_route_manager),
) -> dict:
    route_id = _normalize_route_id(route_id)
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    driver = _ensure_driver(db, payload.driver_user_id)
    driver_changed = route.assigned_user_id != driver.id
    vehicle_changes: list[str] = []
    if payload.number_auto is not None:
        item = _changed_text("ТС", route.number_auto, payload.number_auto)
        route.number_auto = payload.number_auto.strip().upper()
        if item:
            vehicle_changes.append(item)
    if payload.trailer_number is not None:
        item = _changed_text("Прицеп", route.trailer_number, payload.trailer_number)
        route.trailer_number = payload.trailer_number.strip().upper()
        if item:
            vehicle_changes.append(item)
    if driver_changed:
        route.driver_received_at = None
    route.assigned_user_id = driver.id
    route.legacy_driver_tg_id = int(driver.legacy_tg_id) if (driver.legacy_tg_id or "").isdigit() else None
    db.add(route)
    if driver_changed:
        notify_route_assigned(
            db,
            route=route,
            assigned_user=driver,
            actor_user=current_user,
        )
    elif vehicle_changes:
        notify_driver_route_updated(db, route=route, actor_user=current_user, changes=vehicle_changes)
    db.commit()
    db.refresh(route)
    return _route_out(db, route, include_points=True)


@router.post("/{route_id:path}/cancel")
def cancel_route(
    route_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_route_manager),
) -> dict:
    route_id = _normalize_route_id(route_id)
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


@router.post("/{route_id:path}/complete")
def complete_route(
    route_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_route_manager),
) -> dict:
    route_id = _normalize_route_id(route_id)
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


@router.patch("/{route_id:path}/status")
def update_route_status(
    route_id: str,
    payload: UpdateRouteStatusPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_route_manager),
) -> dict:
    route_id = _normalize_route_id(route_id)
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


@router.patch("/{route_id:path}")
def update_route(
    route_id: str,
    payload: UpdateAdminRoutePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_route_manager),
) -> dict:
    route_id = _normalize_route_id(route_id)
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

    changes: list[str] = []
    if payload.number_auto is not None:
        item = _changed_text("ТС", route.number_auto, payload.number_auto)
        route.number_auto = payload.number_auto.strip()
        if item:
            changes.append(item)
    if payload.temperature is not None:
        item = _changed_text("Температура", route.temperature, payload.temperature)
        route.temperature = payload.temperature.strip()
        if item:
            changes.append(item)
    if payload.dispatcher_contacts is not None:
        item = _changed_text("Контакты диспетчера", route.dispatcher_contacts, payload.dispatcher_contacts)
        route.dispatcher_contacts = payload.dispatcher_contacts.strip()
        if item:
            changes.append(item)
    if payload.registration_number is not None:
        item = _changed_text("Рег. номер", route.registration_number, payload.registration_number)
        route.registration_number = payload.registration_number.strip()
        if item:
            changes.append(item)
    if payload.trailer_number is not None:
        item = _changed_text("Прицеп", route.trailer_number, payload.trailer_number)
        route.trailer_number = payload.trailer_number.strip()
        if item:
            changes.append(item)
    if payload.created_by_user_id:
        creator = _ensure_logistic(db, payload.created_by_user_id)
        if route.created_by_user_id != creator.id:
            old_creator = db.get(User, route.created_by_user_id) if route.created_by_user_id else None
            old_name = (old_creator.full_name or old_creator.login) if old_creator else "—"
            new_name = creator.full_name or creator.login
            route.created_by_user_id = creator.id
            changes.append(f"Логист: {old_name} → {new_name}")
    if payload.points is not None:
        _apply_points_replace(db, route, payload.points, preserve_progress=True)
        _sync_route_status_from_points(db, route)
        changes.append("Точки рейса")

    db.add(route)
    notify_driver_route_updated(db, route=route, actor_user=current_user, changes=changes)
    db.commit()
    db.refresh(route)
    return _route_out(db, route, include_points=True)


@router.delete("/{route_id:path}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route(
    route_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_route_manager),
) -> None:
    route_id = _normalize_route_id(route_id)
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

