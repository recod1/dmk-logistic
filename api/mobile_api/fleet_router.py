from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_fleet_editor, get_current_route_manager
from mobile_api.db import get_db
from mobile_api.models import FleetTrailer, FleetVehicle, User
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
