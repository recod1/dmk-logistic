from __future__ import annotations

import json
import logging
import mimetypes
import uuid
from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
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
from mobile_api.shift_inspection import (
    LEGACY_END_KINDS,
    LEGACY_START_KINDS,
    OPEN_WORKFLOWS,
    PHOTO_KIND_END,
    PHOTO_KIND_START,
    WORKFLOW_ACTIVE,
    WORKFLOW_CLOSED,
    WORKFLOW_CLOSING,
    WORKFLOW_DRAFT,
    as_dict,
    as_list,
    blocking_issues,
    dump_json,
    empty_phase,
    handover_from_intake,
    parse_json,
    photo_slots,
)
from mobile_api.time_formatting import display_zone, format_dt_for_app

router = APIRouter(tags=["driver-shifts"])
logger = logging.getLogger(__name__)

VEHICLE_SLOTS = ("front", "rear", "left", "right")
SHIFT_VIEW_ROLES = ADMIN_ACCESS_ROLES | {RoleCode.LOGISTIC, RoleCode.DRIVER}
WORKFLOW_LABELS = {
    WORKFLOW_DRAFT: "Приёмка",
    WORKFLOW_ACTIVE: "Идёт вахта",
    WORKFLOW_CLOSING: "Сдача",
    WORKFLOW_CLOSED: "Завершена",
}


class ShiftPatchBody(BaseModel):
    driver_name: str | None = Field(default=None, max_length=255)
    truck: str | None = Field(default=None, max_length=64)
    trailer: str | None = Field(default=None, max_length=64)
    place: str | None = Field(default=None, max_length=255)
    started_at: str | None = None
    intake: dict | None = None
    handover: dict | None = None
    refuels: list | None = None


class ShiftActionBody(BaseModel):
    force: bool = False


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
    kind = row.kind or ""
    phase = "end" if kind in LEGACY_END_KINDS else "start"
    return {
        "id": row.id,
        "kind": kind,
        "slot": row.slot or "",
        "content_type": row.content_type,
        "phase": phase,
    }


def _workflow(shift: DriverShift) -> str:
    raw = (getattr(shift, "workflow_status", None) or "").strip()
    if raw in {WORKFLOW_DRAFT, WORKFLOW_ACTIVE, WORKFLOW_CLOSING, WORKFLOW_CLOSED}:
        return raw
    return WORKFLOW_CLOSED if shift.ended_at else WORKFLOW_ACTIVE


def _shift_images(db: Session, shift_id: int) -> list[DriverShiftImage]:
    return list(
        db.scalars(
            select(DriverShiftImage)
            .where(DriverShiftImage.shift_id == shift_id)
            .order_by(DriverShiftImage.id.asc())
        ).all()
    )


def _shift_out(db: Session, shift: DriverShift, *, include_details: bool = False) -> dict:
    name = (getattr(shift, "driver_name", None) or "").strip() or _driver_name(db, shift.driver_user_id)
    workflow = _workflow(shift)
    payload = {
        "id": shift.id,
        "title": shift_title(name, shift.started_at, shift.ended_at),
        "driver_user_id": shift.driver_user_id,
        "driver_full_name": name,
        "started_at": shift.started_at.isoformat() if shift.started_at else None,
        "ended_at": shift.ended_at.isoformat() if shift.ended_at else None,
        "status": "ended" if workflow == WORKFLOW_CLOSED else "active",
        "workflow_status": workflow,
        "workflow_label": WORKFLOW_LABELS.get(workflow, workflow),
        "truck": (getattr(shift, "truck", None) or "").strip(),
        "trailer": (getattr(shift, "trailer", None) or "").strip(),
        "place": (getattr(shift, "place", None) or "").strip(),
    }
    if include_details:
        images = _shift_images(db, shift.id)
        payload["images"] = [_image_out(row) for row in images]
        payload["routes"] = _routes_during_shift(db, shift)
        payload["intake"] = as_dict(parse_json(getattr(shift, "intake_json", None), {})) or empty_phase()
        handover_raw = (getattr(shift, "handover_json", None) or "").strip()
        payload["handover"] = as_dict(parse_json(handover_raw, {})) if handover_raw else None
        payload["refuels"] = as_list(parse_json(getattr(shift, "refuels_json", None), []))
        payload["has_signature_start"] = "sign" in photo_slots(images, phase="start")
        payload["has_signature_end"] = "sign" in photo_slots(images, phase="end")
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
        .where(
            DriverShift.driver_user_id == driver_user_id,
            DriverShift.workflow_status != WORKFLOW_CLOSED,
            DriverShift.ended_at.is_(None),
        )
        .order_by(DriverShift.started_at.desc(), DriverShift.id.desc())
        .limit(1)
    ).first()


def _owned_open_shift(db: Session, shift_id: int, user: User) -> DriverShift:
    shift = db.get(DriverShift, shift_id)
    if shift is None or int(shift.driver_user_id) != int(user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return shift


def _parse_iso(raw: str | None) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=display_zone())
    return value.astimezone(timezone.utc)


