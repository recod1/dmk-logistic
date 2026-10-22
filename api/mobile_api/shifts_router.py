from __future__ import annotations

import logging
import mimetypes
import uuid
from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_driver, get_current_user
from mobile_api.db import get_db
from mobile_api.models import DriverShift, DriverShiftImage, Point, Route, User
from mobile_api.point_documents_router import (
    MAX_FILE_BYTES,
    _atomic_write_bytes,
    _thumb_filename_for,
    _try_write_thumbnail_jpeg,
    _upload_root,
    _validate_image_content_type,
)
from mobile_api.roles import ADMIN_ACCESS_ROLES, RoleCode, normalize_role_code
from mobile_api.route_notification_logic import _manager_ids
from mobile_api.notifications_service import create_notification_for_users
from mobile_api.time_formatting import display_zone, format_dt_for_app

router = APIRouter(tags=["driver-shifts"])
logger = logging.getLogger(__name__)

VEHICLE_SLOTS = ("front", "rear", "left", "right")
SHIFT_VIEW_ROLES = ADMIN_ACCESS_ROLES | {RoleCode.LOGISTIC, RoleCode.DRIVER}


def shift_title(full_name: str | None, started_at: datetime | None, ended_at: datetime | None) -> str:
    name = (full_name or "").strip() or "Водитель"
    start = format_dt_for_app(started_at) or "—"
    end = format_dt_for_app(ended_at) if ended_at else "сейчас"
    return f"{name} · {start} — {end}"


def _role(user: User) -> RoleCode:
    try:
        return normalize_role_code(user.role_code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden") from exc


def _can_view_shifts(user: User) -> bool:
    return _role(user) in SHIFT_VIEW_ROLES


def _can_view_all_shifts(user: User) -> bool:
    return _role(user) in (ADMIN_ACCESS_ROLES | {RoleCode.LOGISTIC})


def _driver_name(db: Session, user_id: int) -> str:
    row = db.get(User, user_id)
    if row is None:
        return "Водитель"
    return (row.full_name or row.login or "Водитель").strip()


def _parse_day_bound(raw: str | None, *, end: bool) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    parsed: datetime | None = None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text[:10] if fmt == "%Y-%m-%d" and len(text) >= 10 else text, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        return None
    zone = display_zone()
    day = parsed.date()
    if end:
        return datetime.combine(day, time(23, 59, 59), tzinfo=zone)
    return datetime.combine(day, time(0, 0, 0), tzinfo=zone)


def _image_out(row: DriverShiftImage) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "slot": row.slot or "",
        "content_type": row.content_type,
    }


def _shift_out(db: Session, shift: DriverShift, *, include_details: bool = False) -> dict:
    name = _driver_name(db, shift.driver_user_id)
    payload = {
        "id": shift.id,
        "title": shift_title(name, shift.started_at, shift.ended_at),
        "driver_user_id": shift.driver_user_id,
        "driver_full_name": name,
        "started_at": shift.started_at.isoformat() if shift.started_at else None,
        "ended_at": shift.ended_at.isoformat() if shift.ended_at else None,
        "status": "ended" if shift.ended_at else "active",
    }
    if include_details:
        images = db.scalars(
            select(DriverShiftImage)
            .where(DriverShiftImage.shift_id == shift.id)
            .order_by(DriverShiftImage.id.asc())
        ).all()
        payload["images"] = [_image_out(row) for row in images]
        payload["routes"] = _routes_during_shift(db, shift)
    return payload


def _routes_during_shift(db: Session, shift: DriverShift) -> list[dict]:
    start = shift.started_at
    end = shift.ended_at or datetime.now(timezone.utc)
    rows = db.scalars(
        select(Route)
        .where(
            Route.assigned_user_id == shift.driver_user_id,
            Route.accepted_at.is_not(None),
            Route.accepted_at <= end,
            or_(
                Route.accepted_at >= start,
                Route.status.in_(("process", "success")),
            ),
        )
        .order_by(Route.accepted_at.desc(), Route.id.desc())
    ).all()
    out: list[dict] = []
    seen: set[str] = set()
    for route in rows:
        if route.status == "success" and route.updated_at and route.updated_at < start:
            continue
        if route.id in seen:
            continue
        seen.add(route.id)
        points_count = db.scalar(select(func.count()).select_from(Point).where(Point.route_id == route.id)) or 0
        out.append(
            {
                "id": route.id,
                "status": route.status,
                "number_auto": route.number_auto or "",
                "trailer_number": route.trailer_number or "",
                "accepted_at": route.accepted_at.isoformat() if route.accepted_at else None,
                "created_at": route.created_at.isoformat() if route.created_at else None,
                "points_count": int(points_count),
            }
        )
    return out


