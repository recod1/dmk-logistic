from __future__ import annotations

import asyncio
import mimetypes
import threading
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_user
from mobile_api.chat_realtime import chat_realtime_hub
from mobile_api.db import get_db
from mobile_api.models import Salary, SalaryChatAttachment, SalaryChatMessage, SalaryChatRead, User
from mobile_api.notifications_service import create_notification_for_users
from mobile_api.point_documents_router import _upload_root as _mobile_upload_root
from mobile_api.roles import RoleCode, normalize_role_code
from mobile_api.salary_logic import (
    build_salaries_csv_bytes,
    driver_identity_keys,
    driver_salary_key,
    parse_dd_mm_yyyy,
    parse_salary_line_37,
    resolve_user_for_salary_driver_id,
    salary_belongs_to_driver,
    salary_date_in_range,
)
from mobile_api.settings import mobile_settings

router = APIRouter(tags=["salary"])


def _is_accountant_admin(user: User) -> bool:
    try:
        r = normalize_role_code(user.role_code)
        return r in {RoleCode.ACCOUNTANT, RoleCode.ADMIN, RoleCode.SUPERADMIN}
    except ValueError:
        return False


def _accountant_admin_user_ids(db: Session) -> list[int]:
    return [
        int(x)
        for x in db.scalars(
            select(User.id).where(
                User.role_code.in_([RoleCode.ACCOUNTANT.value, RoleCode.ADMIN.value, RoleCode.SUPERADMIN.value]),
                User.is_active.is_(True),  # noqa: E712
            )
        ).all()
    ]


def _publish_salary_chat(user_ids: list[int], payload: dict) -> None:
    def _run() -> None:
        try:
            asyncio.run(chat_realtime_hub.publish_to_users(user_ids, payload))
        except Exception:
            return

    threading.Thread(target=_run, daemon=True).start()