def _inspection_view(shift: DriverShift) -> dict:
    return {
        "driver_name": (shift.driver_name or "").strip(),
        "truck": (shift.truck or "").strip(),
        "intake": as_dict(parse_json(shift.intake_json, {})) or empty_phase(),
        "handover": as_dict(parse_json(shift.handover_json, {})) if (shift.handover_json or "").strip() else None,
    }


def _require_editable(shift: DriverShift, phase: str) -> None:
    workflow = _workflow(shift)
    if phase == "start" and workflow != WORKFLOW_DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Приёмка уже завершена")
    if phase == "end" and workflow != WORKFLOW_CLOSING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сдача сейчас недоступна")


def _delete_image_files(row: DriverShiftImage) -> None:
    root = _upload_root()
    full_path = (root / row.storage_path).resolve()
    try:
        full_path.relative_to(root)
    except ValueError:
        return
    thumb = full_path.parent / _thumb_filename_for(full_path.name)
    for path in (full_path, thumb):
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            logger.warning("shift image delete failed: %s", path)


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
        stmt = stmt.where(
            or_(
                DriverShift.workflow_status.in_(OPEN_WORKFLOWS),
                DriverShift.ended_at.is_(None),
            )
        )
        stmt = stmt.where(DriverShift.workflow_status != WORKFLOW_CLOSED)
    elif kind in {"ended", "finished", "done"}:
        stmt = stmt.where(
            or_(DriverShift.workflow_status == WORKFLOW_CLOSED, DriverShift.ended_at.is_not(None))
        )
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


