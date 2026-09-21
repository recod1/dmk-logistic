from __future__ import annotations

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_display_tz_name = os.getenv("DMK_DISPLAY_TZ", "Europe/Moscow")


def display_zone() -> ZoneInfo:
    try:
        return ZoneInfo(_display_tz_name)
    except Exception:
        return ZoneInfo("Europe/Moscow")


def format_dt_for_app(dt: datetime | None) -> str | None:
    """Человекочитаемое время в часовом поясе приложения (по умолчанию Москва)."""
    if dt is None:
        return None
    value = dt
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(display_zone()).strftime("%d.%m.%Y %H:%M")
