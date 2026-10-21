from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.auth import get_current_user
from mobile_api.chat_router import _assert_can_access_route, post_route_chat_and_notify
from mobile_api.db import get_db
from mobile_api.models import Point, Route, RouteIncident, User
from mobile_api.notifications_service import create_notification_for_users
from mobile_api.roles import RoleCode
from mobile_api.route_incidents import (
    FOLLOW_UP,
    INCIDENT_KINDS,
    KIND_LABELS,
    NEEDS_REASON,
    PHOTO_STAGES,
    RETURN_STAGES,
    RETURN_STAGE_LABELS,
    RETURN_WARNING,
    dump_return_stages,
    format_incident_chat,
    next_return_stage,
    parse_return_stages,
    return_stages_out,
)
from mobile_api.time_formatting import format_dt_for_app


router = APIRouter(tags=["route-incidents"])


class IncidentCreateIn(BaseModel):
    kind: str = Field(min_length=1, max_length=32)
    comment: str = Field(default="", max_length=2000)
    cargo_name: str = Field(default="", max_length=255)
    quantity: str = Field(default="", max_length=64)
    point_id: int | None = None


class IncidentFollowUpIn(BaseModel):
    note: str = Field(default="", max_length=2000)


class ReturnStageIn(BaseModel):
    authorized_by: str = Field(default="", max_length=255)
    comment: str = Field(default="", max_length=2000)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    odometer: str = Field(default="", max_length=64)
    odometer_source: str = Field(default="", max_length=16)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _assert_driver_assigned(user: User, route: Route) -> None:
    if user.role_code != RoleCode.DRIVER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only driver can report a problem")
    if route.assigned_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your route")


def _incident_out(row: RouteIncident) -> dict:
    follow = FOLLOW_UP.get(row.kind)
    return {
        "id": int(row.id),
        "route_id": row.route_id,
        "point_id": row.point_id,
        "kind": row.kind,
        "kind_label": KIND_LABELS.get(row.kind, row.kind),
        "status": row.status,
        "comment": row.comment or "",
        "cargo_name": row.cargo_name or "",
        "quantity": row.quantity or "",
        "authorized_by": row.authorized_by or "",
        "return_stage": row.return_stage or "",
        "return_stage_label": RETURN_STAGE_LABELS.get(row.return_stage or "", ""),
        "next_return_stage": next_return_stage(row.return_stage or "") if row.kind == "return" and row.status == "open" else None,
        "next_return_stage_label": RETURN_STAGE_LABELS.get(next_return_stage(row.return_stage or "") or "", "")
        if row.kind == "return" and row.status == "open"
        else "",
        "needs_photo": (next_return_stage(row.return_stage or "") in PHOTO_STAGES)
        if row.kind == "return" and row.status == "open"
        else False,
        "return_warning": RETURN_WARNING if row.kind == "return" and not (row.return_stage or "") else "",
        "follow_up_code": follow[0] if follow and row.status == "open" else None,
        "follow_up_label": follow[1] if follow and row.status == "open" else None,
        "opened_by_user_id": row.opened_by_user_id,
        "resolved_at": format_dt_for_app(row.resolved_at),
        "created_at": format_dt_for_app(row.created_at),
        "chat_message_id": row.chat_message_id,
        "stages": return_stages_out(row.stages_json, format_time=format_dt_for_app) if row.kind == "return" else [],
        "chat_text": "",
    }


def _notify_problem(db: Session, route: Route, user: User, title: str, message: str) -> None:
    from mobile_api.chat_router import _route_chat_recipient_ids

    create_notification_for_users(
        db,
        user_ids=_route_chat_recipient_ids(db, route),
        event_type="route_problem",
        title=title,
        message=message,
        route_id=route.id,
        payload={"route_id": route.id, "kind": title},
        skip_user_ids=[user.id],
    )


def _list_incidents(db: Session, route_id: str) -> list[RouteIncident]:
    return list(
        db.scalars(
            select(RouteIncident).where(RouteIncident.route_id == route_id).order_by(RouteIncident.id.desc())
        ).all()
    )


