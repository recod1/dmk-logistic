from __future__ import annotations

import asyncio
import mimetypes
import threading
import uuid
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_user
from mobile_api.chat_realtime import chat_realtime_hub
from mobile_api.db import SessionLocal, get_db
from mobile_api.models import Route, RouteChatAttachment, RouteChatMessage, RouteChatRead, User
from mobile_api.point_documents_router import _upload_root as _mobile_upload_root
from mobile_api.notifications_service import create_notification_for_users
from mobile_api.roles import RoleCode, normalize_role_code
from mobile_api.settings import mobile_settings


router = APIRouter(tags=["chat"])


class ChatMessageOut(BaseModel):
    id: int
    route_id: str
    user_id: int
    author_name: str
    text: str
    created_at: str
    attachments: list[dict] = Field(default_factory=list)


class ChatSendPayload(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def _is_manager(user: User) -> bool:
    try:
        role = normalize_role_code(user.role_code)
    except ValueError:
        return False
    return role in {RoleCode.ADMIN, RoleCode.SUPERADMIN, RoleCode.LOGISTIC}


def _assert_can_access_route(db: Session, user: User, route_id: str) -> Route:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    if user.role_code == RoleCode.DRIVER.value:
        if route.assigned_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chat is not available for this route")
    else:
        if not _is_manager(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chat is not available for this role")
    return route


def _message_out(db: Session, msg: RouteChatMessage) -> dict:
    author = db.get(User, msg.user_id)
    author_name = (author.full_name or author.login) if author else f"user#{msg.user_id}"
    attachments = db.scalars(
        select(RouteChatAttachment)
        .where(RouteChatAttachment.message_id == msg.id)
        .order_by(RouteChatAttachment.id.asc())
    ).all()
    return {
        "id": int(msg.id),
        "route_id": str(msg.route_id),
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
            for a in attachments
        ],
    }


@router.get("/v1/chat/routes/{route_id}/messages")
def list_messages(
    route_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _assert_can_access_route(db, current_user, route_id)
    rows = db.scalars(
        select(RouteChatMessage)
        .where(RouteChatMessage.route_id == route_id)
        .order_by(RouteChatMessage.created_at.asc(), RouteChatMessage.id.asc())
        .limit(limit)
    ).all()
    if rows:
        last_id = int(rows[-1].id)
        existing = db.scalar(
            select(RouteChatRead).where(RouteChatRead.user_id == current_user.id, RouteChatRead.route_id == route_id)
        )
        if existing is None:
            db.add(RouteChatRead(user_id=current_user.id, route_id=route_id, last_read_message_id=last_id))
        else:
            existing.last_read_message_id = max(int(existing.last_read_message_id or 0), last_id)
            db.add(existing)
        db.commit()
    return {"items": [_message_out(db, row) for row in rows]}


class UnreadSummaryIn(BaseModel):
    route_ids: list[str] = Field(default_factory=list, max_items=300)


@router.post("/v1/chat/unread-summary")
def unread_summary(
    payload: UnreadSummaryIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    route_ids = [str(x).strip() for x in (payload.route_ids or []) if str(x).strip()]
    route_ids = list(dict.fromkeys(route_ids))[:300]
    if not route_ids:
        return {"items": []}

    # Filter allowed routes for current user.
    if current_user.role_code == RoleCode.DRIVER.value:
        allowed = db.scalars(
            select(Route.id).where(Route.id.in_(route_ids), Route.assigned_user_id == current_user.id)
        ).all()
        route_ids = [str(x) for x in allowed]
        if not route_ids:
            return {"items": []}
    else:
        if not _is_manager(current_user):
            return {"items": []}

    reads = db.scalars(
        select(RouteChatRead).where(RouteChatRead.user_id == current_user.id, RouteChatRead.route_id.in_(route_ids))
    ).all()
    last_by_route = {str(r.route_id): int(r.last_read_message_id or 0) for r in reads}

    # Count messages newer than last_read_message_id excluding own messages.
    items: list[dict] = []
    for rid in route_ids:
        last_id = last_by_route.get(str(rid), 0)
        unread = db.scalar(
            select(func.count())
            .select_from(RouteChatMessage)
            .where(RouteChatMessage.route_id == rid, RouteChatMessage.id > last_id, RouteChatMessage.user_id != current_user.id)
        ) or 0
        items.append({"route_id": rid, "unread_count": int(unread)})

    return {"items": items}


@router.post("/v1/chat/routes/{route_id}/messages", status_code=status.HTTP_201_CREATED)
def send_message(
    route_id: str,
    payload: ChatSendPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    route = _assert_can_access_route(db, current_user, route_id)
    msg = RouteChatMessage(route_id=route_id, user_id=current_user.id, text=payload.text.strip())
    db.add(msg)
    db.commit()
    db.refresh(msg)

    out = _message_out(db, msg)

    recipients: list[int] = []
    if route.assigned_user_id:
        recipients.append(int(route.assigned_user_id))
    if route.created_by_user_id:
        recipients.append(int(route.created_by_user_id))
    manager_ids = db.scalars(
        select(User.id).where(User.role_code.in_([RoleCode.ADMIN.value, RoleCode.SUPERADMIN.value, RoleCode.LOGISTIC.value]))
    ).all()
    recipients.extend(int(x) for x in manager_ids)
    recipients = sorted(set(recipients))

    # realtime chat push
    _publish_chat(recipients, {"type": "chat_message_created", "item": out})

    # notifications for others (so PWA shows + web push)
    author_name = (current_user.full_name or current_user.login or "").strip() or "Пользователь"
    snippet = payload.text.strip()
    if len(snippet) > 120:
        snippet = snippet[:120] + "…"
    create_notification_for_users(
        db,
        user_ids=recipients,
        event_type="chat_message",
        title=f"Чат рейса {route_id}",
        message=f"{author_name}: {snippet}",
        route_id=route_id,
        payload={"route_id": route_id, "chat_message_id": int(msg.id)},
        skip_user_ids=[current_user.id],
    )
    db.commit()

    return out


MAX_CHAT_FILES = 10
MAX_CHAT_FILE_BYTES = 20 * 1024 * 1024


@router.post("/v1/chat/routes/{route_id}/attachments", status_code=status.HTTP_201_CREATED)
async def send_message_with_attachments(
    route_id: str,
    text: str = "",
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    route = _assert_can_access_route(db, current_user, route_id)
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files")
    if len(files) > MAX_CHAT_FILES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many files")

    msg_text = (text or "").strip()
    if not msg_text:
        msg_text = "📎 Файлы"

    msg = RouteChatMessage(route_id=route_id, user_id=current_user.id, text=msg_text)
    db.add(msg)
    db.commit()
    db.refresh(msg)

    root = _mobile_upload_root()
    sub = root / "chat" / str(route_id) / str(msg.id)
    sub.mkdir(parents=True, exist_ok=True)

    created_ids: list[int] = []
    for upload in files:
        body = await upload.read()
        if len(body) > MAX_CHAT_FILE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large (max {MAX_CHAT_FILE_BYTES} bytes)",
            )
        ctype = (upload.content_type or "application/octet-stream").split(";")[0].strip().lower()
        safe_name = (upload.filename or "").strip()[:255] or "file"
        ext = mimetypes.guess_extension(ctype) or ""
        fname = f"{uuid.uuid4().hex}{ext}"
        full_path = sub / fname
        full_path.write_bytes(body)
        rel = f"chat/{route_id}/{msg.id}/{fname}"
        row = RouteChatAttachment(
            message_id=int(msg.id),
            route_id=str(route_id),
            uploaded_by_user_id=int(current_user.id),
            original_name=safe_name,
            storage_path=rel,
            content_type=ctype,
            file_size=len(body),
        )
        db.add(row)
        db.flush()
        created_ids.append(int(row.id))

    db.commit()
    out = _message_out(db, msg)

    recipients: list[int] = []
    if route.assigned_user_id:
        recipients.append(int(route.assigned_user_id))
    if route.created_by_user_id:
        recipients.append(int(route.created_by_user_id))
    manager_ids = db.scalars(
        select(User.id).where(User.role_code.in_([RoleCode.ADMIN.value, RoleCode.SUPERADMIN.value, RoleCode.LOGISTIC.value]))
    ).all()
    recipients.extend(int(x) for x in manager_ids)
    recipients = sorted(set(recipients))

    _publish_chat(recipients, {"type": "chat_message_created", "item": out})
    create_notification_for_users(
        db,
        user_ids=recipients,
        event_type="chat_message",
        title=f"Чат рейса {route_id}",
        message=f"{(current_user.full_name or current_user.login or 'Пользователь')}: {msg_text}",
        route_id=route_id,
        payload={"route_id": route_id, "chat_message_id": int(msg.id)},
        skip_user_ids=[current_user.id],
    )
    db.commit()

    return out


@router.get("/v1/chat/attachments/{attachment_id}/file")
def download_chat_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    row = db.get(RouteChatAttachment, attachment_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    _assert_can_access_route(db, current_user, str(row.route_id))

    root = _mobile_upload_root()
    full_path = (root / row.storage_path).resolve()
    try:
        full_path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path") from exc
    if not full_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on server")

    media_type = row.content_type or "application/octet-stream"
    headers = {"Cache-Control": "private, max-age=86400"}
    return FileResponse(
        path=str(full_path),
        media_type=media_type,
        filename=row.original_name or full_path.name,
        headers=headers,
    )


def _decode_ws_user(token: str | None, db: Session) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token")
    try:
        payload = jwt.decode(token, mobile_settings.jwt_secret, algorithms=[mobile_settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token payload")
    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or not found")
    return user


def _publish_chat(user_ids: list[int], payload: dict) -> None:
    def _run() -> None:
        try:
            asyncio.run(chat_realtime_hub.publish_to_users(user_ids, payload))
        except Exception:
            return

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


@router.websocket("/v1/chat/ws")
async def chat_ws(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    with SessionLocal() as db:
        try:
            user = _decode_ws_user(token, db)
        except HTTPException:
            await websocket.close(code=1008)
            return

    await chat_realtime_hub.connect(user.id, websocket)
    try:
        await websocket.send_json({"type": "ready"})
        while True:
            try:
                msg = await websocket.receive_text()
                if msg == "ping":
                    await websocket.send_text("pong")
            except RuntimeError:
                continue
    except WebSocketDisconnect:
        pass
    finally:
        await chat_realtime_hub.disconnect(user.id, websocket)