@router.post("/v1/shifts/draft")
def create_shift_draft(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    if _active_shift(db, current_user.id) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Вахта уже начата")
    name = (current_user.full_name or current_user.login or "").strip()
    shift = DriverShift(
        driver_user_id=current_user.id,
        started_at=datetime.now(timezone.utc),
        workflow_status=WORKFLOW_DRAFT,
        driver_name=name,
        intake_json=dump_json(empty_phase()),
        handover_json="",
        refuels_json="[]",
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return _shift_out(db, shift, include_details=True)


@router.patch("/v1/shifts/{shift_id}")
def patch_shift(
    shift_id: int,
    payload: ShiftPatchBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    shift = _owned_open_shift(db, shift_id, current_user)
    workflow = _workflow(shift)
    if workflow == WORKFLOW_CLOSED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Вахта уже завершена")
    if payload.driver_name is not None:
        shift.driver_name = payload.driver_name.strip()
    if payload.truck is not None:
        shift.truck = payload.truck.strip().upper()
    if payload.trailer is not None:
        shift.trailer = payload.trailer.strip().upper()
    if payload.place is not None:
        shift.place = payload.place.strip()
    started = _parse_iso(payload.started_at)
    if started is not None and workflow == WORKFLOW_DRAFT:
        shift.started_at = started
    if payload.intake is not None:
        if workflow != WORKFLOW_DRAFT:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Приёмка уже завершена")
        shift.intake_json = dump_json(payload.intake)
    if payload.handover is not None:
        if workflow != WORKFLOW_CLOSING:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сдача сейчас недоступна")
        shift.handover_json = dump_json(payload.handover)
    if payload.refuels is not None:
        if workflow not in {WORKFLOW_ACTIVE, WORKFLOW_CLOSING, WORKFLOW_DRAFT}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя менять заправки")
        shift.refuels_json = dump_json(payload.refuels)
    db.commit()
    db.refresh(shift)
    return _shift_out(db, shift, include_details=True)


@router.post("/v1/shifts/{shift_id}/photos")
async def upload_shift_photo(
    shift_id: int,
    slot: str = Form(...),
    phase: str = Form("start"),
    quality_json: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    shift = _owned_open_shift(db, shift_id, current_user)
    phase_key = "end" if (phase or "").strip().lower() == "end" else "start"
    _require_editable(shift, phase_key)
    slot_key = (slot or "").strip()[:64]
    if not slot_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не указан слот фото")
    body, ctype = await _read_image(file)
    kind = PHOTO_KIND_END if phase_key == "end" else PHOTO_KIND_START
    existing = db.scalars(
        select(DriverShiftImage).where(
            DriverShiftImage.shift_id == shift.id,
            DriverShiftImage.slot == slot_key,
            DriverShiftImage.kind.in_(LEGACY_END_KINDS if phase_key == "end" else LEGACY_START_KINDS),
        )
    ).all()
    for row in existing:
        _delete_image_files(row)
        db.delete(row)
    stored = _store_image(
        db,
        shift=shift,
        user_id=current_user.id,
        kind=kind,
        slot=slot_key,
        body=body,
        content_type=ctype,
    )
    meta = {}
    if quality_json.strip():
        try:
            parsed = json.loads(quality_json)
            if isinstance(parsed, list):
                meta = {"q": parsed}
        except (TypeError, ValueError):
            meta = {}
    if meta:
        field = "handover_json" if phase_key == "end" else "intake_json"
        payload = as_dict(parse_json(getattr(shift, field), {})) or empty_phase()
        photos_meta = as_dict(payload.get("photos_meta"))
        photos_meta[slot_key] = meta
        payload["photos_meta"] = photos_meta
        setattr(shift, field, dump_json(payload))
    db.commit()
    db.refresh(stored)
    db.refresh(shift)
    return {"image": _image_out(stored), "shift": _shift_out(db, shift, include_details=True)}


@router.delete("/v1/shifts/{shift_id}/photos/{image_id}")
def delete_shift_photo(
    shift_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    shift = _owned_open_shift(db, shift_id, current_user)
    row = db.get(DriverShiftImage, image_id)
    if row is None or int(row.shift_id) != int(shift.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    phase = "end" if row.kind in LEGACY_END_KINDS else "start"
    _require_editable(shift, phase)
    _delete_image_files(row)
    db.delete(row)
    db.commit()
    db.refresh(shift)
    return _shift_out(db, shift, include_details=True)


@router.post("/v1/shifts/{shift_id}/accept")
def accept_shift_vehicle(
    shift_id: int,
    payload: ShiftActionBody | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    shift = _owned_open_shift(db, shift_id, current_user)
    if _workflow(shift) != WORKFLOW_DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Приёмка уже завершена")
    images = _shift_images(db, shift.id)
    view = _inspection_view(shift)
    issues = blocking_issues(view, "start", photo_slots(images, phase="start"))
    force = bool(payload and payload.force)
    if issues and not force:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="; ".join(issues[:6]))
    if "sign" not in photo_slots(images, phase="start"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Поставьте подпись в конце итога")
    shift.workflow_status = WORKFLOW_ACTIVE
    _notify_shift(db, shift=shift, driver=current_user, started=True)
    db.commit()
    db.refresh(shift)
    return _shift_out(db, shift, include_details=True)


@router.post("/v1/shifts/{shift_id}/begin-end")
def begin_shift_handover(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    shift = _owned_open_shift(db, shift_id, current_user)
    if _workflow(shift) not in {WORKFLOW_ACTIVE, WORKFLOW_CLOSING}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сначала завершите приёмку ТС")
    if not (shift.handover_json or "").strip():
        intake = as_dict(parse_json(shift.intake_json, {}))
        shift.handover_json = dump_json(handover_from_intake(intake))
    shift.workflow_status = WORKFLOW_CLOSING
    db.commit()
    db.refresh(shift)
    return _shift_out(db, shift, include_details=True)


@router.post("/v1/shifts/{shift_id}/cancel-end")
def cancel_shift_handover(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    shift = _owned_open_shift(db, shift_id, current_user)
    if _workflow(shift) != WORKFLOW_CLOSING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сдача не начата")
    shift.workflow_status = WORKFLOW_ACTIVE
    db.commit()
    db.refresh(shift)
    return _shift_out(db, shift, include_details=True)


@router.post("/v1/shifts/{shift_id}/close")
def close_shift_vehicle(
    shift_id: int,
    payload: ShiftActionBody | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    shift = _owned_open_shift(db, shift_id, current_user)
    if _workflow(shift) != WORKFLOW_CLOSING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сначала начните сдачу ТС")
    images = _shift_images(db, shift.id)
    view = _inspection_view(shift)
    issues = blocking_issues(view, "end", photo_slots(images, phase="end"))
    force = bool(payload and payload.force)
    if issues and not force:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="; ".join(issues[:6]))
    if "sign" not in photo_slots(images, phase="end"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Поставьте подпись в конце итога")
    handover = as_dict(parse_json(shift.handover_json, {}))
    ended = _parse_iso(handover.get("time")) or datetime.now(timezone.utc)
    shift.ended_at = ended
    shift.workflow_status = WORKFLOW_CLOSED
    _notify_shift(db, shift=shift, driver=current_user, started=False)
    db.commit()
    db.refresh(shift)
    return _shift_out(db, shift, include_details=True)


@router.delete("/v1/shifts/{shift_id}")
def delete_shift_draft(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_driver),
) -> dict:
    shift = _owned_open_shift(db, shift_id, current_user)
    if _workflow(shift) != WORKFLOW_DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Удалить можно только черновик приёмки")
    images = _shift_images(db, shift.id)
    for row in images:
        _delete_image_files(row)
        db.delete(row)
    db.delete(shift)
    db.commit()
    return {"ok": True}


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
    shift = DriverShift(
        driver_user_id=current_user.id,
        started_at=datetime.now(timezone.utc),
        workflow_status=WORKFLOW_ACTIVE,
        driver_name=(current_user.full_name or current_user.login or "").strip(),
        intake_json=dump_json(empty_phase()),
    )
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
    shift.workflow_status = WORKFLOW_CLOSED
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
