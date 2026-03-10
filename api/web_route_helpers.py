# api/web_route_helpers.py — хелперы для отображения рейсов в веб-интерфейсе
import html
from typing import Optional
from database.repositories.route_repository import RouteRepository, STATUS_LABELS_RU
from utils.telegram_helpers import format_point_time_display


STATUS_TEXTS = {
    "new": "Не принят",
    "process": "В процессе",
    "success": "Завершен",
    "cancelled": "Отменён",
}

POINT_STATUS_RU = {
    "new": "Принят",
    "process": "Выехал на точку",
    "registration": "Зарегистрировался",
    "load": "На воротах",
    "docs": "Забрал документы",
    "success": "Завершена",
}


def build_route_detail_html(
    route,
    route_repository: RouteRepository,
    user_repository,
) -> str:
    """Формирует HTML-описание рейса для веб-страницы (без tg:// ссылок)."""
    driver = user_repository.get_by_tg_id(route.tg_id)
    driver_name = driver.name if driver else "Неизвестно"
    number_auto = (route.number_auto or "").strip()
    human_status = STATUS_TEXTS.get(route.status, route.status)

    active_point_status = None
    active_point_type = None
    active_point_place = None
    active_point_time = None
    points_ids = [x for x in (route.points or "").split(",") if x.strip() and x.strip() != "0"]
    for point_id_str in points_ids:
        try:
            pt = route_repository.get_point_by_id(int(point_id_str))
            if pt and pt.status != "success":
                active_point_status = POINT_STATUS_RU.get(pt.status, pt.status)
                active_point_type = "Загрузка" if pt.type_point == "loading" else "Выгрузка"
                active_point_place = (pt.place_point or "").strip() or None
                times = [
                    t for t in (
                        pt.time_accepted, pt.time_registration, pt.time_put_on_gate,
                        pt.time_docs, pt.time_departure
                    )
                    if t and str(t).strip() and str(t) not in ("0", "")
                ]
                active_point_time = times[-1] if times else None
                break
        except ValueError:
            continue

    if route.status == "process" and active_point_status is not None:
        status_line = html.escape(active_point_status)
        if active_point_type:
            status_line += ", " + html.escape(active_point_type)
        if active_point_place:
            status_line += ", " + html.escape(active_point_place)
        if active_point_time:
            status_line += ", " + html.escape(format_point_time_display(active_point_time))
    else:
        status_line = human_status
        if active_point_type:
            status_line += ", " + html.escape(active_point_type)
        if active_point_place:
            status_line += ", " + html.escape(active_point_place)
        if active_point_status:
            status_line += ", " + html.escape(active_point_status)
        if active_point_time:
            status_line += ", " + html.escape(format_point_time_display(active_point_time))

    def _esc(text):
        return html.escape((text or "").strip() or "—")

    lines = [
        f"<strong>N рейса:</strong> <code>{_esc(str(route.id))}</code>",
        f"<strong>Водитель:</strong> {_esc(driver_name)}",
        f"<strong>ТС:</strong> <code>{_esc(number_auto)}</code>",
        f"<strong>Статус рейса:</strong> {status_line}",
        "",
    ]
    if getattr(route, "trailer_number", None) and route.trailer_number:
        lines.append(f"🛞 Прицеп: {_esc(route.trailer_number)}")
    if route.temperature:
        lines.append(f"🌡 Температура: {_esc(route.temperature)}")
    if route.dispatcher_contacts:
        lines.append(f"☎ Контакты: {_esc(route.dispatcher_contacts)}")
    if getattr(route, "registration_number", None) and route.registration_number:
        lines.append(f"📋 N регистрации: {_esc(route.registration_number)}")
    lines.append("")
    lines.append("📍 <strong>Точки:</strong>")

    for point_id_str in points_ids:
        try:
            point_id = int(point_id_str)
        except ValueError:
            continue
        point = route_repository.get_point_by_id(point_id)
        if not point:
            continue
        type_emoji = "📦" if point.type_point == "loading" else "📤"
        type_text = "Загрузка" if point.type_point == "loading" else "Выгрузка"
        status_pt = POINT_STATUS_RU.get(point.status, point.status)
        line = f"  📅 {point.date_point} | {type_emoji} {type_text}: {point.place_point} — {status_pt}"
        if point.time_accepted and point.time_accepted != "0":
            line += f"\n    🚗 Выехал: {format_point_time_display(point.time_accepted)}"
        if point.time_registration and point.time_registration not in ("0", ""):
            line += f"\n    📝 Регистрация: {format_point_time_display(point.time_registration)}"
        if point.time_put_on_gate and point.time_put_on_gate not in ("0", ""):
            line += f"\n    🚪 На ворота: {format_point_time_display(point.time_put_on_gate)}"
        if point.time_docs and point.time_docs not in ("0", ""):
            line += f"\n    📋 Документы: {format_point_time_display(point.time_docs)}"
        if point.time_departure and point.time_departure not in ("0", ""):
            line += f"\n    🏁 Выехал: {format_point_time_display(point.time_departure)}"
        lines.append(line)
        lines.append("")

    if not points_ids:
        lines.append("  📭 Точек нет")

    return "\n".join(lines)


