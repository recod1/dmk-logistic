from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class DriverRouteState:
    id: str
    status: str
    created_at: datetime | None


def _created_key(value: datetime | None) -> float:
    if value is None:
        return 0.0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def pick_active_route(routes: list[DriverRouteState]) -> DriverRouteState | None:
    """
    Active route priority:
    1) accepted route in progress ("process"), the oldest first
    2) pending route ("new"), the oldest first
    """
    in_progress = [route for route in routes if route.status == "process"]
    if in_progress:
        return sorted(in_progress, key=lambda item: _created_key(item.created_at))[0]

    pending = [route for route in routes if route.status == "new"]
    if pending:
        return sorted(pending, key=lambda item: _created_key(item.created_at))[0]
    return None


def can_accept_route(route_id: str, routes: list[DriverRouteState]) -> tuple[bool, str | None]:
    """Validate driver route acceptance constraints."""
    target = next((route for route in routes if route.id == route_id), None)
    if target is None:
        return False, "Route not found for current driver"

    if target.status == "process":
        another_process = [route for route in routes if route.status == "process" and route.id != route_id]
        if another_process:
            return False, "Another route is already accepted"
        return True, None

    if target.status != "new":
        return False, f"Route already {target.status}"

    in_progress = [route for route in routes if route.status == "process" and route.id != route_id]
    if in_progress:
        return False, "Another route is already accepted"

    pending = sorted(
        [route for route in routes if route.status == "new"],
        key=lambda item: _created_key(item.created_at),
    )
    if pending and pending[0].id != route_id:
        return False, "Routes must be accepted in creation order"

    return True, None
