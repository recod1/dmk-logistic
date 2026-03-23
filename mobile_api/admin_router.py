from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_admin, hash_password
from mobile_api.db import get_db
from mobile_api.models import User


router = APIRouter(prefix="/v1/admin/users", tags=["admin-users"])


class UserCreatePayload(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    role: str = Field(min_length=1, max_length=32)


class UserUpdatePayload(BaseModel):
    login: str | None = Field(default=None, min_length=1, max_length=64)
    password: str | None = Field(default=None, min_length=1, max_length=256)
    role: str | None = Field(default=None, min_length=1, max_length=32)
    is_active: bool | None = None


def _clean_required(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} is required")
    return cleaned


def _user_out(user: User) -> dict:
    return {
        "id": user.id,
        "login": user.login,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if isinstance(user.created_at, datetime) else None,
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
    exists = db.scalar(select(User).where(User.login == payload.login))
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Login already exists")

    login = _clean_required(payload.login, "login")
    role = _clean_required(payload.role, "role")

    user = User(
        login=login,
        password_hash=hash_password(payload.password),
        role=role,
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

    if payload.role is not None:
        user.role = _clean_required(payload.role, "role")

    if payload.is_active is not None:
        # Protect from accidental self-lockout by API call.
        if current_admin.id == user.id and payload.is_active is False:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin cannot deactivate self")
        user.is_active = payload.is_active

    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user)

