from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_admin
from mobile_api.db import get_db
from mobile_api.models import ChatRoom, ChatRoomMember, ChatRoomRoleMember, User
from mobile_api.notifications_service import create_notification_for_users
from mobile_api.roles import normalize_role_code

router = APIRouter(prefix="/v1/admin/chats", tags=["admin-chats"])


def _room_admin_out(db: Session, room: ChatRoom) -> dict:
    member_ids = [int(x) for x in db.scalars(select(ChatRoomMember.user_id).where(ChatRoomMember.room_id == room.id)).all()]
    role_rows = db.scalars(select(ChatRoomRoleMember).where(ChatRoomRoleMember.room_id == room.id)).all()
    return {
        "id": int(room.id),
        "kind": room.kind,
        "title": room.title or "",
        "system_key": room.system_key,
        "member_user_ids": member_ids,
        "role_codes": [r.role_code for r in role_rows],
        "created_at": room.created_at.isoformat() if room.created_at else "",
    }


class CreateRoomIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    system_key: str | None = Field(default=None, max_length=128)
    member_user_ids: list[int] = Field(default_factory=list)
    role_codes: list[str] = Field(default_factory=list)


class PatchRoomIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class MemberIn(BaseModel):
    user_id: int = Field(ge=1)


class RoleIn(BaseModel):
    role_code: str = Field(min_length=2, max_length=32)


class BroadcastIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)
    role_codes: list[str] = Field(min_length=1, max_length=10)
    skip_self: bool = True


@router.get("/rooms")
def admin_list_rooms(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> dict:
    rooms = db.scalars(select(ChatRoom).order_by(ChatRoom.id.desc())).all()
    return {"items": [_room_admin_out(db, r) for r in rooms]}


@router.post("/rooms", status_code=status.HTTP_201_CREATED)
def admin_create_room(
    payload: CreateRoomIn,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> dict:
    if payload.system_key:
        clash = db.scalar(select(ChatRoom).where(ChatRoom.system_key == payload.system_key.strip()))
        if clash is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="system_key already exists")
    room = ChatRoom(
        kind="group",
        title=payload.title.strip(),
        system_key=(payload.system_key.strip() if payload.system_key else None),
        created_by_user_id=int(admin.id),
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    for uid in {int(x) for x in payload.member_user_ids if int(x) > 0}:
        u = db.get(User, uid)
        if u is None or not u.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid member user_id={uid}")
        db.add(ChatRoomMember(room_id=int(room.id), user_id=uid))
    for rc in payload.role_codes:
        try:
            norm = normalize_role_code(rc).value
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        db.add(ChatRoomRoleMember(room_id=int(room.id), role_code=norm))
    db.commit()
    return _room_admin_out(db, room)


@router.patch("/rooms/{room_id}")
def admin_patch_room(
    room_id: int,
    payload: PatchRoomIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> dict:
    room = db.get(ChatRoom, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    room.title = payload.title.strip()
    db.add(room)
    db.commit()
    db.refresh(room)
    return _room_admin_out(db, room)


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> None:
    room = db.get(ChatRoom, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    db.delete(room)
    db.commit()


@router.post("/rooms/{room_id}/members", status_code=status.HTTP_201_CREATED)
def admin_add_member(
    room_id: int,
    payload: MemberIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> dict:
    room = db.get(ChatRoom, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    u = db.get(User, int(payload.user_id))
    if u is None or not u.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")
    exists = db.scalar(
        select(ChatRoomMember).where(ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == int(payload.user_id))
    )
    if exists is None:
        db.add(ChatRoomMember(room_id=room_id, user_id=int(payload.user_id)))
        db.commit()
    return _room_admin_out(db, room)


@router.delete("/rooms/{room_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_remove_member(
    room_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> None:
    row = db.scalar(select(ChatRoomMember).where(ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == user_id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    db.delete(row)
    db.commit()


@router.post("/rooms/{room_id}/roles", status_code=status.HTTP_201_CREATED)
def admin_add_role(
    room_id: int,
    payload: RoleIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> dict:
    room = db.get(ChatRoom, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        norm = normalize_role_code(payload.role_code).value
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    exists = db.scalar(select(ChatRoomRoleMember).where(ChatRoomRoleMember.room_id == room_id, ChatRoomRoleMember.role_code == norm))
    if exists is None:
        db.add(ChatRoomRoleMember(room_id=room_id, role_code=norm))
        db.commit()
    return _room_admin_out(db, room)


@router.delete("/rooms/{room_id}/roles/{role_code}", status_code=status.HTTP_204_NO_CONTENT)
def admin_remove_role(
    room_id: int,
    role_code: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> None:
    try:
        norm = normalize_role_code(role_code).value
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    row = db.scalar(select(ChatRoomRoleMember).where(ChatRoomRoleMember.room_id == room_id, ChatRoomRoleMember.role_code == norm))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    db.delete(row)
    db.commit()


@router.post("/broadcast")
def admin_broadcast(
    payload: BroadcastIn,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> dict:
    codes: list[str] = []
    for raw in payload.role_codes:
        try:
            codes.append(normalize_role_code(raw).value)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    codes = list(dict.fromkeys(codes))
    user_ids = [int(x) for x in db.scalars(select(User.id).where(User.role_code.in_(codes), User.is_active == True)).all()]  # noqa: E712
    skip = [int(admin.id)] if payload.skip_self else []
    skip_set = set(skip)
    recipient_count = len([uid for uid in user_ids if uid not in skip_set])
    create_notification_for_users(
        db,
        user_ids=user_ids,
        event_type="admin_broadcast",
        title=payload.title.strip(),
        message=payload.message.strip(),
        payload={"role_codes": codes},
        skip_user_ids=skip,
    )
    db.commit()
    return {"recipient_count": recipient_count}
