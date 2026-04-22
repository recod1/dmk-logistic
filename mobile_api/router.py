from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from mobile_api.auth import create_access_token, get_current_driver, verify_password
from mobile_api.db import get_db
from mobile_api.driver_trip_rules import DriverRouteState, can_accept_route, pick_active_route
from mobile_api.models import Point, PointDocumentImage, Route, RouteEvent, RoutePoint, User
from mobile_api.route_notification_logic import (
    notify_point_status_changed,
    notify_point_status_reverted,
    notify_route_accepted_by_driver,
    notify_route_completed,
)
from mobile_api.time_formatting import format_dt_for_app
from mobile_api.roles import role_label_ru
from services.wialon_service import WIALON_ENABLED, get_vehicle_location_data, vehicle_number_for_wialon


logger = logging.getLogger(__name__)

POINT_STATUS_FLOW = {
    "new": "process",
    "process": "registration",
    "registration": "load",
    "load": "docs",
}

POINT_STATUS_REVERSE = {
    "process": "new",
    "registration": "process",
    "load": "registration",
    "docs": "load",
}

STATUS_CLEAR_WHEN_REVERTING_FROM = {
    "process": ("departure_time", "time_accepted"),
    "registration": ("registration_time", "time_registration"),
    "load": ("gate_time", "time_put_on_gate"),
    "docs": ("docs_time", "time_docs"),
}

COMPLETED_POINT_STATUSES = {"docs", "success"}

STATUS_TIME_COLUMN = {
    "process": "departure_time",
    "registration": "registration_time",
    "load": "gate_time",
    "docs": "docs_time",
}

LEGACY_STATUS_TIME_COLUMN = {
    "process": "time_accepted",
    "registration": "time_registration",
    "load": "time_put_on_gate",
    "docs": "time_docs",
}


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class BatchEventPayload(BaseModel):
    client_event_id: str = Field(min_length=1, max_length=128)
    occurred_at_client: datetime
    point_id: int
    to_status: Literal["process", "registration", "load", "docs", "success"]
    time_source: Literal["device", "manual"] | None = None
    odometer: str | None = Field(default=None, max_length=128)
    coordinates: dict | None = None
    document_file_ids: list[int] | None = Field(default=None, max_length=32)


class BatchEventsRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    events: list[BatchEventPayload] = Field(default_factory=list, max_items=500)


router = APIRouter(tags=["mobile-v1"])


