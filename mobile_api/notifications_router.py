from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_user
from mobile_api.db import SessionLocal, get_db
from mobile_api.models import Notification, User
from mobile_api.notifications_realtime import notifications_realtime_hub
from mobile_api.settings import mobile_settings


router = APIRouter(tags=["notifications"])


def _list_notifications_impl(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    items = db.scalars(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": item.id,
                "event_type": item.event_type,
                "title": item.title,
                "message": item.message,
                "route_id": item.route_id,
                "point_id": item.point_id,
                "is_read": item.is_read,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ]
    }


def _decode_ws_user(token: str | None, db: Session) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token")
    try:
        payload = jwt.decode(
            token,
            mobile_settings.jwt_secret,
            algorithms=[mobile_settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token payload")
    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or not found")
    return user


@router.get("/v1/notifications")
def list_notifications_v1(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return _list_notifications_impl(limit=limit, db=db, current_user=current_user)


@router.get("/v1/mobile/notifications")
def list_notifications_mobile(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return _list_notifications_impl(limit=limit, db=db, current_user=current_user)


@router.get("/v1/notifications/unread-count")
def unread_notifications_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    unread = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
    ) or 0
    return {"unread_count": int(unread)}


@router.post("/v1/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    item = db.get(Notification, notification_id)
    if item is None or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if not item.is_read:
        item.is_read = True
        db.add(item)
        db.commit()
        db.refresh(item)
    return {
        "item": {
            "id": item.id,
            "event_type": item.event_type,
            "title": item.title,
            "message": item.message,
            "route_id": item.route_id,
            "point_id": item.point_id,
            "is_read": item.is_read,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
    }


@router.post("/v1/notifications/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    updated = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .update({Notification.is_read: True}, synchronize_session=False)
    )
    db.commit()
    return {"updated": int(updated)}


@router.websocket("/v1/notifications/ws")
async def notifications_ws(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    with SessionLocal() as db:
        try:
            user = _decode_ws_user(token, db)
        except HTTPException:
            await websocket.close(code=1008)
            return

    await notifications_realtime_hub.connect(user.id, websocket)
    try:
        await websocket.send_json({"type": "ready"})
        while True:
            # Keepalive + future extension: currently client can only ping.
            try:
                message = await websocket.receive_text()
                if message == "ping":
                    await websocket.send_text("pong")
            except RuntimeError:
                # Some clients can send ping frames without text payload;
                # keep socket open for server push.
                continue
    except WebSocketDisconnect:
        pass
    finally:
        await notifications_realtime_hub.disconnect(user.id, websocket)