def get_driver_name(user_repository, tg_id: int) -> str:
    """Получить имя водителя по tg_id."""
    user = user_repository.get_by_tg_id(tg_id)
    return user.name if user else "Неизвестно"


def build_route_detail_data(route, route_repository: RouteRepository, user_repository):
    """Возвращает структурированные данные рейса для шаблона."""
    driver = user_repository.get_by_tg_id(route.tg_id)
    driver_name = driver.name if driver else "Неизвестно"
    human_status = STATUS_TEXTS.get(route.status, route.status)

    active_point = None
    points_ids = [x for x in (route.points or "").split(",") if x.strip() and x.strip() != "0"]
    for point_id_str in points_ids:
        try:
            pt = route_repository.get_point_by_id(int(point_id_str))
            if pt and pt.status != "success":
                times = [
                    t for t in (
                        pt.time_accepted, pt.time_registration, pt.time_put_on_gate,
                        pt.time_docs, pt.time_departure
                    )
                    if t and str(t).strip() and str(t) not in ("0", "")
                ]
                active_point = {
                    "status": POINT_STATUS_RU.get(pt.status, pt.status),
                    "type": "Загрузка" if pt.type_point == "loading" else "Выгрузка",
                    "place": (pt.place_point or "").strip() or None,
                    "time": format_point_time_display(times[-1]) if times else None,
                }
                break
        except ValueError:
            continue

    status_display = human_status
    if route.status == "process" and active_point:
        status_display = ", ".join(
            x for x in [active_point["status"], active_point["type"], active_point["place"], active_point["time"]] if x
        )
    elif active_point:
        status_display = ", ".join(
            x for x in [human_status, active_point["type"], active_point["place"], active_point["status"], active_point["time"]] if x
        )

    STATUS_STEPS = [
        ("process", "Выехал на точку", "time_accepted", "🚗"),
        ("registration", "Регистрация", "time_registration", "📝"),
        ("load", "На воротах", "time_put_on_gate", "🚪"),
        ("docs", "Забрал документы", "time_docs", "📋"),
        ("success", "Выехал с точки", "time_departure", "🏁"),
    ]

    points_data = []
    for point_id_str in points_ids:
        try:
            point_id = int(point_id_str)
        except ValueError:
            continue
        point = route_repository.get_point_by_id(point_id)
        if not point:
            continue
        type_text = "Загрузка" if point.type_point == "loading" else "Выгрузка"
        status_pt = POINT_STATUS_RU.get(point.status, point.status)

        status_data = route_repository.get_point_status_data(getattr(point, "odometer", None))
        point_lat = getattr(point, "lat", None)
        point_lng = getattr(point, "lng", None)

        status_steps = []
        for st_key, st_label, time_field, emoji in STATUS_STEPS:
            time_val = getattr(point, time_field, None)
            has_time = time_val and str(time_val).strip() and str(time_val) not in ("0", "")
            d = status_data.get(st_key, {}) if status_data else {}
            odometer_val = d.get("o")
            lat_val = d.get("lat")
            lng_val = d.get("lng")
            status_steps.append({
                "key": st_key,
                "label": st_label,
                "emoji": emoji,
                "time": format_point_time_display(time_val) if has_time else None,
                "done": has_time,
                "odometer": odometer_val,
                "lat": lat_val,
                "lng": lng_val,
            })

        points_data.append({
            "type": type_text,
            "type_emoji": "📦" if point.type_point == "loading" else "📤",
            "date": point.date_point,
            "place": point.place_point,
            "status": status_pt,
            "status_steps": status_steps,
            "point_lat": point_lat,
            "point_lng": point_lng,
            "point_odometer_raw": getattr(point, "odometer", None),
        })

    return {
        "driver_name": driver_name,
        "status_display": status_display,
        "points_data": points_data,
        "trailer_number": (getattr(route, "trailer_number", None) or "").strip() or None,
        "temperature": (route.temperature or "").strip() or None,
        "dispatcher_contacts": (route.dispatcher_contacts or "").strip() or None,
        "registration_number": (getattr(route, "registration_number", None) or "").strip() or None,
        "number_auto": (route.number_auto or "").strip() or None,
    }
