from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_fleet_editor, get_current_route_manager
from mobile_api.db import get_db
from mobile_api.driver_trip_rules import DriverRouteState, pick_active_route
from mobile_api.models import FleetTrailer, FleetVehicle, Route, User
from mobile_api.presence import list_presence_history, presence_fields, queue_presence_probes
from mobile_api.roles import RoleCode
from mobile_api.time_formatting import format_dt_for_app
from utils.vehicle_plate import require_plate

router = APIRouter(tags=["fleet"])


class FleetPlateBody(BaseModel):
    plate: str = Field(min_length=1, max_length=32)


def _item_out(row: FleetVehicle | FleetTrailer) -> dict:
    return {
        "id": int(row.id),
        "plate": row.plate,
        "updated_at": row.updated_at.isoformat() if isinstance(row.updated_at, datetime) else str(row.updated_at),
    }


def _http_plate(raw: str) -> str:
    try:
        return require_plate(raw)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


def ensure_fleet_vehicle(db: Session, plate: str) -> FleetVehicle | None:
    cleaned = (plate or "").strip()
    if not cleaned:
        return None
    try:
        normalized = require_plate(cleaned)
    except ValueError:
        return None
    existing = db.scalar(select(FleetVehicle).where(FleetVehicle.plate == normalized))
    if existing is not None:
        return existing
    row = FleetVehicle(plate=normalized)
    db.add(row)
    return row


def ensure_fleet_trailer(db: Session, plate: str) -> FleetTrailer | None:
    cleaned = (plate or "").strip()
    if not cleaned:
        return None
    try:
        normalized = require_plate(cleaned)
    except ValueError:
        return None
    existing = db.scalar(select(FleetTrailer).where(FleetTrailer.plate == normalized))
    if existing is not None:
        return existing
    row = FleetTrailer(plate=normalized)
    db.add(row)
    return row


@router.get("/v1/fleet/vehicles")
def list_vehicles(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_route_manager),
) -> dict:
    rows = db.scalars(select(FleetVehicle).order_by(FleetVehicle.plate.asc())).all()
    return {"items": [_item_out(row) for row in rows]}


@router.post("/v1/fleet/vehicles", status_code=status.HTTP_201_CREATED)
def create_vehicle(
    payload: FleetPlateBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_fleet_editor),
) -> dict:
    plate = _http_plate(payload.plate)
    if db.scalar(select(FleetVehicle).where(FleetVehicle.plate == plate)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Такой номер ТС уже есть в списке")
    row = FleetVehicle(plate=plate)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _item_out(row)


@router.patch("/v1/fleet/vehicles/{item_id}")
def update_vehicle(
    item_id: int,
    payload: FleetPlateBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_fleet_editor),
) -> dict:
    row = db.get(FleetVehicle, item_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ТС не найден")
    plate = _http_plate(payload.plate)
    other = db.scalar(select(FleetVehicle).where(FleetVehicle.plate == plate, FleetVehicle.id != item_id))
    if other is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Такой номер ТС уже есть в списке")
    row.plate = plate
    db.commit()
    db.refresh(row)
    return _item_out(row)


@router.delete("/v1/fleet/vehicles/{item_id}")
def delete_vehicle(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_fleet_editor),
) -> dict:
    row = db.get(FleetVehicle, item_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ТС не найден")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/v1/fleet/trailers")
def list_trailers(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_route_manager),
) -> dict:
    rows = db.scalars(select(FleetTrailer).order_by(FleetTrailer.plate.asc())).all()
    return {"items": [_item_out(row) for row in rows]}


@router.post("/v1/fleet/trailers", status_code=status.HTTP_201_CREATED)
def create_trailer(
    payload: FleetPlateBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_fleet_editor),
) -> dict:
    plate = _http_plate(payload.plate)
    if db.scalar(select(FleetTrailer).where(FleetTrailer.plate == plate)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Такой номер прицепа уже есть в списке")
    row = FleetTrailer(plate=plate)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _item_out(row)


@router.patch("/v1/fleet/trailers/{item_id}")
def update_trailer(
    item_id: int,
    payload: FleetPlateBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_fleet_editor),
) -> dict:
    row = db.get(FleetTrailer, item_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Прицеп не найден")
    plate = _http_plate(payload.plate)
    other = db.scalar(select(FleetTrailer).where(FleetTrailer.plate == plate, FleetTrailer.id != item_id))
    if other is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Такой номер прицепа уже есть в списке")
    row.plate = plate
    db.commit()
    db.refresh(row)
    return _item_out(row)


@router.delete("/v1/fleet/trailers/{item_id}")
def delete_trailer(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_fleet_editor),
) -> dict:
    row = db.get(FleetTrailer, item_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Прицеп не найден")
    db.delete(row)
    db.commit()
    return {"ok": True}


def _active_routes_by_driver(db: Session, driver_ids: list[int]) -> dict[int, list[Route]]:
    routes = (
        db.scalars(select(Route).where(Route.assigned_user_id.in_(driver_ids), Route.status.in_(["new", "process"]))).all()
        if driver_ids
        else []
    )
    by_driver: dict[int, list[Route]] = {}
    for route in routes:
        if route.assigned_user_id:
            by_driver.setdefault(int(route.assigned_user_id), []).append(route)
    return by_driver


def _driver_live_out(driver: User, assigned: list[Route]) -> dict:
    states = [DriverRouteState(id=r.id, status=r.status, created_at=r.created_at) for r in assigned]
    active_state = pick_active_route(states)
    active = next((r for r in assigned if active_state and r.id == active_state.id), None)
    presence = presence_fields(driver)
    lat = presence["last_lat"] if presence["last_lat"] is not None else (active.driver_lat if active else None)
    lng = presence["last_lng"] if presence["last_lng"] is not None else (active.driver_lng if active else None)
    loc_at = presence["last_location_at"] or (format_dt_for_app(active.driver_location_at) if active else None)
    return {
        "id": int(driver.id),
        "login": driver.login,
        "full_name": driver.full_name,
        "phone": driver.phone,
        "route_id": active.id if active else None,
        "route_status": active.status if active else None,
        "number_auto": (active.number_auto if active else "") or "",
        "lat": lat,
        "lng": lng,
        "location_at": loc_at,
        **presence,
    }


@router.get("/v1/fleet/drivers")
def list_live_drivers(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_fleet_editor),
) -> dict:
    drivers = db.scalars(
        select(User)
        .where(User.role_code == RoleCode.DRIVER.value, User.is_active.is_(True))
        .order_by(User.full_name.asc(), User.login.asc(), User.id.asc())
    ).all()
    by_driver = _active_routes_by_driver(db, [int(d.id) for d in drivers])
    items = [_driver_live_out(driver, by_driver.get(int(driver.id), [])) for driver in drivers]
    queue_presence_probes(db, list(drivers))
    return {"items": items}


@router.get("/v1/fleet/drivers/{user_id}")
def get_live_driver(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_fleet_editor),
) -> dict:
    driver = db.get(User, user_id)
    if driver is None or driver.role_code != RoleCode.DRIVER.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Водитель не найден")
    by_driver = _active_routes_by_driver(db, [int(driver.id)])
    payload = _driver_live_out(driver, by_driver.get(int(driver.id), []))
    payload["history"] = list_presence_history(db, int(driver.id))
    return payload
