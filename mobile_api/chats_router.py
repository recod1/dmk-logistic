from __future__ import annotations

import asyncio
import mimetypes
import threading
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_user
from mobile_api.db import get_db
from mobile_api.models import (
    ChatAttachment,
    ChatMessage,
    ChatRead,
    ChatRoom,
    ChatRoomMember,
    ChatRoomRoleMember,
    User,
)
from mobile_api.notifications_service import create_notification_for_users
from mobile_api.roles import ADMIN_ACCESS_ROLES, RoleCode, normalize_role_code, role_label_ru
from mobile_api.chat_realtime import chat_realtime_hub
from mobile_api.point_documents_router import _upload_root as _mobile_upload_root


router = APIRouter(tags=["chats"])


def _is_driver_role(user: User) -> bool:
    try:
        return normalize_role_code(user.role_code) == RoleCode.DRIVER
    except ValueError:
        return False


def _is_logistic_role(user: User) -> bool:
    try:
        return normalize_role_code(user.role_code) == RoleCode.LOGISTIC
    except ValueError:
        return False


def _spawn_publish_chat_room(recipients: list[int], item: dict) -> None:
    def _run() -> None:
        try:
            asyncio.run(chat_realtime_hub.publish_to_users(recipients, {"type": "chat_room_message_created", "item": item}))
        except Exception:
            return

    try:
        threading.Thread(target=_run, daemon=True).start()
    except Exception:
        pass


def _room_recipient_user_ids(db: Session, room_id: int) -> list[int]:
    member_ids = db.scalars(select(ChatRoomMember.user_id).where(ChatRoomMember.room_id == room_id)).all()
    role_codes = list(db.scalars(select(ChatRoomRoleMember.role_code).where(ChatRoomRoleMember.room_id == room_id)).all())
    role_user_ids: list[int] = []
    if role_codes:
        role_user_ids = [
            int(x)
            for x in db.scalars(select(User.id).where(User.role_code.in_(role_codes), User.is_active == True)).all()  # noqa: E712
        ]
    return sorted(set(int(x) for x in member_ids) | set(role_user_ids))


def _notify_and_publish_room_message(db: Session, room: ChatRoom, msg: ChatMessage, current_user: User, item: dict) -> None:
    recipients = _room_recipient_user_ids(db, int(room.id))
    _spawn_publish_chat_room(recipients, item)
    author_name = (current_user.full_name or current_user.login or "").strip() or "Пользователь"
    snippet = (msg.text or "").strip()
    if len(snippet) > 120:
        snippet = snippet[:120] + "…"
    room_title = _room_out(db, room, current_user)["title"] or "Чат"
    create_notification_for_users(
        db,
        user_ids=recipients,
        event_type="chat_message",
        title=f"Чат: {room_title}",
        message=f"{author_name}: {snippet}",
        payload={"room_id": int(room.id), "chat_message_id": int(msg.id)},
        skip_user_ids=[current_user.id],
    )
    db.commit()


def ensure_driver_system_rooms(db: Session, driver: User) -> None:
    if not _is_driver_role(driver):
        return
    did = int(driver.id)
    pairs = [
        (f"sys:driver:{did}:logistics", "Логисты", RoleCode.LOGISTIC.value),
        (f"sys:driver:{did}:accounting", "Бухгалтерия", RoleCode.ACCOUNTANT.value),
    ]
    for key, title, role_code in pairs:
        existing = db.scalar(select(ChatRoom).where(ChatRoom.system_key == key))
        if existing is not None:
            continue
        room = ChatRoom(kind="group", title=title, system_key=key, created_by_user_id=None)
        db.add(room)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        db.add(ChatRoomMember(room_id=int(room.id), user_id=did))
        db.add(ChatRoomRoleMember(room_id=int(room.id), role_code=role_code))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()