def _fnum(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _salary_to_dict(s: Salary) -> dict[str, Any]:
    return {
        "id": int(s.id),
        "id_driver": s.id_driver,
        "date_salary": s.date_salary,
        "type_route": s.type_route,
        "sum_status": _fnum(s.sum_status),
        "sum_daily": _fnum(s.sum_daily),
        "load_2_trips": _fnum(s.load_2_trips),
        "calc_shuttle": _fnum(s.calc_shuttle),
        "sum_load_unload": _fnum(s.sum_load_unload),
        "sum_curtain": _fnum(s.sum_curtain),
        "sum_return": _fnum(s.sum_return),
        "sum_add_shuttle": _fnum(s.sum_add_shuttle),
        "sum_add_point": _fnum(s.sum_add_point),
        "sum_gas_station": _fnum(s.sum_gas_station),
        "pallets_hyper": int(s.pallets_hyper or 0),
        "pallets_metro": int(s.pallets_metro or 0),
        "pallets_ashan": int(s.pallets_ashan or 0),
        "rate_3km": _fnum(s.rate_3km),
        "rate_3_5km": _fnum(s.rate_3_5km),
        "rate_5km": _fnum(s.rate_5km),
        "rate_10km": _fnum(s.rate_10km),
        "rate_12km": _fnum(s.rate_12km),
        "rate_12_5km": _fnum(s.rate_12_5km),
        "mileage": _fnum(s.mileage),
        "sum_cell_compensation": _fnum(s.sum_cell_compensation),
        "experience": int(s.experience or 0),
        "percent_10": _fnum(s.percent_10),
        "sum_bonus": _fnum(s.sum_bonus),
        "withhold": _fnum(s.withhold),
        "compensation": _fnum(s.compensation),
        "dr": _fnum(s.dr),
        "sum_without_daily_dr_bonus_exp": _fnum(s.sum_without_daily_dr_bonus_exp),
        "sum_without_daily_dr_bonus": _fnum(s.sum_without_daily_dr_bonus),
        "total": _fnum(s.total),
        "load_address": s.load_address or "",
        "unload_address": s.unload_address or "",
        "transport": s.transport or "",
        "trailer_number": s.trailer_number or "",
        "route_number": s.route_number or "",
        "status_driver": (s.status_driver or "").strip(),
        "comment_driver": (s.comment_driver or "").strip(),
        "created_at": s.created_at.isoformat() if isinstance(s.created_at, datetime) else str(s.created_at),
    }


def _get_salary_or_404(db: Session, salary_id: int) -> Salary:
    row = db.get(Salary, salary_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary not found")
    return row


def _assert_can_view_salary(db: Session, user: User, salary: Salary) -> None:
    if salary_belongs_to_driver(salary, user):
        return
    if _is_accountant_admin(user):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Salary is not available")


def _assert_driver_salary(user: User, salary: Salary) -> None:
    if not salary_belongs_to_driver(salary, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your salary record")


def _salary_chat_recipient_ids(db: Session, salary: Salary) -> list[int]:
    ids: list[int] = []
    du = resolve_user_for_salary_driver_id(db, salary.id_driver)
    if du:
        ids.append(int(du.id))
    ids.extend(_accountant_admin_user_ids(db))
    return sorted(set(ids))


def _chat_message_out(db: Session, msg: SalaryChatMessage) -> dict[str, Any]:
    author = db.get(User, msg.user_id)
    author_name = (author.full_name or author.login) if author else f"user#{msg.user_id}"
    atts = db.scalars(
        select(SalaryChatAttachment)
        .where(SalaryChatAttachment.message_id == msg.id)
        .order_by(SalaryChatAttachment.id.asc())
    ).all()
    return {
        "id": int(msg.id),
        "salary_id": int(msg.salary_id),
        "user_id": int(msg.user_id),
        "author_name": author_name,
        "text": msg.text,
        "created_at": msg.created_at.isoformat() if isinstance(msg.created_at, datetime) else str(msg.created_at),
        "attachments": [
            {
                "id": int(a.id),
                "original_name": a.original_name,
                "content_type": a.content_type,
                "file_size": int(a.file_size),
            }
            for a in atts
        ],
    }


def _resolve_driver_for_create(db: Session, driver_user_id: int | None, driver_login: str | None) -> User:
    if driver_user_id and driver_user_id > 0:
        u = db.get(User, int(driver_user_id))
    elif driver_login and driver_login.strip():
        u = db.scalar(select(User).where(func.lower(User.login) == driver_login.strip().lower()))
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="driver_user_id or driver_login required")
    if u is None or not u.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
    try:
        if normalize_role_code(u.role_code) != RoleCode.DRIVER:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User must be a driver")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid driver role") from exc
    return u


def _verify_salary_integration_key(x_salary_api_key: str | None = Header(None, alias="X-Salary-Api-Key")) -> None:
    expected = (mobile_settings.salary_integration_api_key or "").strip()
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="SALARY_INTEGRATION_API_KEY is not configured")
    if (x_salary_api_key or "").strip() != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid X-Salary-Api-Key")


class SalaryCreateBody(BaseModel):
    driver_user_id: int = Field(ge=1)
    salary_line: str = Field(min_length=10, description="37 значений через пробел, как в боте")