def _active_shift(db: Session, driver_user_id: int) -> DriverShift | None:
    return db.scalars(
        select(DriverShift)
        .where(DriverShift.driver_user_id == driver_user_id, DriverShift.ended_at.is_(None))
        .order_by(DriverShift.started_at.desc(), DriverShift.id.desc())
        .limit(1)
    ).first()


async def _read_image(upload: UploadFile) -> tuple[bytes, str]:
    ctype = upload.content_type or mimetypes.guess_type(upload.filename or "")[0] or "application/octet-stream"
    ctype = _validate_image_content_type(ctype)
    body = await upload.read()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пустое фото")
    if len(body) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large (max {MAX_FILE_BYTES} bytes)",
        )
    return body, ctype


def _store_image(
    db: Session,
    *,
    shift: DriverShift,
    user_id: int,
    kind: str,
    slot: str,
    body: bytes,
    content_type: str,
) -> DriverShiftImage:
    root = _upload_root()
    sub = root / "shifts" / str(shift.id)
    sub.mkdir(parents=True, exist_ok=True)
    ext = mimetypes.guess_extension(content_type) or ".jpg"
    if ext == ".jpe":
        ext = ".jpg"
    fname = f"{uuid.uuid4().hex}{ext}"
    full_path = sub / fname
    _atomic_write_bytes(full_path, body)
    _try_write_thumbnail_jpeg(full_path, body)
    row = DriverShiftImage(
        shift_id=shift.id,
        kind=kind,
        slot=slot,
        storage_path=f"shifts/{shift.id}/{fname}",
        content_type=content_type,
        file_size=len(body),
        uploaded_by_user_id=user_id,
    )
    db.add(row)
    return row


def _notify_shift(db: Session, *, shift: DriverShift, driver: User, started: bool) -> None:
    name = (driver.full_name or driver.login or "Водитель").strip()
    when = format_dt_for_app(shift.started_at if started else shift.ended_at) or ""
    action = "начал(а) вахту" if started else "закончил(а) вахту"
    event_type = "shift_started" if started else "shift_ended"
    title = "Вахта начата" if started else "Вахта закончена"
    create_notification_for_users(
        db,
        user_ids=_manager_ids(db),
        event_type=event_type,
        title=title,
        message=f"{name} {action} · {when}".strip(" ·"),
        payload={
            "shift_id": shift.id,
            "driver_user_id": driver.id,
            "driver_full_name": name,
            "started_at": shift.started_at.isoformat() if shift.started_at else None,
            "ended_at": shift.ended_at.isoformat() if shift.ended_at else None,
        },
        skip_user_ids=[driver.id],
    )