def ensure_logistic_driver_room(db: Session, logistic: User, driver: User) -> ChatRoom:
    key = f"sys:logistic:{int(logistic.id)}:driver:{int(driver.id)}"
    existing = db.scalar(select(ChatRoom).where(ChatRoom.system_key == key))
    if existing is not None:
        return existing
    label = (driver.full_name or driver.login or "Водитель").strip()
    if len(label) > 90:
        label = label[:90] + "…"
    title = f"Чат Логисты — {label}"
    room = ChatRoom(kind="group", title=title, system_key=key, created_by_user_id=int(logistic.id))
    db.add(room)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        again = db.scalar(select(ChatRoom).where(ChatRoom.system_key == key))
        if again is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create chat room",
            ) from None
        return again
    db.add(ChatRoomMember(room_id=int(room.id), user_id=int(logistic.id)))
    db.add(ChatRoomMember(room_id=int(room.id), user_id=int(driver.id)))
    db.commit()
    db.refresh(room)
    return room


def _assert_room_access(db: Session, user: User, room: ChatRoom) -> None:
    # Admins can access everything
    try:
        role = normalize_role_code(user.role_code)
    except ValueError:
        role = None
    if role in ADMIN_ACCESS_ROLES:
        return

    is_member = db.scalar(
        select(func.count())
        .select_from(ChatRoomMember)
        .where(ChatRoomMember.room_id == room.id, ChatRoomMember.user_id == user.id)
    )
    if is_member and int(is_member) > 0:
        return
    role_member = db.scalar(
        select(func.count())
        .select_from(ChatRoomRoleMember)
        .where(ChatRoomRoleMember.room_id == room.id, ChatRoomRoleMember.role_code == user.role_code)
    )
    if role_member and int(role_member) > 0:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chat is not available")


def _room_title_for_direct(db: Session, room: ChatRoom, current_user: User) -> str:
    other_id = room.direct_user1_id if room.direct_user2_id == current_user.id else room.direct_user2_id
    other = db.get(User, int(other_id)) if other_id else None
    if other is None:
        return room.title or "Личный чат"
    return (other.full_name or other.login or "Пользователь").strip()


def _room_out(db: Session, room: ChatRoom, current_user: User, unread_by_room: dict[int, int] | None = None) -> dict:
    title = room.title
    if room.kind == "direct":
        title = _room_title_for_direct(db, room, current_user)
    return {
        "id": int(room.id),
        "kind": room.kind,
        "title": title or "",
        "system_key": room.system_key,
        "unread_count": int((unread_by_room or {}).get(int(room.id), 0)),
        "created_at": room.created_at.isoformat() if isinstance(room.created_at, datetime) else str(room.created_at),
    }


def _message_out(db: Session, msg: ChatMessage) -> dict:
    author = db.get(User, msg.user_id)
    author_name = (author.full_name or author.login) if author else f"user#{msg.user_id}"
    atts = db.scalars(
        select(ChatAttachment).where(ChatAttachment.message_id == msg.id).order_by(ChatAttachment.id.asc())
    ).all()
    return {
        "id": int(msg.id),
        "room_id": int(msg.room_id),
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


class UnreadRoomsIn(BaseModel):
    room_ids: list[int] = Field(default_factory=list, max_items=500)


@router.post("/v1/chats/unread-summary")
def unread_rooms_summary(
    payload: UnreadRoomsIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    room_ids = [int(x) for x in (payload.room_ids or []) if int(x) > 0]
    room_ids = list(dict.fromkeys(room_ids))[:500]
    if not room_ids:
        return {"items": []}

    reads = db.scalars(
        select(ChatRead).where(ChatRead.user_id == current_user.id, ChatRead.room_id.in_(room_ids))
    ).all()
    last_by_room = {int(r.room_id): int(r.last_read_message_id or 0) for r in reads}

    items: list[dict] = []
    for rid in room_ids:
        last_id = last_by_room.get(rid, 0)
        unread = db.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.room_id == rid, ChatMessage.id > last_id, ChatMessage.user_id != current_user.id)
        ) or 0
        items.append({"room_id": rid, "unread_count": int(unread)})
    return {"items": items}


