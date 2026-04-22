from __future__ import annotations

import asyncio
import threading
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_user
from mobile_api.chat_realtime import chat_realtime_hub
from mobile_api.db import SessionLocal, get_db
from mobile_api.models import Route, RouteChatMessage, RouteChatRead, User
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
    return {
        "id": int(msg.id),
        "route_id": str(msg.route_id),
        "user_id": int(msg.user_id),
        "author_name": author_name,
        "text": msg.text,
        "created_at": msg.created_at.isoformat() if isinstance(msg.created_at, datetime) else str(msg.created_at),
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

