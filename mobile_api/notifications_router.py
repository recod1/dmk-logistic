from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_user
from mobile_api.db import SessionLocal, get_db
from mobile_api.models import Notification, Point, Route, User, WebPushSubscription
from mobile_api.notifications_realtime import notifications_realtime_hub
from mobile_api.settings import mobile_settings


router = APIRouter(tags=["notifications"])


class PushSubscribePayload(BaseModel):
    endpoint: str = Field(min_length=8, max_length=4096)
    keys: dict[str, str]


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

    route_ids = sorted({str(item.route_id) for item in items if item.route_id})
    point_ids = sorted({int(item.point_id) for item in items if item.point_id is not None})

    routes_by_id: dict[str, Route] = {}
    if route_ids:
        routes = db.scalars(select(Route).where(Route.id.in_(route_ids))).all()
        routes_by_id = {str(r.id): r for r in routes}

    points_by_id: dict[int, Point] = {}
    if point_ids:
        points = db.scalars(select(Point).where(Point.id.in_(point_ids))).all()
        points_by_id = {int(p.id): p for p in points}

    driver_ids = sorted({int(r.assigned_user_id) for r in routes_by_id.values() if r and r.assigned_user_id})
    drivers_by_id: dict[int, User] = {}
    if driver_ids:
        drivers = db.scalars(select(User).where(User.id.in_(driver_ids))).all()
        drivers_by_id = {int(u.id): u for u in drivers}

    return {
        "items": [
            {
                "id": item.id,
                "event_type": item.event_type,
                "title": item.title,
                "message": item.message,
                "route_id": item.route_id,
                "point_id": item.point_id,
                "driver_full_name": (
                    (drivers_by_id.get(int(routes_by_id[str(item.route_id)].assigned_user_id)).full_name)  # type: ignore[arg-type]
                    if item.route_id
                    and str(item.route_id) in routes_by_id
                    and routes_by_id[str(item.route_id)].assigned_user_id
                    and int(routes_by_id[str(item.route_id)].assigned_user_id) in drivers_by_id
                    else None
                ),
                "number_auto": (
                    routes_by_id[str(item.route_id)].number_auto
                    if item.route_id and str(item.route_id) in routes_by_id
                    else None
                ),
                "trailer_number": (
                    routes_by_id[str(item.route_id)].trailer_number
                    if item.route_id and str(item.route_id) in routes_by_id
                    else None
                ),
                "point_place_point": (
                    points_by_id[int(item.point_id)].place_point
                    if item.point_id is not None and int(item.point_id) in points_by_id
                    else None
                ),
                "point_type_point": (
                    points_by_id[int(item.point_id)].type_point
                    if item.point_id is not None and int(item.point_id) in points_by_id
                    else None
                ),
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


@router.get("/v1/notifications/push/vapid-public-key")
def push_vapid_public_key(
    current_user: User = Depends(get_current_user),
) -> dict:
    _ = current_user
    key = mobile_settings.vapid_public_key or None
    return {"public_key": key}


@router.post("/v1/notifications/push/subscribe")
def push_subscribe(
    payload: PushSubscribePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    p256dh = payload.keys.get("p256dh")
    auth = payload.keys.get("auth")
    if not p256dh or not auth:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="keys must include p256dh and auth",
        )
    existing = db.scalar(
        select(WebPushSubscription).where(
            WebPushSubscription.user_id == current_user.id,
            WebPushSubscription.endpoint == payload.endpoint,
        )
    )
    if existing is not None:
        existing.p256dh = p256dh
        existing.auth = auth
        db.add(existing)
    else:
        db.add(
            WebPushSubscription(
                user_id=current_user.id,
                endpoint=payload.endpoint,
                p256dh=p256dh,
                auth=auth,
            )
        )
    db.commit()
    return {"ok": True}


@router.post("/v1/notifications/push/subscriptions:clear")
def push_clear_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Clears all push subscriptions for current user.
    Useful after VAPID key rotation (old subscriptions become invalid).
    """
    deleted = (
        db.query(WebPushSubscription)
        .filter(WebPushSubscription.user_id == current_user.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"ok": True, "deleted": int(deleted)}


@router.post("/v1/notifications/push/test")
def push_test(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Debug endpoint to verify that Web Push is configured and subscriptions are valid.
    Sends a push to the current user (to all their subscriptions).
    """
    if not mobile_settings.vapid_public_key or not mobile_settings.vapid_private_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="VAPID keys are not configured on server")

    from mobile_api.web_push_service import collect_subscriptions_for_users, send_web_push_to_users_sync

    rows = collect_subscriptions_for_users(db, [int(current_user.id)])
    subs = [(sub_id, endpoint, p256dh, auth) for sub_id, _user_id, endpoint, p256dh, auth in rows]
    if not subs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No push subscriptions for this user")

    results = send_web_push_to_users_sync(
        subscriptions=subs,
        title="ДМК (test)",
        body="Тестовое push-уведомление. Если вы это видите — Web Push работает.",
        notification_id=None,
    )
    ok_count = len([r for r in results if r.get("ok")])
    return {"ok": ok_count == len(subs), "subscriptions": len(subs), "ok_count": ok_count, "results": results}


@router.get("/v1/notifications/push/subscriptions")
def push_list_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Debug endpoint to see what push subscriptions are stored for the current user.
    Useful to confirm that iOS (web.push.apple.com) subscription is created.
    """
    rows = db.scalars(
        select(WebPushSubscription)
        .where(WebPushSubscription.user_id == current_user.id)
        .order_by(WebPushSubscription.created_at.desc(), WebPushSubscription.id.desc())
    ).all()

    items = []
    for row in rows:
        host = ""
        try:
            from urllib.parse import urlparse

            host = urlparse(row.endpoint).netloc
        except Exception:
            host = ""
        items.append(
            {
                "id": row.id,
                "endpoint_host": host,
                "endpoint_preview": (row.endpoint[:80] + "…") if len(row.endpoint) > 80 else row.endpoint,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return {"count": len(items), "items": items}


@router.get("/v1/notifications/push/debug-config")
def push_debug_config(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Returns diagnostic info about VAPID env values as seen by the running container.
    Does NOT return the full private key.
    """
    _ = current_user
    raw_priv = mobile_settings.vapid_private_key or ""
    raw_pub = mobile_settings.vapid_public_key or ""

    info: dict = {
        "vapid_public_key_set": bool(raw_pub.strip()),
        "vapid_public_key_len": len(raw_pub.strip()),
        "vapid_private_key_set": bool(raw_priv.strip()),
        "vapid_private_key_len": len(raw_priv),
        "vapid_private_key_has_begin": "BEGIN" in raw_priv,
        "vapid_private_key_has_end": "END" in raw_priv,
        "vapid_private_key_has_literal_backslash_n": "\\n" in raw_priv,
        "vapid_private_key_newline_count": raw_priv.count("\n"),
        "vapid_claim_email": mobile_settings.vapid_claim_email,
    }

    try:
        import base64
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        normalized = raw_priv.strip().strip('"').strip("'")
        if "\\n" in normalized or "\\r\\n" in normalized:
            normalized = normalized.replace("\\r\\n", "\n").replace("\\n", "\n")
        if "BEGIN PRIVATE KEY" in normalized and "END PRIVATE KEY" in normalized and "\n" not in normalized:
            normalized = normalized.replace("-----BEGIN PRIVATE KEY-----", "-----BEGIN PRIVATE KEY-----\n")
            normalized = normalized.replace("-----END PRIVATE KEY-----", "\n-----END PRIVATE KEY-----")

        key = None
        if "BEGIN" in normalized:
            key = serialization.load_pem_private_key(normalized.encode("utf-8"), password=None)
        else:
            # Try to parse base64/base64url value as DER (PKCS8) or raw 32-byte scalar.
            padding = "=" * ((4 - (len(normalized) % 4)) % 4)
            try:
                decoded = base64.urlsafe_b64decode((normalized + padding).encode("utf-8"))
            except Exception:
                decoded = base64.b64decode((normalized + padding).encode("utf-8"))
            if len(decoded) == 32:
                private_value = int.from_bytes(decoded, byteorder="big", signed=False)
                key = ec.derive_private_key(private_value, ec.SECP256R1())
            else:
                key = serialization.load_der_private_key(decoded, password=None)
        info["private_key_parsed_by_cryptography"] = True

        # Best-effort: verify that VAPID_PUBLIC_KEY matches the private key (common misconfig).
        try:
            if isinstance(key, ec.EllipticCurvePrivateKey):
                pub = key.public_key().public_bytes(
                    encoding=serialization.Encoding.X962,
                    format=serialization.PublicFormat.UncompressedPoint,
                )
                computed_pub = base64.urlsafe_b64encode(pub).decode("utf-8").rstrip("=")
                info["computed_public_key_len"] = len(computed_pub)
                info["public_key_matches_private"] = computed_pub.strip() == raw_pub.strip()
            else:
                info["public_key_matches_private"] = False
        except Exception as exc2:
            info["public_key_matches_private"] = False
            info["public_key_match_error"] = str(exc2)
    except Exception as exc:
        info["private_key_parsed_by_cryptography"] = False
        info["private_key_parse_error"] = str(exc)

    return info


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