@router.get("/v1/routes/{route_id:path}/incidents")
def list_incidents(
    route_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    route = _assert_can_access_route(db, current_user, route_id)
    return {"items": [_incident_out(row) for row in _list_incidents(db, route.id)]}


@router.post("/v1/mobile/routes/{route_id:path}/incidents", status_code=status.HTTP_201_CREATED)
def create_incident(
    route_id: str,
    payload: IncidentCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    route = _assert_can_access_route(db, current_user, unquote(route_id))
    _assert_driver_assigned(current_user, route)
    kind = (payload.kind or "").strip()
    if kind not in INCIDENT_KINDS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown problem kind")
    comment = (payload.comment or "").strip()
    if kind in NEEDS_REASON and not comment:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Укажите причину")
    unloading_ids = list(
        db.scalars(select(Point.id).where(Point.route_id == route.id, Point.type_point == "unloading")).all()
    )
    if kind == "return":
        if route.status == "cancelled":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Возврат недоступен по отменённому рейсу")
        if not unloading_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Возврат доступен на точках выгрузки")
        if not (payload.cargo_name or "").strip() or not (payload.quantity or "").strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Для возврата укажите количество и краткое наименование груза",
            )
        open_return = db.scalar(
            select(RouteIncident.id).where(
                RouteIncident.route_id == route.id,
                RouteIncident.kind == "return",
                RouteIncident.status == "open",
            )
        )
        if open_return:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Возврат по этому рейсу уже открыт")
    point_id = payload.point_id
    if kind == "return":
        if point_id is None and len(unloading_ids) == 1:
            point_id = int(unloading_ids[0])
        if point_id is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Выберите точку выгрузки")
        if int(point_id) not in {int(x) for x in unloading_ids}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Возврат только для точки выгрузки")
    if point_id is not None:
        point = db.get(Point, int(point_id))
        if point is None or point.route_id != route.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Point not found")
    row = RouteIncident(
        route_id=route.id,
        point_id=point_id,
        kind=kind,
        status="open",
        comment=comment,
        cargo_name=(payload.cargo_name or "").strip(),
        quantity=(payload.quantity or "").strip(),
        opened_by_user_id=current_user.id,
    )
    db.add(row)
    db.flush()
    text = format_incident_chat(
        kind=kind,
        comment=comment,
        cargo_name=row.cargo_name,
        quantity=row.quantity,
    )
    msg = post_route_chat_and_notify(db, route, current_user, text)
    row.chat_message_id = int(msg.id)
    db.add(row)
    if kind != "return":
        _notify_problem(
            db,
            route,
            current_user,
            f"Проблема в рейсе {route.id}",
            f"{KIND_LABELS.get(kind, kind)}: {comment or KIND_LABELS.get(kind, kind)}",
        )
    db.commit()
    db.refresh(row)
    out = _incident_out(row)
    out["chat_text"] = text
    return out


@router.post("/v1/mobile/routes/{route_id:path}/incidents/{incident_id}/follow-up")
def follow_up_incident(
    route_id: str,
    incident_id: int,
    payload: IncidentFollowUpIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    route = _assert_can_access_route(db, current_user, unquote(route_id))
    _assert_driver_assigned(current_user, route)
    row = db.get(RouteIncident, incident_id)
    if row is None or row.route_id != route.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    if row.status != "open":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already resolved")
    follow = FOLLOW_UP.get(row.kind)
    if not follow:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This problem has no follow-up")
    note = (payload.note or "").strip() or follow[1]
    row.status = "resolved"
    row.resolved_at = _now()
    db.add(row)
    text = format_incident_chat(kind=row.kind, comment=note, follow_up=follow[1])
    post_route_chat_and_notify(db, route, current_user, text)
    _notify_problem(db, route, current_user, f"Рейс {route.id}: {follow[1]}", note)
    db.commit()
    db.refresh(row)
    return _incident_out(row)


@router.post("/v1/mobile/routes/{route_id:path}/incidents/{incident_id}/return-stage")
def advance_return_stage(
    route_id: str,
    incident_id: int,
    payload: ReturnStageIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    route = _assert_can_access_route(db, current_user, unquote(route_id))
    _assert_driver_assigned(current_user, route)
    row = db.get(RouteIncident, incident_id)
    if row is None or row.route_id != route.id or row.kind != "return":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return not found")
    if row.status != "open":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Return already finished")
    nxt = next_return_stage(row.return_stage or "")
    if not nxt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Return already delivered")
    if nxt == "issued":
        who = (payload.authorized_by or "").strip()
        if not who:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Укажите, кто разрешил забрать возврат",
            )
        row.authorized_by = who
    extra = (payload.comment or "").strip()
    row.return_stage = nxt
    stamp = _now()
    stages = parse_return_stages(row.stages_json)
    stages[nxt] = {
        "time": stamp.isoformat(),
        "lat": payload.lat,
        "lng": payload.lng,
        "odometer": (payload.odometer or "").strip(),
        "odometer_source": (payload.odometer_source or "").strip(),
    }
    row.stages_json = dump_return_stages(stages)
    if nxt == RETURN_STAGES[-1]:
        row.status = "resolved"
        row.resolved_at = stamp
    db.add(row)
    db.commit()
    db.refresh(row)
    return _incident_out(row)
