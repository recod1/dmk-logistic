"""Driver route problems and return workflow labels."""

from __future__ import annotations

import json
from datetime import datetime

INCIDENT_KINDS = ("delay", "breakdown", "no_pass", "no_data", "not_unloading", "return")

KIND_LABELS = {
    "delay": "Опоздание",
    "breakdown": "Поломка",
    "no_pass": "Нет пропуска на въезд",
    "no_data": "Нет данных на загр/выгр",
    "not_unloading": "Не выгружают",
    "return": "Возврат",
}

FOLLOW_UP = {
    "breakdown": ("fixed", "Поломка устранена"),
    "no_pass": ("pass_received", "Пропуск получен"),
    "no_data": ("data_received", "Данные получены"),
}

RETURN_STAGES = ("issued", "loaded", "departed", "registration", "gates", "delivered")

RETURN_STAGE_LABELS = {
    "issued": "Оформил возврат",
    "loaded": "Загрузил возврат",
    "departed": "Выехал на точку",
    "registration": "Регистрация",
    "gates": "Поставил на ворота",
    "delivered": "Возврат сдан",
}

RETURN_WARNING = (
    "‼️ЗАБИРАТЬ ВОЗВРАТ ТОЛЬКО ПОСЛЕ ПОДТВЕРЖДЕНИЯ ОТ ЛОГИСТА "
    "(в любом мессенджере или по телефону)‼️"
)

NEEDS_REASON = {"delay", "breakdown", "not_unloading", "return"}
PHOTO_STAGES = {"loaded", "delivered"}


def parse_return_stages(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def dump_return_stages(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def _as_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def return_stages_out(raw: str | None, *, format_time) -> list[dict]:
    stored = parse_return_stages(raw)
    items = []
    for code in RETURN_STAGES:
        snap = stored.get(code) if isinstance(stored.get(code), dict) else {}
        items.append(
            {
                "code": code,
                "label": RETURN_STAGE_LABELS[code],
                "time": format_time(_as_datetime(snap.get("time"))),
                "lat": snap.get("lat"),
                "lng": snap.get("lng"),
                "odometer": snap.get("odometer") or "",
                "odometer_source": snap.get("odometer_source") or "",
            }
        )
    return items


def next_return_stage(current: str) -> str | None:
    if not current:
        return RETURN_STAGES[0]
    try:
        idx = RETURN_STAGES.index(current)
    except ValueError:
        return RETURN_STAGES[0]
    if idx + 1 >= len(RETURN_STAGES):
        return None
    return RETURN_STAGES[idx + 1]


def format_incident_chat(
    *,
    kind: str,
    comment: str = "",
    cargo_name: str = "",
    quantity: str = "",
    authorized_by: str = "",
    return_stage: str = "",
    follow_up: str = "",
) -> str:
    title = KIND_LABELS.get(kind, kind)
    lines = [f"Проблема в рейсе: {title}"]
    if follow_up:
        lines.append(follow_up)
    if return_stage:
        lines.append(f"Этап возврата: {RETURN_STAGE_LABELS.get(return_stage, return_stage)}")
    if comment.strip():
        lines.append(comment.strip())
    if cargo_name.strip():
        lines.append(f"Груз: {cargo_name.strip()}")
    if quantity.strip():
        lines.append(f"Кол-во: {quantity.strip()}")
    if authorized_by.strip():
        lines.append(f"Разрешил забрать: {authorized_by.strip()}")
    return "\n".join(lines)