@router.get("/v1/chats/users")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    rows = db.scalars(select(User).where(User.is_active == True).order_by(func.lower(User.full_name), func.lower(User.login))).all()  # noqa: E712
    return {
        "items": [
            {
                "id": u.id,
                "login": u.login,
                "full_name": u.full_name,
                "role_code": u.role_code,
                "role_label": role_label_ru(u.role_code),
            }
            for u in rows
        ]
    }


@router.post("/v1/chats/direct")
def open_direct_chat(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    other_id = int(payload.get("user_id") or 0)
    if other_id <= 0 or other_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user")
    other = db.get(User, other_id)
    if other is None or not other.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    u1, u2 = sorted([int(current_user.id), int(other_id)])
    existing = db.scalar(
        select(ChatRoom).where(ChatRoom.kind == "direct", ChatRoom.direct_user1_id == u1, ChatRoom.direct_user2_id == u2)
    )
    if existing is None:
        room = ChatRoom(kind="direct", title="", direct_user1_id=u1, direct_user2_id=u2, created_by_user_id=current_user.id)
        db.add(room)
        db.commit()
        db.refresh(room)
        # explicit members (helps access checks fast)
        db.add(ChatRoomMember(room_id=room.id, user_id=u1))
        db.add(ChatRoomMember(room_id=room.id, user_id=u2))
        db.commit()
        existing = room
    return {"room": _room_out(db, existing, current_user)}


@router.post("/v1/chats/bootstrap")
def chats_bootstrap(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if _is_driver_role(current_user):
        ensure_driver_system_rooms(db, current_user)
    return {"ok": True}


@router.get("/v1/chats/logistic/driver-rooms")
def list_logistic_driver_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if not _is_logistic_role(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only for logistic role")
    drivers = db.scalars(
        select(User)
        .where(User.is_active == True, User.role_code == RoleCode.DRIVER.value)  # noqa: E712
        .order_by(func.lower(User.full_name), func.lower(User.login))
    ).all()
    items: list[dict] = []
    for d in drivers:
        if int(d.id) == int(current_user.id):
            continue
        room = ensure_logistic_driver_room(db, current_user, d)
        items.append(
            {
                "driver": {"id": int(d.id), "full_name": d.full_name, "login": d.login},
                "room": _room_out(db, room, current_user),
            }
        )
    return {"items": items}


@router.get("/v1/chats/rooms")
def list_rooms(
    kind: str | None = Query(default=None, description="direct|group or empty for all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    q = select(ChatRoom).order_by(ChatRoom.created_at.desc())
    if kind:
        q = q.where(ChatRoom.kind == kind)

    # candidate rooms by membership or role-membership
    member_room_ids = db.scalars(
        select(ChatRoomMember.room_id).where(ChatRoomMember.user_id == current_user.id)
    ).all()
    role_room_ids = db.scalars(
        select(ChatRoomRoleMember.room_id).where(ChatRoomRoleMember.role_code == current_user.role_code)
    ).all()
    allowed = sorted(set(int(x) for x in member_room_ids) | set(int(x) for x in role_room_ids))

    try:
        role = normalize_role_code(current_user.role_code)
    except ValueError:
        role = None
    if role in ADMIN_ACCESS_ROLES:
        rooms = db.scalars(q).all()
    else:
        if not allowed:
            return {"items": []}
        rooms = db.scalars(q.where(ChatRoom.id.in_(allowed))).all()

    # unread counts
    reads = db.scalars(select(ChatRead).where(ChatRead.user_id == current_user.id, ChatRead.room_id.in_([r.id for r in rooms]))).all()
    last_by_room = {int(r.room_id): int(r.last_read_message_id or 0) for r in reads}
    unread_by_room: dict[int, int] = {}
    for room in rooms:
        last_id = last_by_room.get(int(room.id), 0)
        unread = db.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.room_id == room.id, ChatMessage.id > last_id, ChatMessage.user_id != current_user.id)
        ) or 0
        unread_by_room[int(room.id)] = int(unread)

    return {"items": [_room_out(db, r, current_user, unread_by_room) for r in rooms]}


@router.get("/v1/chats/rooms/{room_id}/messages")
def list_room_messages(
    room_id: int,
    limit: int = Query(default=200, ge=1, le=500),
    before_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    room = db.get(ChatRoom, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    _assert_room_access(db, current_user, room)

    q = select(ChatMessage).where(ChatMessage.room_id == room_id).order_by(ChatMessage.id.desc()).limit(limit)
    if before_id:
        q = q.where(ChatMessage.id < before_id)
    rows = list(reversed(db.scalars(q).all()))
    if rows:
        last_id = int(rows[-1].id)
        existing = db.scalar(select(ChatRead).where(ChatRead.user_id == current_user.id, ChatRead.room_id == room_id))
        if existing is None:
            db.add(ChatRead(user_id=current_user.id, room_id=room_id, last_read_message_id=last_id))
        else:
            existing.last_read_message_id = max(int(existing.last_read_message_id or 0), last_id)
            db.add(existing)
        db.commit()
    return {"items": [_message_out(db, r) for r in rows]}


class SendTextIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/v1/chats/rooms/{room_id}/messages", status_code=status.HTTP_201_CREATED)
def send_room_message(
    room_id: int,
    payload: SendTextIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    room = db.get(ChatRoom, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    _assert_room_access(db, current_user, room)
    msg = ChatMessage(room_id=room_id, user_id=current_user.id, text=payload.text.strip())
    db.add(msg)
    db.commit()
    db.refresh(msg)
    out = _message_out(db, msg)
    _notify_and_publish_room_message(db, room, msg, current_user, out)
    return out


MAX_CHAT_FILES = 10
MAX_CHAT_FILE_BYTES = 20 * 1024 * 1024


@router.post("/v1/chats/rooms/{room_id}/attachments", status_code=status.HTTP_201_CREATED)
async def send_room_attachments(
    room_id: int,
    text: str = "",
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    room = db.get(ChatRoom, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    _assert_room_access(db, current_user, room)
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files")
    if len(files) > MAX_CHAT_FILES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many files")

    msg_text = (text or "").strip() or "📎 Файлы"
    msg = ChatMessage(room_id=room_id, user_id=current_user.id, text=msg_text)
    db.add(msg)
    db.commit()
    db.refresh(msg)

    root = _mobile_upload_root()
    sub = root / "chats" / str(room_id) / str(msg.id)
    sub.mkdir(parents=True, exist_ok=True)

    for upload in files:
        body = await upload.read()
        if len(body) > MAX_CHAT_FILE_BYTES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large")
        ctype = (upload.content_type or "application/octet-stream").split(";")[0].strip().lower()
        safe_name = (upload.filename or "").strip()[:255] or "file"
        ext = mimetypes.guess_extension(ctype) or ""
        fname = f"{uuid.uuid4().hex}{ext}"
        full_path = sub / fname
        full_path.write_bytes(body)
        rel = f"chats/{room_id}/{msg.id}/{fname}"
        row = ChatAttachment(
            message_id=int(msg.id),
            room_id=int(room_id),
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
    out = _message_out(db, msg)
    _notify_and_publish_room_message(db, room, msg, current_user, out)
    return out


@router.get("/v1/chats/attachments/{attachment_id}/file")
def download_room_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    row = db.get(ChatAttachment, attachment_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    room = db.get(ChatRoom, int(row.room_id))
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    _assert_room_access(db, current_user, room)

    root = _mobile_upload_root()
    full_path = (root / row.storage_path).resolve()
    try:
        full_path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path") from exc
    if not full_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on server")
    headers = {"Cache-Control": "private, max-age=86400"}
    return FileResponse(
        path=str(full_path),
        media_type=row.content_type or "application/octet-stream",
        filename=row.original_name or full_path.name,
        headers=headers,
    )