class SalaryCommentBody(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class SalaryChatSendBody(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class SalaryIntegrationBody(BaseModel):
    driver_user_id: int | None = Field(default=None, ge=1)
    driver_login: str | None = None
    legacy_tg_id: str | None = None
    salary_line: str = Field(min_length=10)


@router.get("/v1/salary/lookup/drivers")
def lookup_drivers(
    q: str = Query(min_length=1, max_length=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if not _is_accountant_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    pattern = f"%{q.strip()}%"
    rows = db.scalars(
        select(User)
        .where(
            User.is_active.is_(True),  # noqa: E712
            User.role_code == RoleCode.DRIVER.value,
            or_(User.full_name.ilike(pattern), User.login.ilike(pattern)),  # type: ignore[attr-defined]
        )
        .order_by(func.lower(User.full_name), func.lower(User.login))
        .limit(30)
    ).all()
    return {
        "items": [
            {
                "id": int(u.id),
                "login": u.login,
                "full_name": u.full_name,
                "legacy_tg_id": u.legacy_tg_id,
            }
            for u in rows
        ]
    }


@router.post("/v1/salary", status_code=status.HTTP_201_CREATED)
def create_salary_manual(
    payload: SalaryCreateBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if not _is_accountant_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    driver = _resolve_driver_for_create(db, payload.driver_user_id, None)
    try:
        fields = parse_salary_line_37(payload.salary_line)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    row = Salary(id_driver=driver_salary_key(driver), status_driver=" ", comment_driver=" ", **fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    create_notification_for_users(
        db,
        user_ids=[int(driver.id)],
        event_type="salary_new",
        title="Новый расчёт зарплаты",
        message=f"Расчёт за {row.date_salary}, итого {_fnum(row.total):.2f} ₽",
        payload={"salary_id": int(row.id)},
        skip_user_ids=[],
    )
    db.commit()
    return _salary_to_dict(row)


@router.post("/v1/salary/integration", status_code=status.HTTP_201_CREATED)
def create_salary_integration(
    payload: SalaryIntegrationBody,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_salary_integration_key),
) -> dict:
    driver: User | None = None
    if payload.driver_user_id:
        driver = db.get(User, int(payload.driver_user_id))
    elif payload.driver_login and payload.driver_login.strip():
        driver = db.scalar(select(User).where(func.lower(User.login) == payload.driver_login.strip().lower()))
    elif payload.legacy_tg_id and str(payload.legacy_tg_id).strip():
        driver = db.scalar(
            select(User).where(User.legacy_tg_id == str(payload.legacy_tg_id).strip(), User.is_active.is_(True))  # noqa: E712
        )
    if driver is None or not driver.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
    try:
        if normalize_role_code(driver.role_code) != RoleCode.DRIVER:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User must be a driver")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid driver role") from exc
    try:
        fields = parse_salary_line_37(payload.salary_line)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    row = Salary(id_driver=driver_salary_key(driver), status_driver=" ", comment_driver=" ", **fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    create_notification_for_users(
        db,
        user_ids=[int(driver.id)],
        event_type="salary_new",
        title="Новый расчёт зарплаты",
        message=f"Расчёт за {row.date_salary}, итого {_fnum(row.total):.2f} ₽",
        payload={"salary_id": int(row.id)},
        skip_user_ids=[],
    )
    db.commit()
    return _salary_to_dict(row)


@router.get("/v1/salary/mine")
def list_my_salaries(
    date_from: str | None = Query(default=None, description="дд.мм.гггг"),
    date_to: str | None = Query(default=None, description="дд.мм.гггг"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        if normalize_role_code(current_user.role_code) != RoleCode.DRIVER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only for drivers")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only for drivers") from exc
    keys = driver_identity_keys(current_user)
    rows = db.scalars(select(Salary).where(Salary.id_driver.in_(keys)).order_by(Salary.id.desc())).all()
    if date_from and date_to:
        try:
            s_dt = parse_dd_mm_yyyy(date_from)
            e_dt = parse_dd_mm_yyyy(date_to)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date_from/date_to") from exc
        rows = [s for s in rows if salary_date_in_range(s, s_dt, e_dt)]
    return {"items": [_salary_to_dict(s) for s in rows]}


@router.get("/v1/salary/mine/export.csv")
def export_my_salaries_csv(
    date_from: str = Query(min_length=8, max_length=10),
    date_to: str = Query(min_length=8, max_length=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    try:
        if normalize_role_code(current_user.role_code) != RoleCode.DRIVER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only for drivers")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only for drivers") from exc
    try:
        s_dt = parse_dd_mm_yyyy(date_from)
        e_dt = parse_dd_mm_yyyy(date_to)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format") from exc
    keys = driver_identity_keys(current_user)
    rows = list(db.scalars(select(Salary).where(Salary.id_driver.in_(keys)).order_by(Salary.id.desc())).all())
    rows = [s for s in rows if salary_date_in_range(s, s_dt, e_dt)]
    name = (current_user.full_name or current_user.login or str(current_user.id)).strip()
    period_info = f"с {date_from} по {date_to}"
    body = build_salaries_csv_bytes(rows, name, period_info)
    fn = f"расчеты_{name}_{date_from}_{date_to}.csv".replace(" ", "_")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fn}"'},
    )


@router.get("/v1/salary/for-driver/{driver_user_id}")
def list_salaries_for_driver(
    driver_user_id: int,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if not _is_accountant_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    driver = db.get(User, driver_user_id)
    if driver is None or not driver.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
    key = driver_salary_key(driver)
    rows = db.scalars(select(Salary).where(Salary.id_driver == key).order_by(Salary.id.desc())).all()
    if date_from and date_to:
        try:
            s_dt = parse_dd_mm_yyyy(date_from)
            e_dt = parse_dd_mm_yyyy(date_to)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid dates") from exc
        rows = [s for s in rows if salary_date_in_range(s, s_dt, e_dt)]
    return {"items": [_salary_to_dict(s) for s in rows], "driver": {"id": int(driver.id), "full_name": driver.full_name, "login": driver.login}}


@router.get("/v1/salary/{salary_id}")
def get_salary(
    salary_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    s = _get_salary_or_404(db, salary_id)
    _assert_can_view_salary(db, current_user, s)
    return _salary_to_dict(s)


@router.post("/v1/salary/{salary_id}/confirm")
def confirm_salary(
    salary_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        if normalize_role_code(current_user.role_code) != RoleCode.DRIVER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only driver can confirm")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only driver can confirm") from exc
    s = _get_salary_or_404(db, salary_id)
    _assert_driver_salary(current_user, s)
    s.status_driver = "confirmed"
    db.add(s)
    db.commit()
    db.refresh(s)
    notify_ids = _accountant_admin_user_ids(db)
    create_notification_for_users(
        db,
        user_ids=notify_ids,
        event_type="salary_confirmed",
        title="Расчёт подтверждён водителем",
        message=f"{current_user.full_name or current_user.login}: расчёт #{salary_id} за {s.date_salary}, ЗП {_fnum(s.total):.2f}",
        payload={"salary_id": int(salary_id)},
        skip_user_ids=[current_user.id],
    )
    db.commit()
    return _salary_to_dict(s)


@router.post("/v1/salary/{salary_id}/comment")
def comment_salary(
    salary_id: int,
    payload: SalaryCommentBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        if normalize_role_code(current_user.role_code) != RoleCode.DRIVER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only driver can comment")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only driver can comment") from exc
    s = _get_salary_or_404(db, salary_id)
    _assert_driver_salary(current_user, s)
    s.comment_driver = payload.text.strip()
    s.status_driver = "commented"
    db.add(s)
    db.commit()
    db.refresh(s)
    notify_ids = _accountant_admin_user_ids(db)
    create_notification_for_users(
        db,
        user_ids=notify_ids,
        event_type="salary_commented",
        title="Комментарий к расчёту",
        message=f"{current_user.full_name or current_user.login}: расчёт #{salary_id} за {s.date_salary}",
        payload={"salary_id": int(salary_id)},
        skip_user_ids=[current_user.id],
    )
    db.commit()
    return _salary_to_dict(s)


@router.get("/v1/salary/{salary_id}/chat/messages")
def list_salary_chat_messages(
    salary_id: int,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    s = _get_salary_or_404(db, salary_id)
    _assert_can_view_salary(db, current_user, s)
    rows = db.scalars(
        select(SalaryChatMessage)
        .where(SalaryChatMessage.salary_id == salary_id)
        .order_by(SalaryChatMessage.id.asc())
        .limit(limit)
    ).all()
    if rows:
        last_id = int(rows[-1].id)
        existing = db.scalar(
            select(SalaryChatRead).where(SalaryChatRead.user_id == current_user.id, SalaryChatRead.salary_id == salary_id)
        )
        if existing is None:
            db.add(SalaryChatRead(user_id=current_user.id, salary_id=salary_id, last_read_message_id=last_id))
        else:
            existing.last_read_message_id = max(int(existing.last_read_message_id or 0), last_id)
            db.add(existing)
        db.commit()
    return {"items": [_chat_message_out(db, r) for r in rows]}


@router.post("/v1/salary/{salary_id}/chat/messages", status_code=status.HTTP_201_CREATED)
def send_salary_chat_message(
    salary_id: int,
    payload: SalaryChatSendBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    s = _get_salary_or_404(db, salary_id)
    _assert_can_view_salary(db, current_user, s)
    msg = SalaryChatMessage(salary_id=salary_id, user_id=current_user.id, text=payload.text.strip())
    db.add(msg)
    db.commit()
    db.refresh(msg)
    out = _chat_message_out(db, msg)
    recipients = _salary_chat_recipient_ids(db, s)
    _publish_salary_chat(recipients, {"type": "salary_chat_message_created", "item": out})
    author_name = (current_user.full_name or current_user.login or "").strip() or "Пользователь"
    snippet = payload.text.strip()
    if len(snippet) > 120:
        snippet = snippet[:120] + "…"
    create_notification_for_users(
        db,
        user_ids=recipients,
        event_type="chat_message",
        title=f"Чат расчёта #{salary_id}",
        message=f"{author_name}: {snippet}",
        payload={"salary_id": int(salary_id), "salary_chat_message_id": int(msg.id)},
        skip_user_ids=[current_user.id],
    )
    db.commit()
    return out


MAX_SALARY_CHAT_FILES = 10
MAX_SALARY_CHAT_FILE_BYTES = 20 * 1024 * 1024


@router.post("/v1/salary/{salary_id}/chat/attachments", status_code=status.HTTP_201_CREATED)
async def send_salary_chat_attachments(
    salary_id: int,
    text: str = "",
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    s = _get_salary_or_404(db, salary_id)
    _assert_can_view_salary(db, current_user, s)
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files")
    if len(files) > MAX_SALARY_CHAT_FILES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many files")
    msg_text = (text or "").strip() or "📎 Файлы"
    msg = SalaryChatMessage(salary_id=salary_id, user_id=current_user.id, text=msg_text)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    root = _mobile_upload_root()
    sub = root / "salary_chat" / str(salary_id) / str(msg.id)
    sub.mkdir(parents=True, exist_ok=True)
    for upload in files:
        body = await upload.read()
        if len(body) > MAX_SALARY_CHAT_FILE_BYTES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large")
        ctype = (upload.content_type or "application/octet-stream").split(";")[0].strip().lower()
        safe_name = (upload.filename or "").strip()[:255] or "file"
        ext = mimetypes.guess_extension(ctype) or ""
        fname = f"{uuid.uuid4().hex}{ext}"
        full_path = sub / fname
        full_path.write_bytes(body)
        rel = f"salary_chat/{salary_id}/{msg.id}/{fname}"
        row = SalaryChatAttachment(
            message_id=int(msg.id),
            salary_id=int(salary_id),
            uploaded_by_user_id=int(current_user.id),
            original_name=safe_name,
            storage_path=rel,
            content_type=ctype,
            file_size=len(body),
        )
        db.add(row)
        db.flush()
    db.commit()
    db.refresh(msg)
    out = _chat_message_out(db, msg)
    recipients = _salary_chat_recipient_ids(db, s)
    _publish_salary_chat(recipients, {"type": "salary_chat_message_created", "item": out})
    create_notification_for_users(
        db,
        user_ids=recipients,
        event_type="chat_message",
        title=f"Чат расчёта #{salary_id}",
        message=f"{(current_user.full_name or current_user.login or 'Пользователь')}: {msg_text}",
        payload={"salary_id": int(salary_id), "salary_chat_message_id": int(msg.id)},
        skip_user_ids=[current_user.id],
    )
    db.commit()
    return out


@router.get("/v1/salary/chat/attachments/{attachment_id}/file")
def download_salary_chat_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    row = db.get(SalaryChatAttachment, attachment_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    s = _get_salary_or_404(db, int(row.salary_id))
    _assert_can_view_salary(db, current_user, s)
    root = _mobile_upload_root()
    full_path = (root / row.storage_path).resolve()
    try:
        full_path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path") from exc
    if not full_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on server")
    return FileResponse(
        path=str(full_path),
        media_type=row.content_type or "application/octet-stream",
        filename=row.original_name or full_path.name,
        headers={"Cache-Control": "private, max-age=86400"},
    )
