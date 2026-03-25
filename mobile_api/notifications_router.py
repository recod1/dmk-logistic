from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_user
from mobile_api.db import get_db
from mobile_api.models import Notification, User


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