@router.get("/v1/shifts/me/active")
def get_my_active_shift(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    shift = _active_shift(db, current_user.id)
    return {"shift": _shift_out(db, shift) if shift else None}


@router.get("/v1/shifts")
def list_shifts(
    status_filter: str = Query(default="", alias="status"),
    q: str = Query(default=""),
    driver_user_id: int | None = Query(default=None),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if not _can_view_shifts(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    stmt = select(DriverShift)
    if not _can_view_all_shifts(current_user):
        stmt = stmt.where(DriverShift.driver_user_id == current_user.id)
    kind = (status_filter or "").strip().lower()
    if kind == "active":
        stmt = stmt.where(DriverShift.ended_at.is_(None))
    elif kind in {"ended", "finished", "done"}:
        stmt = stmt.where(DriverShift.ended_at.is_not(None))
    if driver_user_id:
        stmt = stmt.where(DriverShift.driver_user_id == int(driver_user_id))
    else:
        query = (q or "").strip()
        if query:
            driver_ids = db.scalars(
                select(User.id).where(
                    or_(
                        User.full_name.ilike(f"%{query}%"),
                        User.login.ilike(f"%{query}%"),
                    )
                )
            ).all()
            stmt = stmt.where(DriverShift.driver_user_id.in_(list(driver_ids) or [-1]))
    start_bound = _parse_day_bound(date_from, end=False)
    end_bound = _parse_day_bound(date_to, end=True)
    if start_bound is not None:
        stmt = stmt.where(or_(DriverShift.ended_at.is_(None), DriverShift.ended_at >= start_bound))
    if end_bound is not None:
        stmt = stmt.where(DriverShift.started_at <= end_bound)
    stmt = stmt.order_by(DriverShift.started_at.desc(), DriverShift.id.desc())
    rows = db.scalars(stmt.limit(300)).all()
    return {"items": [_shift_out(db, row) for row in rows]}


@router.get("/v1/shifts/{shift_id}")
def get_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if not _can_view_shifts(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    shift = db.get(DriverShift, shift_id)
    if shift is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if not _can_view_all_shifts(current_user) and int(shift.driver_user_id) != int(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return _shift_out(db, shift, include_details=True)


@router.post("/v1/shifts/start")
async def start_shift(
    front: UploadFile = File(...),
    rear: UploadFile = File(...),
    left: UploadFile = File(...),
    right: UploadFile = File(...),
    waybill: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    if _active_shift(db, current_user.id) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Вахта уже начата")
    if not waybill:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нужно фото путевого листа")
    vehicle_files = {"front": front, "rear": rear, "left": left, "right": right}
    vehicle_bodies: dict[str, tuple[bytes, str]] = {}
    for slot, upload in vehicle_files.items():
        vehicle_bodies[slot] = await _read_image(upload)
    waybill_bodies: list[tuple[bytes, str]] = []
    for upload in waybill:
        waybill_bodies.append(await _read_image(upload))
    shift = DriverShift(driver_user_id=current_user.id, started_at=datetime.now(timezone.utc))
    db.add(shift)
    db.flush()
    for slot in VEHICLE_SLOTS:
        body, ctype = vehicle_bodies[slot]
        _store_image(
            db,
            shift=shift,
            user_id=current_user.id,
            kind="start_vehicle",
            slot=slot,
            body=body,
            content_type=ctype,
        )
    for body, ctype in waybill_bodies:
        _store_image(
            db,
            shift=shift,
            user_id=current_user.id,
            kind="start_waybill",
            slot="",
            body=body,
            content_type=ctype,
        )
    _notify_shift(db, shift=shift, driver=current_user, started=True)
    db.commit()
    db.refresh(shift)
    return _shift_out(db, shift, include_details=True)


@router.post("/v1/shifts/{shift_id}/finish")
async def finish_shift(
    shift_id: int,
    front: UploadFile = File(...),
    rear: UploadFile = File(...),
    left: UploadFile = File(...),
    right: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    shift = db.get(DriverShift, shift_id)
    if shift is None or int(shift.driver_user_id) != int(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if shift.ended_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Вахта уже закончена")
    vehicle_files = {"front": front, "rear": rear, "left": left, "right": right}
    vehicle_bodies: dict[str, tuple[bytes, str]] = {}
    for slot, upload in vehicle_files.items():
        vehicle_bodies[slot] = await _read_image(upload)
    shift.ended_at = datetime.now(timezone.utc)
    for slot in VEHICLE_SLOTS:
        body, ctype = vehicle_bodies[slot]
        _store_image(
            db,
            shift=shift,
            user_id=current_user.id,
            kind="end_vehicle",
            slot=slot,
            body=body,
            content_type=ctype,
        )
    _notify_shift(db, shift=shift, driver=current_user, started=False)
    db.commit()
    db.refresh(shift)
    return _shift_out(db, shift, include_details=True)


@router.get("/v1/shift-images/{image_id}/file")
def download_shift_image(
    image_id: int,
    thumb: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    if not _can_view_shifts(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    row = db.get(DriverShiftImage, image_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    shift = db.get(DriverShift, row.shift_id)
    if shift is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if not _can_view_all_shifts(current_user) and int(shift.driver_user_id) != int(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    root = _upload_root()
    full_path = (root / row.storage_path).resolve()
    try:
        full_path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path") from exc
    if not full_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on server")
    serve_path = full_path
    media_type = row.content_type or "application/octet-stream"
    if thumb:
        thumb_path = full_path.parent / _thumb_filename_for(full_path.name)
        if thumb_path.is_file():
            serve_path = thumb_path
            media_type = "image/jpeg"
    return FileResponse(
        path=str(serve_path),
        media_type=media_type,
        filename=serve_path.name,
        headers={"Cache-Control": "private, max-age=86400"},
    )
