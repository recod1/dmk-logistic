"""Compare planned route points for driver notification text."""

from __future__ import annotations

from typing import Any, Iterable

from utils.onec_datetime import planned_wall_fields


def changed_text(label: str, old: str | None, new: str | None) -> str | None:
    prev = (old or "").strip()
    nxt = (new or "").strip()
    if prev == nxt:
        return None
    if prev and nxt:
        return f"{label}: {prev} → {nxt}"
    return f"{label}: {nxt or '—'}"


def point_kind_label(type_point: str | None) -> str:
    return "Выгрузка" if (type_point or "").strip().lower() == "unloading" else "Загрузка"


def point_plan_text(date_raw: str | None, time_raw: str | None) -> str:
    date_s, time_s = planned_wall_fields(date_raw or "", time_raw or "")
    return " ".join(part for part in (date_s, time_s) if part).strip()


def _attr(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def diff_route_points(existing: Iterable[Any], incoming: Iterable[Any]) -> list[str]:
    existing_list = list(existing)
    incoming_list = list(incoming)
    existing_by_id = {int(_attr(point, "id")): point for point in existing_list if _attr(point, "id") is not None}
    sorted_incoming = sorted(
        enumerate(incoming_list),
        key=lambda item: _attr(item[1], "order_index") if _attr(item[1], "order_index") is not None else item[0],
    )
    used_ids: set[int] = set()
    phrases: list[str] = []
    for new_order, (_, point_in) in enumerate(sorted_incoming):
        type_point = (_attr(point_in, "type_point") or "loading").strip().lower()
        if type_point not in {"loading", "unloading"}:
            type_point = "loading"
        place_point = (_attr(point_in, "place_point") or "").strip()
        date_point = _attr(point_in, "date_point") or ""
        point_time = _attr(point_in, "point_time") or ""
        incoming_id = _attr(point_in, "id")
        old = None
        if incoming_id is not None:
            old = existing_by_id.get(int(incoming_id))
        elif new_order < len(existing_list) and int(_attr(existing_list[new_order], "id")) not in used_ids:
            old = existing_list[new_order]
        kind = point_kind_label(type_point)
        if old is None:
            detail = place_point or point_plan_text(date_point, point_time)
            phrases.append(f"Добавлена {kind}" + (f" · {detail}" if detail else ""))
            continue
        used_ids.add(int(_attr(old, "id")))
        old_kind = point_kind_label(_attr(old, "type_point"))
        old_order = next(
            (idx for idx, item in enumerate(existing_list) if int(_attr(item, "id")) == int(_attr(old, "id"))),
            new_order,
        )
        type_change = changed_text(f"{kind} · тип", old_kind, kind)
        if type_change:
            phrases.append(type_change)
        date_change = changed_text(
            f"{kind} · дата",
            point_plan_text(_attr(old, "date_point"), _attr(old, "point_time")),
            point_plan_text(date_point, point_time),
        )
        if date_change:
            phrases.append(date_change)
        place_change = changed_text(f"{kind} · адрес", _attr(old, "place_point"), place_point)
        if place_change:
            phrases.append(place_change)
        if old_order != new_order:
            order_change = changed_text(f"{kind} · порядок", str(old_order + 1), str(new_order + 1))
            if order_change:
                phrases.append(order_change)
    for old in existing_list:
        if int(_attr(old, "id")) in used_ids:
            continue
        detail = (_attr(old, "place_point") or "").strip() or point_plan_text(_attr(old, "date_point"), _attr(old, "point_time"))
        phrases.append(f"Удалена {point_kind_label(_attr(old, 'type_point'))}" + (f" · {detail}" if detail else ""))
    return phrases