def _as_utc(dt: datetime) -> datetime:
    """UTC instant; PWA шлёт occurred_at_client как ISO 8601 из Date.toISOString() (смещение устройства учтено на клиенте)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_datetime_ru(dt: datetime | None) -> str | None:
    return format_dt_for_app(dt)


def _point_to_dict(
    point: Point,
    docs_meta: list[dict] | None = None,
    time_sources: dict[str, str] | None = None,
) -> dict:
    sources = time_sources or {}
    return {
        "id": point.id,
        "route_id": point.route_id,
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
        "departure_time_source": sources.get("process"),
        "departure_odometer": point.departure_odometer,
        "departure_coordinates": {"lat": point.departure_lat, "lng": point.departure_lng},
        "registration_time": _format_datetime_ru(point.registration_time),
        "registration_time_source": sources.get("registration"),
        "registration_odometer": point.registration_odometer,
        "registration_coordinates": {"lat": point.registration_lat, "lng": point.registration_lng},
        "gate_time": _format_datetime_ru(point.gate_time),
        "gate_time_source": sources.get("load"),
        "gate_odometer": point.gate_odometer,
        "gate_coordinates": {"lat": point.gate_lat, "lng": point.gate_lng},
        "docs_time": _format_datetime_ru(point.docs_time),
        "docs_time_source": sources.get("docs"),
        "docs_odometer": point.docs_odometer,
        "docs_coordinates": {"lat": point.docs_lat, "lng": point.docs_lng},
        "odometer": point.odometer,
        "coordinates": {"lat": point.lat, "lng": point.lng},
        "docs_images": docs_meta or [],
    }


def _get_ordered_points(db: Session, route_id: str) -> list[Point]:
    ordered_ids = db.scalars(
        select(RoutePoint.point_id).where(RoutePoint.route_id == route_id).order_by(RoutePoint.order_index)
    ).all()
    if ordered_ids:
        points = db.scalars(select(Point).where(Point.id.in_(ordered_ids))).all()
        by_id = {p.id: p for p in points}
        return [by_id[point_id] for point_id in ordered_ids if point_id in by_id]

    return db.scalars(select(Point).where(Point.route_id == route_id).order_by(Point.id)).all()


def _route_snapshot(db: Session, route: Route) -> dict:
    points = _get_ordered_points(db, route.id)
    point_ids = [p.id for p in points]
    by_point: dict[int, list[PointDocumentImage]] = defaultdict(list)
    if point_ids:
        imgs = db.scalars(
            select(PointDocumentImage)
            .where(PointDocumentImage.point_id.in_(point_ids))
            .order_by(PointDocumentImage.id.asc())
        ).all()
        for img in imgs:
            by_point[img.point_id].append(img)

    sources_by_point: dict[int, dict[str, str]] = defaultdict(dict)
    if point_ids:
        # Track latest time source for each point + status (process/registration/load/docs).
        # We rely on server_received_at as a monotonic-ish "latest applied" ordering.
        rows = db.scalars(
            select(RouteEvent)
            .where(
                RouteEvent.point_id.in_(point_ids),
                RouteEvent.applied.is_(True),
                RouteEvent.time_source.isnot(None),
            )
            .order_by(RouteEvent.server_received_at.desc(), RouteEvent.id.desc())
        ).all()
        for ev in rows:
            if ev.point_id is None or not ev.to_status:
                continue
            if ev.to_status not in {"process", "registration", "load", "docs"}:
                continue
            if ev.to_status in sources_by_point[int(ev.point_id)]:
                continue
            if ev.time_source:
                sources_by_point[int(ev.point_id)][str(ev.to_status)] = str(ev.time_source)
    return {
        "id": route.id,
        "status": route.status,
        "number_auto": route.number_auto,
        "temperature": route.temperature,
        "dispatcher_contacts": route.dispatcher_contacts,
        "registration_number": route.registration_number,
        "trailer_number": route.trailer_number,
        "created_at": route.created_at.isoformat() if route.created_at else None,
        "accepted_at": route.accepted_at.isoformat() if route.accepted_at else None,
        "points": [
            _point_to_dict(
                p,
                [{"id": x.id, "content_type": x.content_type} for x in by_point.get(p.id, [])],
                sources_by_point.get(int(p.id), {}),
            )
            for p in points
        ],
    }


def _active_route_for_user(db: Session, user_id: int) -> Route | None:
    rows = db.scalars(
        select(Route)
        .where(Route.assigned_user_id == user_id, Route.status.in_(["new", "process"]))
        .order_by(Route.created_at.asc(), Route.id.asc())
    ).all()
    if not rows:
        return None
    active = pick_active_route(
        [
            DriverRouteState(id=item.id, status=item.status, created_at=item.created_at)
            for item in rows
        ]
    )
    if active is None:
        return None
    return next((route for route in rows if route.id == active.id), None)


def _driver_routes_for_user(db: Session, user_id: int) -> list[Route]:
    return db.scalars(
        select(Route)
        .where(Route.assigned_user_id == user_id)
        .order_by(
            case((Route.status == "process", 0), (Route.status == "new", 1), else_=2),
            Route.created_at.asc(),
        )
    ).all()


def _route_summary(db: Session, route: Route) -> dict:
    points = _get_ordered_points(db, route.id)
    active_point = next(
        (point for point in points if point.status not in COMPLETED_POINT_STATUSES),
        points[-1] if points else None,
    )
    return {
        "id": route.id,
        "status": route.status,
        "number_auto": route.number_auto,
        "temperature": route.temperature,
        "dispatcher_contacts": route.dispatcher_contacts,
        "registration_number": route.registration_number,
        "trailer_number": route.trailer_number,
        "created_at": route.created_at.isoformat() if route.created_at else None,
        "accepted_at": route.accepted_at.isoformat() if route.accepted_at else None,
        "points_count": len(points),
        "active_point_id": active_point.id if active_point else None,
        "active_point_status": active_point.status if active_point else None,
    }


def _recalculate_driver_routes_completion(db: Session, user_id: int) -> bool:
    rows = _driver_routes_for_user(db, user_id)
    has_changes = False
    for route in rows:
        if _refresh_route_status_if_completed(db, route):
            has_changes = True
    return has_changes


@router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.login == payload.login))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login or password")

    access_token, expires_at = create_access_token(user)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_at": expires_at.isoformat(),
        "user": {
            "id": user.id,
            "login": user.login,
            "role": user.role_code,
            "role_code": user.role_code,
            "role_label": role_label_ru(user.role_code),
            "full_name": user.full_name,
            "phone": user.phone,
        },
    }


@router.get("/v1/mobile/routes/active")
def get_active_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    if _recalculate_driver_routes_completion(db, current_user.id):
        db.commit()
    route = _active_route_for_user(db, current_user.id)
    if route is None:
        return {"route": None}
    return {"route": _route_snapshot(db, route)}


@router.get("/v1/mobile/routes")
def list_driver_routes(
    scope: Literal["assigned", "history", "all"] = "assigned",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    if _recalculate_driver_routes_completion(db, current_user.id):
        db.commit()
    all_routes = _driver_routes_for_user(db, current_user.id)
    if scope == "assigned":
        routes = [route for route in all_routes if route.status in {"new", "process"}]
    elif scope == "history":
        routes = [route for route in all_routes if route.status in {"success", "cancelled"}]
    else:
        routes = all_routes

    active = pick_active_route(
        [DriverRouteState(id=item.id, status=item.status, created_at=item.created_at) for item in all_routes]
    )
    return {
        "items": [_route_summary(db, route) for route in routes],
        "active_route_id": active.id if active else None,
    }


@router.get("/v1/mobile/routes/{route_id}")
def get_driver_route(
    route_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    if route.assigned_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Route is assigned to another user")
    if _refresh_route_status_if_completed(db, route):
        db.commit()
        db.refresh(route)
    return {"route": _route_snapshot(db, route)}


@router.post("/v1/mobile/routes/{route_id}/accept")
def accept_route(
    route_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    all_routes = _driver_routes_for_user(db, current_user.id)
    route = next((item for item in all_routes if item.id == route_id), None)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

    allowed, reason = can_accept_route(
        route_id,
        [DriverRouteState(id=item.id, status=item.status, created_at=item.created_at) for item in all_routes],
    )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason or "Route cannot be accepted")

    if route.status == "new":
        route.status = "process"
        route.accepted_at = datetime.now(timezone.utc)
        db.add(route)
        notify_route_accepted_by_driver(
            db,
            route=route,
            driver_user=current_user,
            actor_user=current_user,
        )
        db.commit()
        db.refresh(route)

    return {"route": _route_snapshot(db, route)}


def _validate_document_ids_for_docs(
    db: Session, *, point: Point, user_id: int, file_ids: list[int] | None
) -> str | None:
    ids = list(file_ids or [])
    if not ids:
        return "Для статуса «Забрал документы» необходимо загрузить хотя бы одно фото"
    if len(ids) > 32:
        return "Слишком много файлов документов"
    uniq = sorted({int(x) for x in ids})
    rows = db.scalars(
        select(PointDocumentImage).where(
            PointDocumentImage.id.in_(uniq),
            PointDocumentImage.point_id == point.id,
            PointDocumentImage.uploaded_by_user_id == user_id,
        )
    ).all()
    if len(rows) != len(uniq):
        return "Некорректные вложения документов"
    return None


def _try_apply_point_status(point: Point, to_status: str, occurred_at_client: datetime) -> tuple[bool, str | None]:
    occurred_at_client = _as_utc(occurred_at_client)

    if point.status == to_status:
        return True, None

    expected_next = POINT_STATUS_FLOW.get(point.status)
    if expected_next != to_status:
        return False, f"Invalid transition: {point.status} -> {to_status}"

    point.status = to_status
    time_column = STATUS_TIME_COLUMN.get(to_status)
    if time_column:
        setattr(point, time_column, occurred_at_client)
    legacy_time_column = LEGACY_STATUS_TIME_COLUMN.get(to_status)
    if legacy_time_column:
        setattr(point, legacy_time_column, occurred_at_client)
    return True, None


def _normalize_target_status(to_status: str) -> str:
    # Поддержка старых офлайн-событий, где последним статусом точки был "success".
    if to_status == "success":
        return "docs"
    return to_status


def _telemetry_odometer_ok(value: str | None) -> bool:
    if value is None:
        return False
    return bool(str(value).strip())


def _telemetry_coords_ok(value: dict | None) -> bool:
    if not value or not isinstance(value, dict):
        return False
    lat_raw, lng_raw = value.get("lat"), value.get("lng")
    if not isinstance(lat_raw, (int, float)) or not isinstance(lng_raw, (int, float)):
        return False
    return not (float(lat_raw) == 0.0 and float(lng_raw) == 0.0)


def _apply_point_telemetry(point: Point, status_value: str, odometer: str | None, coordinates: dict | None) -> None:
    odometer_value: str | None = None
    lat_value: float | None = None
    lng_value: float | None = None

    if odometer is not None:
        odometer_value = odometer.strip() if isinstance(odometer, str) else str(odometer)
        point.odometer = odometer_value
    if coordinates and isinstance(coordinates, dict):
        lat_raw = coordinates.get("lat")
        lng_raw = coordinates.get("lng")
        if isinstance(lat_raw, (int, float)):
            lat_value = float(lat_raw)
            point.lat = lat_value
        if isinstance(lng_raw, (int, float)):
            lng_value = float(lng_raw)
            point.lng = lng_value

    if status_value == "process":
        if odometer_value is not None:
            point.departure_odometer = odometer_value
        if lat_value is not None:
            point.departure_lat = lat_value
        if lng_value is not None:
            point.departure_lng = lng_value
    elif status_value == "registration":
        if odometer_value is not None:
            point.registration_odometer = odometer_value
        if lat_value is not None:
            point.registration_lat = lat_value
        if lng_value is not None:
            point.registration_lng = lng_value
    elif status_value == "load":
        if odometer_value is not None:
            point.gate_odometer = odometer_value
        if lat_value is not None:
            point.gate_lat = lat_value
        if lng_value is not None:
            point.gate_lng = lng_value
    elif status_value == "docs":
        if odometer_value is not None:
            point.docs_odometer = odometer_value
        if lat_value is not None:
            point.docs_lat = lat_value
        if lng_value is not None:
            point.docs_lng = lng_value


def _refresh_route_status_if_completed(db: Session, route: Route) -> bool:
    if route.status in {"cancelled", "success"}:
        return False

    point_statuses = db.scalars(select(Point.status).where(Point.route_id == route.id)).all()
    if point_statuses and all(status_value in COMPLETED_POINT_STATUSES for status_value in point_statuses):
        route.status = "success"
        db.add(route)
        return True
    return False


def _downgrade_route_from_success_if_needed(db: Session, route: Route) -> None:
    if route.status != "success":
        return
    point_statuses = db.scalars(select(Point.status).where(Point.route_id == route.id)).all()
    if not point_statuses:
        return
    if all(status_value in COMPLETED_POINT_STATUSES for status_value in point_statuses):
        return
    route.status = "process"
    db.add(route)


@router.post("/v1/mobile/points/{point_id}/status:revert")
def revert_point_status_endpoint(
    point_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    point = db.get(Point, point_id)
    if point is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Point not found")
    route = db.get(Route, point.route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    if route.assigned_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Point is not available for current user")
    if route.status not in {"new", "process", "success"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Route status does not allow changes")
    if point.status not in POINT_STATUS_REVERSE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot revert this point status")

    previous = POINT_STATUS_REVERSE[point.status]
    for column_name in STATUS_CLEAR_WHEN_REVERTING_FROM.get(point.status, ()):
        setattr(point, column_name, None)
    point.status = previous
    db.add(point)

    _downgrade_route_from_success_if_needed(db, route)
    notify_point_status_reverted(
        db,
        route=route,
        point=point,
        actor_user=current_user,
        previous_status=previous,
    )
    db.commit()
    db.refresh(route)
    return {"route": _route_snapshot(db, route)}


@router.post("/v1/mobile/events:batch")
def batch_events(
    payload: BatchEventsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    results: list[dict] = []

    for event in payload.events:
        existing = db.scalar(
            select(RouteEvent).where(
                RouteEvent.user_id == current_user.id,
                RouteEvent.device_id == payload.device_id,
                RouteEvent.client_event_id == event.client_event_id,
            )
        )
        if existing is not None:
            results.append(
                {
                    "client_event_id": existing.client_event_id,
                    "point_id": existing.point_id,
                    "to_status": existing.to_status,
                    "applied": existing.applied,
                    "duplicate": True,
                    "error": existing.error,
                    "server_received_at": existing.server_received_at.isoformat(),
                }
            )
            continue

        point = db.get(Point, event.point_id)
        if point is None:
            server_received_at = datetime.now(timezone.utc)
            results.append(
                {
                    "client_event_id": event.client_event_id,
                    "point_id": event.point_id,
                    "to_status": event.to_status,
                    "applied": False,
                    "duplicate": False,
                    "error": "Point not found",
                    "server_received_at": server_received_at.isoformat(),
                }
            )
            continue

        route = db.get(Route, point.route_id)
        if route is None:
            server_received_at = datetime.now(timezone.utc)
            results.append(
                {
                    "client_event_id": event.client_event_id,
                    "point_id": event.point_id,
                    "to_status": event.to_status,
                    "applied": False,
                    "duplicate": False,
                    "error": "Route not found",
                    "server_received_at": server_received_at.isoformat(),
                }
            )
            continue

        if route.assigned_user_id != current_user.id:
            server_received_at = datetime.now(timezone.utc)
            stored_event = RouteEvent(
                route_id=point.route_id,
                point_id=event.point_id,
                user_id=current_user.id,
                device_id=payload.device_id,
                client_event_id=event.client_event_id,
                occurred_at_client=_as_utc(event.occurred_at_client),
                to_status=event.to_status,
                time_source=event.time_source,
                applied=False,
                error="Point is not available for current user",
                server_received_at=server_received_at,
            )
            db.add(stored_event)
            results.append(
                {
                    "client_event_id": event.client_event_id,
                    "point_id": event.point_id,
                    "to_status": event.to_status,
                    "applied": False,
                    "duplicate": False,
                    "error": "Point is not available for current user",
                    "server_received_at": server_received_at.isoformat(),
                }
            )
            continue

        server_received_at = datetime.now(timezone.utc)
        target_status = _normalize_target_status(event.to_status)

        doc_err: str | None = None
        if target_status == "docs":
            doc_err = _validate_document_ids_for_docs(
                db,
                point=point,
                user_id=current_user.id,
                file_ids=event.document_file_ids,
            )

        if doc_err:
            stored_event = RouteEvent(
                route_id=route.id,
                point_id=event.point_id,
                user_id=current_user.id,
                device_id=payload.device_id,
                client_event_id=event.client_event_id,
                occurred_at_client=_as_utc(event.occurred_at_client),
                to_status=target_status,
                time_source=event.time_source,
                applied=False,
                error=doc_err,
                server_received_at=server_received_at,
            )
            db.add(stored_event)
            results.append(
                {
                    "client_event_id": event.client_event_id,
                    "point_id": event.point_id,
                    "to_status": target_status,
                    "applied": False,
                    "duplicate": False,
                    "error": doc_err,
                    "server_received_at": server_received_at.isoformat(),
                }
            )
            continue

        applied, error = _try_apply_point_status(point, target_status, event.occurred_at_client)
        stored_event = RouteEvent(
            route_id=route.id,
            point_id=event.point_id,
            user_id=current_user.id,
            device_id=payload.device_id,
            client_event_id=event.client_event_id,
            occurred_at_client=_as_utc(event.occurred_at_client),
            to_status=target_status,
            time_source=event.time_source,
            applied=applied,
            error=error,
            server_received_at=server_received_at,
        )
        db.add(stored_event)
        if applied:
            odometer = event.odometer
            coordinates = event.coordinates
            vehicle_no = vehicle_number_for_wialon(route.number_auto, route.registration_number)
            need_odom = not _telemetry_odometer_ok(odometer)
            need_coords = not _telemetry_coords_ok(coordinates)
            try:
                if not WIALON_ENABLED:
                    logger.info(
                        "mobile_events wialon: skip (Wialon disabled / no token) route_id=%s point_id=%s -> %s",
                        route.id,
                        point.id,
                        target_status,
                    )
                elif not vehicle_no:
                    logger.info(
                        "mobile_events wialon: skip (empty vehicle number) route_id=%s point_id=%s -> %s",
                        route.id,
                        point.id,
                        target_status,
                    )
                elif not need_odom and not need_coords:
                    logger.info(
                        "mobile_events wialon: skip (telemetry from client) route_id=%s point_id=%s -> %s",
                        route.id,
                        point.id,
                        target_status,
                    )
                else:
                    logger.info(
                        "mobile_events wialon: request route_id=%s point_id=%s -> %s vehicle_no=%r need_odom=%s need_coords=%s",
                        route.id,
                        point.id,
                        target_status,
                        vehicle_no,
                        need_odom,
                        need_coords,
                    )
                    wialon = get_vehicle_location_data(vehicle_no)
                    if not wialon:
                        logger.warning(
                            "mobile_events wialon: NO DATA for vehicle_no=%r route_id=%s point_id=%s "
                            "(токен, имя юнита, позиция; при HTML в логах Wialon — проверьте WIALON_BASE_URL, хост должен быть Remote API)",
                            vehicle_no,
                            route.id,
                            point.id,
                        )
                    else:
                        if need_odom:
                            odometer = wialon.get("odometer") or odometer
                        if need_coords:
                            coordinates = {"lat": wialon.get("lat"), "lng": wialon.get("lng")}
                        logger.info(
                            "mobile_events wialon: merged route_id=%s point_id=%s -> %s lat=%s lng=%s odometer=%r",
                            route.id,
                            point.id,
                            target_status,
                            (coordinates or {}).get("lat") if isinstance(coordinates, dict) else None,
                            (coordinates or {}).get("lng") if isinstance(coordinates, dict) else None,
                            odometer,
                        )
            except Exception as exc:
                logger.warning(
                    "mobile_events wialon: error route_id=%s point_id=%s vehicle_no=%r: %s",
                    route.id,
                    point.id,
                    vehicle_no,
                    exc,
                    exc_info=True,
                )

            _apply_point_telemetry(point, target_status, odometer, coordinates)
            db.add(point)
            route_completed_now = _refresh_route_status_if_completed(db, route)
            notify_point_status_changed(
                db,
                route=route,
                point=point,
                actor_user=current_user,
                new_status=target_status,
            )
            db.flush()
            if route_completed_now:
                notify_route_completed(
                    db,
                    route=route,
                    actor_user=current_user,
                )

        delta_ms = int((server_received_at - _as_utc(event.occurred_at_client)).total_seconds() * 1000)
        results.append(
            {
                "client_event_id": event.client_event_id,
                "point_id": event.point_id,
                "to_status": target_status,
                "applied": applied,
                "duplicate": False,
                "error": error,
                "server_received_at": server_received_at.isoformat(),
                "server_time_delta_ms": delta_ms,
            }
        )

    db.commit()
    applied_count = sum(1 for r in results if r.get("applied"))
    return {
        "items": results,
        "applied": applied_count,
        "received": len(payload.events),
        "server_received_at": datetime.now(timezone.utc).isoformat(),
    }

