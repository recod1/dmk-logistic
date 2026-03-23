from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from mobile_api.auth import create_access_token, get_current_user, verify_password
from mobile_api.db import get_db
from mobile_api.models import Point, Route, RouteEvent, RoutePoint, User


POINT_STATUS_FLOW = {
    "new": "process",
    "process": "registration",
    "registration": "load",
    "load": "docs",
    "docs": "success",
}

STATUS_TIME_COLUMN = {
    "process": "time_accepted",
    "registration": "time_registration",
    "load": "time_put_on_gate",
    "docs": "time_docs",
    "success": "time_departure",
}


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class BatchEventPayload(BaseModel):
    client_event_id: str = Field(min_length=1, max_length=128)
    occurred_at_client: datetime
    point_id: int
    to_status: Literal["process", "registration", "load", "docs", "success"]


class BatchEventsRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    events: list[BatchEventPayload] = Field(default_factory=list, max_items=500)


router = APIRouter(tags=["mobile-v1"])


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _point_to_dict(point: Point) -> dict:
    return {
        "id": point.id,
        "route_id": point.route_id,
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
    return {
        "id": route.id,
        "status": route.status,
        "number_auto": route.number_auto,
        "temperature": route.temperature,
        "dispatcher_contacts": route.dispatcher_contacts,
        "registration_number": route.registration_number,
        "trailer_number": route.trailer_number,
        "accepted_at": route.accepted_at.isoformat() if route.accepted_at else None,
        "points": [_point_to_dict(p) for p in points],
    }


def _active_route_for_user(db: Session, user_id: int) -> Route | None:
    return db.scalar(
        select(Route)
        .where(Route.assigned_user_id == user_id, Route.status.in_(["new", "process"]))
        .order_by(
            case((Route.status == "process", 0), else_=1),
            Route.created_at.desc(),
        )
        .limit(1)
    )


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
            "role": user.role,
            "full_name": user.full_name,
        },
    }


@router.get("/v1/mobile/routes/active")
def get_active_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    route = _active_route_for_user(db, current_user.id)
    if route is None:
        return {"route": None}
    return {"route": _route_snapshot(db, route)}


@router.post("/v1/mobile/routes/{route_id}/accept")
def accept_route(
    route_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    if route.assigned_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Route is assigned to another user")
    if route.status not in {"new", "process"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Route already {route.status}")
    if route.status == "new":
        route.status = "process"
        route.accepted_at = datetime.now(timezone.utc)
        db.add(route)
        db.commit()
        db.refresh(route)

    return {"route": _route_snapshot(db, route)}


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
    return True, None


def _refresh_route_status_if_completed(db: Session, route: Route) -> None:
    point_statuses = db.scalars(select(Point.status).where(Point.route_id == route.id)).all()
    if point_statuses and all(status == "success" for status in point_statuses):
        route.status = "success"
        db.add(route)


@router.post("/v1/mobile/events:batch")
def batch_events(
    payload: BatchEventsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
        applied, error = _try_apply_point_status(point, event.to_status, event.occurred_at_client)
        stored_event = RouteEvent(
            route_id=route.id,
            point_id=event.point_id,
            user_id=current_user.id,
            device_id=payload.device_id,
            client_event_id=event.client_event_id,
            occurred_at_client=_as_utc(event.occurred_at_client),
            to_status=event.to_status,
            applied=applied,
            error=error,
            server_received_at=server_received_at,
        )
        db.add(stored_event)
        if applied:
            db.add(point)
            _refresh_route_status_if_completed(db, route)

        delta_ms = int((server_received_at - _as_utc(event.occurred_at_client)).total_seconds() * 1000)
        results.append(
            {
                "client_event_id": event.client_event_id,
                "point_id": event.point_id,
                "to_status": event.to_status,
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

