from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_admin, hash_password
from mobile_api.db import get_db
from mobile_api.models import User
from mobile_api.roles import ROLE_LABELS_RU, RoleCode, normalize_role_code, role_label_ru


router = APIRouter(prefix="/v1/admin/users", tags=["admin-users"])


class UserCreatePayload(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    role_code: str = Field(min_length=1, max_length=32)
    full_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)


class UserUpdatePayload(BaseModel):
    login: str | None = Field(default=None, min_length=1, max_length=64)
    password: str | None = Field(default=None, min_length=1, max_length=256)
    role_code: str | None = Field(default=None, min_length=1, max_length=32)
    full_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None


def _clean_required(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} is required")
    return cleaned


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _user_out(user: User) -> dict:
    return {
        "id": user.id,
        "login": user.login,
        "role": user.role_code,
        "role_code": user.role_code,
        "role_label": role_label_ru(user.role_code),
        "full_name": user.full_name,
        "phone": user.phone,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if isinstance(user.created_at, datetime) else None,
    }


@router.get("/roles")
def list_roles(_: User = Depends(get_current_admin)) -> dict:
    return {
        "items": [
            {"role_code": role.value, "role_label": ROLE_LABELS_RU[role]}
            for role in [RoleCode.LOGISTIC, RoleCode.ACCOUNTANT, RoleCode.DRIVER, RoleCode.ADMIN, RoleCode.SUPERADMIN]
        ]
    }


@router.get("")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> dict:
    users = db.scalars(select(User).order_by(User.id.asc())).all()
    return {"items": [_user_out(user) for user in users]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreatePayload,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> dict:
    login = _clean_required(payload.login, "login")
    exists = db.scalar(select(User).where(User.login == login))
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Login already exists")
    try:
        role_code = normalize_role_code(payload.role_code).value
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    user = User(
        login=login,
        password_hash=hash_password(payload.password),
        role_code=role_code,
        full_name=_clean_optional(payload.full_name),
        phone=_clean_optional(payload.phone),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.patch("/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdatePayload,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.login is not None:
        login = _clean_required(payload.login, "login")
        if login != user.login:
            exists = db.scalar(select(User).where(User.login == login))
            if exists is not None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Login already exists")
            user.login = login

    if payload.password is not None:
        user.password_hash = hash_password(payload.password)

    if payload.role_code is not None:
        try:
            user.role_code = normalize_role_code(payload.role_code).value
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    if payload.full_name is not None:
        user.full_name = _clean_optional(payload.full_name)

    if payload.phone is not None:
        user.phone = _clean_optional(payload.phone)

    if payload.is_active is not None:
        # Protect from accidental self-lockout by API call.
        if current_admin.id == user.id and payload.is_active is False:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin cannot deactivate self")
        user.is_active = payload.is_active

    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if current_admin.id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin cannot delete self")
    db.delete(user)
    db.commit()

