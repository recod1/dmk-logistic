from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_admin, get_current_user
from mobile_api.db import get_db
from mobile_api.models import LogisticsContact, User

router = APIRouter(tags=["logistics-contacts"])

MAX_LOGISTICS_CONTACTS = 30


class LogisticsContactItem(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    phone: str = Field(min_length=1, max_length=64)


class LogisticsContactsReplaceBody(BaseModel):
    items: list[LogisticsContactItem] = Field(default_factory=list, max_length=MAX_LOGISTICS_CONTACTS)


def _list_contacts(db: Session) -> list[LogisticsContact]:
    return list(db.scalars(select(LogisticsContact).order_by(LogisticsContact.sort_order.asc(), LogisticsContact.id.asc())).all())


def _contact_out(row: LogisticsContact) -> dict:
    return {
        "id": int(row.id),
        "name": row.name,
        "phone": row.phone,
        "sort_order": int(row.sort_order),
        "updated_at": row.updated_at.isoformat() if isinstance(row.updated_at, datetime) else str(row.updated_at),
    }


def logistics_contacts_payload(db: Session) -> list[dict]:
    return [_contact_out(row) for row in _list_contacts(db)]


@router.get("/v1/logistics-contacts")
def list_logistics_contacts(
    response: Response,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return {"items": [_contact_out(row) for row in _list_contacts(db)]}


@router.put("/v1/admin/logistics-contacts")
def replace_logistics_contacts(
    payload: LogisticsContactsReplaceBody,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> dict:
    cleaned: list[tuple[str, str]] = []
    seen_phones: set[str] = set()
    for item in payload.items:
        name = item.name.strip()
        phone = item.phone.strip()
        if not name or not phone:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Имя и телефон обязательны")
        phone_key = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
        if len(phone_key) < 5:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Некорректный телефон: {phone}")
        if phone_key in seen_phones:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Дублирующийся телефон: {phone}")
        seen_phones.add(phone_key)
        cleaned.append((name, phone))

    db.execute(delete(LogisticsContact))
    db.flush()
    for idx, (name, phone) in enumerate(cleaned):
        db.add(LogisticsContact(name=name, phone=phone, sort_order=idx))
    db.commit()
    return {"items": [_contact_out(row) for row in _list_contacts(db)]}
