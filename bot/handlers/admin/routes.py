# handlers/admin/routes.py
import re
import html
import calendar
from datetime import datetime
from urllib.parse import quote
from aiogram import Router, types, F
from utils.telegram_helpers import copy_link_fio, copy_link_text, format_point_time_display
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards.admin_kb import (
    get_routes_keyboard,
    get_route_point_keyboard,
    get_point_type_keyboard,
    get_admin_main_keyboard,
    get_admin_completed_routes_period_keyboard,
    get_admin_period_selection_keyboard,
    get_admin_months_keyboard,
)

from keyboards.driver_kb import get_route_confirm_keyboard
from states.route_states import (
    RouteState,
    PointState,
    AdminRouteDeleteState,
    AdminRouteSearchState,
    AdminRouteSearchByAutoState,
    AdminRouteCancelState,
    AdminRouteSearchByIdState,
    AdminRouteFilterByState,
    AdminRouteReassignState,
    AdminRouteEditState,
    AdminRouteCompletedPeriodState,
    OnecMissingParamState,
)
from database.repositories.route_repository import RouteRepository, STATUS_LABELS_RU
from database.repositories.user_repository import UserRepository
from core.bot import create_bot
from config.settings import UserRole

router = Router()


def _parse_time_dmy_hm(s: str):
    """Парсит время в формате дд.мм.гггг чч:мм. Возвращает datetime или None."""
    if not s or not str(s).strip():
        return None
    s = str(s).strip()
    if " (" in s:
        s = s.split(" (")[0].strip()
    try:
        return datetime.strptime(s, "%d.%m.%Y %H:%M")
    except ValueError:
        return None


def _format_duration(minutes: float) -> str:
    """Форматирует длительность в часы и минуты."""
    if minutes < 0:
        return "—"
    h = int(minutes // 60)
    m = int(minutes % 60)
    if h > 0:
        return f"{h} ч {m} мин"
    return f"{m} мин"


def _calc_route_times(route, route_repository: RouteRepository) -> list:
    """Вычисляет длительности по рейсу. Возвращает список строк для отображения."""
    lines = []
    points_ids = [x for x in (route.points or "").split(",") if x.strip() and x.strip() != "0"]
    if not points_ids:
        return lines

    status_fields = [
        ("time_accepted", "🚗 Выехал"),
        ("time_registration", "📝 Регистрация"),
        ("time_put_on_gate", "🚪 На ворота"),
        ("time_docs", "📋 Документы"),
        ("time_departure", "🏁 Выехал с точки"),
    ]
    all_events = []
    points_list = []
    for point_id_str in points_ids:
        try:
            pt = route_repository.get_point_by_id(int(point_id_str))
        except ValueError:
            continue
        if not pt:
            continue
        points_list.append(pt)
        type_pt = "Загрузка" if pt.type_point == "loading" else "Выгрузка"
        for field, label in status_fields:
            t = getattr(pt, field, None)
            if t and str(t) not in ("0", ""):
                dt = _parse_time_dmy_hm(t)
                if dt:
                    all_events.append((dt, f"{label} ({type_pt})"))

    if len(all_events) < 2:
        return lines

    all_events.sort(key=lambda x: x[0])
    lines.append("")
    lines.append("⏱ <b>Фактическое время по рейсу:</b>")

    for i in range(len(all_events) - 1):
        _, label1 = all_events[i]
        _, label2 = all_events[i + 1]
        diff = (all_events[i + 1][0] - all_events[i][0]).total_seconds() / 60
        lines.append(f"  • {label1} → {label2}: {_format_duration(diff)}")

    first_pt = points_list[0] if points_list else None
    first_accepted = _parse_time_dmy_hm(getattr(first_pt, "time_accepted", None)) if first_pt else None
    last_docs = None
    for pt in reversed(points_list):
        last_docs = _parse_time_dmy_hm(getattr(pt, "time_docs", None))
        if last_docs:
            break

    if first_accepted and last_docs:
        total = (last_docs - first_accepted).total_seconds() / 60
        lines.append(f"  • <b>Общее:</b> Выехал (1-я) → Документы (посл.): {_format_duration(total)}")

    first_reg = _parse_time_dmy_hm(getattr(first_pt, "time_registration", None)) if first_pt else None
    if first_reg and last_docs:
        reg_to_docs = (last_docs - first_reg).total_seconds() / 60
        lines.append(f"  • Регистрация (1-я) → Документы (посл.): {_format_duration(reg_to_docs)}")

    return lines


async def _back_from_route_creation(message: types.Message, state: FSMContext):
    """Выход из создания рейса (ручной или 1С) по кнопке Назад."""
    await state.clear()
    await message.reply("Создание рейса отменено.", reply_markup=get_routes_keyboard())


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(RouteState))
async def back_from_route_creation_route(message: types.Message, state: FSMContext):
    await _back_from_route_creation(message, state)


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(PointState))
async def back_from_route_creation_point(message: types.Message, state: FSMContext):
    await _back_from_route_creation(message, state)


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(OnecMissingParamState))
async def back_from_route_creation_onec(message: types.Message, state: FSMContext):
    await _back_from_route_creation(message, state)


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(AdminRouteCancelState))
async def back_from_route_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.reply("Отмена рейса отменена.", reply_markup=get_routes_keyboard())


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(AdminRouteSearchByIdState))
async def back_from_route_search_id(message: types.Message, state: FSMContext):
    await state.clear()
    await message.reply("Поиск отменён.", reply_markup=get_routes_keyboard())


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(AdminRouteReassignState))
async def back_from_route_reassign(message: types.Message, state: FSMContext):
    await state.clear()
    await message.reply("Переназначение отменено.", reply_markup=get_routes_keyboard())


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(AdminRouteEditState))
async def back_from_route_edit(message: types.Message, state: FSMContext):
    await state.clear()
    await message.reply("Изменение рейса отменено.", reply_markup=get_routes_keyboard())


# Лимит Telegram на длину сообщения (символов)
TELEGRAM_MAX_MESSAGE_LENGTH = 4096
# Максимум рейсов в одном сообщении при постраничном выводе
ROUTES_PAGE_SIZE = 10


def _build_routes_text(
    routes,
    route_repository: RouteRepository,
    user_repository: UserRepository,
    title: str,
) -> str:
    """Формирует общий текст по списку рейсов с точками."""
    from database.models.route import Route  # только для типов

    text = f"{title}\n\n"

    status_texts = {
        "new": "Не принят",
        "process": "В процессе",
        "success": "Завершен",
        "cancelled": "Отменён",
    }

    for route in routes:
        driver = user_repository.get_by_tg_id(route.tg_id)
        driver_name = driver.name if driver else "Неизвестно"

        status_emoji = {
            "new": "📋",
            "process": "🚚",
            "success": "✅",
            "cancelled": "❌",
        }.get(route.status, "❓")

        human_status = status_texts.get(route.status, route.status)

        text += (
            f"{status_emoji} Рейс: {route.id}\n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"📊 Статус: {human_status}\n"
        )
        if route.number_auto:
            text += f"🚚 ТС: {route.number_auto}\n"
        if getattr(route, 'trailer_number', None):
            text += f"🛞 Прицеп: {route.trailer_number}\n"
        if route.temperature:
            text += f"🌡 Температура: {route.temperature}\n"
        if route.dispatcher_contacts:
            text += f"☎ Контакты: {route.dispatcher_contacts}\n"
        if getattr(route, 'registration_number', None):
            text += f"📋 N регистрации: {route.registration_number}\n"

        points_ids = route.points.split(",")
        point_count = 0
        for point_id in points_ids:
            if point_id == "0":
                continue

            point = route_repository.get_point_by_id(int(point_id))
            if point:
                point_count += 1
                type_emoji = "📦" if point.type_point == "loading" else "📤"
                type_text = "Загрузка" if point.type_point == "loading" else "Выгрузка"
                text += f"  {type_emoji} {type_text}: {point.place_point} ({point.date_point})\n"

        if point_count == 0:
            text += "  📭 Точек нет\n"

        text += "\n"

    return text


def _build_routes_list_html(
    routes,
    route_repository: RouteRepository,
    user_repository: UserRepository,
    title: str,
) -> str:
    """Формирует HTML-текст списка рейсов в том же формате, что и «Поиск по номеру рейса»."""
    parts = [f"<b>{html.escape(title)}</b>", ""]
    for route in routes:
        parts.append(_build_route_detail_html(route, route_repository, user_repository))
        parts.append("")
    return "\n".join(parts).strip()


def _build_route_detail_html(
    route,
    route_repository: RouteRepository,
    user_repository: UserRepository,
) -> str:
    """Один рейс: номер, водитель, ТС в <code> для копирования; точки с временами."""
    driver = user_repository.get_by_tg_id(route.tg_id)
    driver_name = driver.name if driver else "Неизвестно"
    number_auto = (route.number_auto or "").strip()
    status_texts = {"new": "Не принят", "process": "В процессе", "success": "Завершен", "cancelled": "Отменён"}
    point_status_ru = {
        "new": "Принят",
        "process": "Выехал на точку",
        "registration": "Зарегистрировался",
        "load": "На воротах",
        "docs": "Забрал документы",
        "success": "Завершена",
    }
    human_status = status_texts.get(route.status, route.status)
    active_point_status = None
    active_point_type = None
    active_point_place = None
    active_point_time = None
    points_ids = [x for x in (route.points or "").split(",") if x.strip() and x.strip() != "0"]
    for point_id_str in points_ids:
        try:
            pt = route_repository.get_point_by_id(int(point_id_str))
            if pt and pt.status != "success":
                active_point_status = point_status_ru.get(pt.status, pt.status)
                active_point_type = "Загрузка" if pt.type_point == "loading" else "Выгрузка"
                active_point_place = (pt.place_point or "").strip() or None
                times = [t for t in (pt.time_accepted, pt.time_registration, pt.time_put_on_gate, pt.time_docs, pt.time_departure)
                         if t and str(t).strip() and str(t) not in ("0", "")]
                active_point_time = times[-1] if times else None
                break
        except ValueError:
            continue
    # Когда рейс в процессе — в начале строки статуса выводим статус текущей точки, а не «В процессе»
    if route.status == "process" and active_point_status is not None:
        status_line = html.escape(active_point_status)
        if active_point_type is not None:
            status_line += ", {}".format(html.escape(active_point_type))
        if active_point_place:
            status_line += ", {}".format(html.escape(active_point_place))
        if active_point_time:
            status_line += ", {}".format(html.escape(format_point_time_display(active_point_time)))
    else:
        status_line = human_status
        if active_point_type is not None:
            status_line += ", {}".format(html.escape(active_point_type))
        if active_point_place:
            status_line += ", {}".format(html.escape(active_point_place))
        if active_point_status is not None:
            status_line += ", {}".format(html.escape(active_point_status))
        if active_point_time:
            status_line += ", {}".format(html.escape(format_point_time_display(active_point_time)))

    def _copy_link(text):
        safe = (text or "").strip() or "—"
        return '<a href="tg://copy?text={}"><code>{}</code></a>'.format(quote(safe), html.escape(safe))

    lines = [
        "<b>N рейса:</b> {}".format(_copy_link(str(route.id))),
        "<b>Водитель:</b> {}".format(copy_link_fio(driver_name)),
        "<b>ТС:</b> {}".format(_copy_link(number_auto or "—")),
        "<b>Статус рейса:</b> {}".format(status_line),
        "",
    ]
    if getattr(route, 'trailer_number', None) and route.trailer_number:
        lines.append("🛞 Прицеп: {}".format(copy_link_text(route.trailer_number)))
    if route.temperature:
        lines.append("🌡 Температура: {}".format(html.escape(route.temperature)))
    if route.dispatcher_contacts:
        lines.append("☎ Контакты: {}".format(html.escape(route.dispatcher_contacts)))
    if getattr(route, 'registration_number', None) and route.registration_number:
        lines.append("📋 N регистрации: {}".format(html.escape(route.registration_number)))
    lines.append("")
    lines.append("📍 <b>Точки:</b>")

    points_ids = [x for x in (route.points or "").split(",") if x.strip() and x.strip() != "0"]
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
        status_pt = point_status_ru.get(point.status, point.status)
        line = "  📅 {} | {} {}: {} — {}".format(
            point.date_point, type_emoji, type_text, point.place_point, status_pt
        )
        if point.time_accepted and point.time_accepted != "0":
            line += "\n    🚗 Выехал: {}".format(format_point_time_display(point.time_accepted))
        if point.time_registration and point.time_registration not in ("0", ""):
            line += "\n    📝 Регистрация: {}".format(format_point_time_display(point.time_registration))
        if point.time_put_on_gate and point.time_put_on_gate not in ("0", ""):
            line += "\n    🚪 На ворота: {}".format(format_point_time_display(point.time_put_on_gate))
        if point.time_docs and point.time_docs not in ("0", ""):
            line += "\n    📋 Документы: {}".format(format_point_time_display(point.time_docs))
        if point.time_departure and point.time_departure not in ("0", ""):
            line += "\n    🏁 Выехал: {}".format(format_point_time_display(point.time_departure))
        status_data = route_repository.get_point_status_data(getattr(point, 'odometer', None))
        if status_data:
            for st, label in STATUS_LABELS_RU.items():
                if st not in status_data:
                    continue
                d = status_data[st]
                parts = []
                if d.get("o"):
                    parts.append("📏 {}: {}".format(label, html.escape(d["o"])))
                if d.get("lat") is not None and d.get("lng") is not None:
                    parts.append("📍 {:.6f}, {:.6f}".format(d["lat"], d["lng"]))
                if parts:
                    line += "\n    " + " | ".join(parts)
        elif getattr(point, 'lat', None) is not None and getattr(point, 'lng', None) is not None:
            line += "\n    📍 Координаты: {:.6f}, {:.6f}".format(point.lat, point.lng)
        elif getattr(point, 'odometer', None):
            line += "\n    📏 Одометр: {}".format(html.escape(point.odometer))
        lines.append(line)
        lines.append("")  # пустая строка между точками
    if not points_ids:
        lines.append("  📭 Точек нет")
    time_lines = _calc_route_times(route, route_repository)
    if time_lines:
        lines.extend(time_lines)
    return "\n".join(lines)


async def _send_routes_paginated(
    send_func,
    routes: list,
    title: str,
    route_repository: RouteRepository,
    user_repository: UserRepository,
    reply_markup=None,
):
    """
    Отправляет список рейсов постранично в формате как «Поиск по номеру рейса» (HTML).
    send_func должен принимать (text, reply_markup=None, **kwargs) для передачи parse_mode="HTML".
    """
    if not routes:
        return
    total = len(routes)
    page = 0
    start = 0
    while start < total:
        chunk = routes[start : start + ROUTES_PAGE_SIZE]
        page += 1
        total_pages = (total + ROUTES_PAGE_SIZE - 1) // ROUTES_PAGE_SIZE
        page_title = f"{title}" if total_pages <= 1 else f"{title} (стр. {page}/{total_pages})"
        text = _build_routes_list_html(chunk, route_repository, user_repository, page_title)
        while len(text) > TELEGRAM_MAX_MESSAGE_LENGTH and len(chunk) > 1:
            chunk = chunk[: len(chunk) // 2]
            text = _build_routes_list_html(chunk, route_repository, user_repository, page_title)
        use_markup = reply_markup if (start + len(chunk)) >= total else None
        await send_func(text, reply_markup=use_markup, parse_mode="HTML")
        start += len(chunk)


def _get_route_format_keyboard():
    """Клавиатура выбора формата создания рейса"""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="✏️ Вручную", callback_data="route_format_manual"),
        types.InlineKeyboardButton(text="📄 Формат 1С", callback_data="route_format_1c"),
    )
    return builder.as_markup()


def _format_route_info_for_driver(route) -> str:
    """Формирует блок с полной информацией о рейсе (ТС, прицеп, температура, контакты, N регистрации). Копируемые ТС и прицеп — HTML."""
    number_auto = (route.number_auto or "").strip()
    trailer_number = (getattr(route, 'trailer_number', None) or "").strip()
    temperature = (route.temperature or "").strip()
    dispatcher_contacts = (route.dispatcher_contacts or "").strip()
    registration_number = (getattr(route, 'registration_number', None) or "").strip()
    lines = [
        f"📋 N рейса: {route.id}",
        f"🚚 ТС: {copy_link_text(number_auto or '—')}",
        f"🛞 Прицеп: {copy_link_text(trailer_number or '—')}",
        f"🌡 Температура: {temperature or '—'}",
        f"☎ Контакты диспетчера: {dispatcher_contacts or '—'}",
        f"📋 N регистрации: {registration_number or '—'}",
    ]
    return "\n".join(lines)


async def _notify_driver_about_new_route(
    route,
    route_repository: RouteRepository,
    user_repository: UserRepository,
    bot,
):
    """Отправка уведомления водителю о новом рейсе. Если есть активный рейс — одно короткое сообщение без дублирования деталей."""
    try:
        all_routes = route_repository.get_all()
        driver_active_routes = [r for r in all_routes if r.tg_id == route.tg_id and r.status == "process"]

        if driver_active_routes:
            # Одно короткое сообщение: не дублируем полные детали рейса и предупреждение в два блока
            text = (
                f"📋 У вас новый рейс (N рейса: {route.id}).\n\n"
                f"⚠️ У вас уже есть активный рейс: {driver_active_routes[0].id}. "
                f"Новый рейс будет доступен после завершения текущего.\n\n"
                "Чтобы посмотреть новый рейс, нажмите «🚚 Рейс»."
            )
            await bot.send_message(int(route.tg_id), text, parse_mode="HTML")
            return
        # Нет активного рейса — полная информация и кнопка принятия
        text = "📋 У вас новый рейс\n\n"
        text += _format_route_info_for_driver(route)
        text += "\n\n"
        points_ids = route.points.split(",") if route.points != "0" else []
        if points_ids and points_ids[0] != "0":
            text += "\n📍 Точки:\n"
            for point_id_str in points_ids:
                if point_id_str == "0":
                    continue
                try:
                    point_id = int(point_id_str)
                    point = route_repository.get_point_by_id(point_id)
                    if point:
                        type_emoji = "📦" if point.type_point == "loading" else "📤"
                        type_text = "Загрузка" if point.type_point == "loading" else "Выгрузка"
                        text += f"  {type_emoji} {type_text}: {point.place_point} ({point.date_point})\n"
                except ValueError:
                    continue
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.add(types.InlineKeyboardButton(
            text="✅ Принять рейс",
            callback_data=f"accept_route_{route.id}"
        ))
        await bot.send_message(int(route.tg_id), text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка при отправке уведомления водителю {route.tg_id}: {e}")


@router.message(F.text == "🚚 Рейсы")
async def menu_routes(message: types.Message):
    await message.reply("🚚 Рейсы", reply_markup=get_routes_keyboard())

@router.message(F.text == "➕ Создать рейс")
async def create_route(message: types.Message, state: FSMContext):
    """Начало создания рейса - выбор формата"""
    await message.reply(
        "Выберите формат создания рейса:",
        reply_markup=_get_route_format_keyboard()
    )

@router.message(RouteState.route_id)
async def create_route_id(message: types.Message, state: FSMContext, route_repository: RouteRepository):
    """Получение номера рейса для ручного формата"""
    await state.update_data(route_id=message.text)
    data = await state.get_data()
    id_exist = route_repository.route_id_exists(data["route_id"])

    if id_exist:
        await message.reply("❌ Рейс с таким номером уже существует", reply_markup=get_routes_keyboard())
        await state.clear()
    else:
        await state.set_state(RouteState.temperature)
        await message.reply("Введите температурный режим (или отправьте \"-\" для пропуска):", reply_markup=get_routes_keyboard())

def _get_create_route_number_auto_prompt():
    return (
        "Введите номер ТС.\n\n"
        "Поддерживаемые форматы:\n"
        "• А111АА222\n"
        "• А111АА22\n"
        "• ЕН068477 (спец. номер)\n\n"
        "Примеры корректных номеров:\n"
        "• А123ВС456\n"
        "• М567ОР78\n"
        "• В901ТУ123\n"
        "• ЕН068477"
    )


@router.message(RouteState.driver)
async def create_route_driver(
    message: types.Message,
    state: FSMContext,
    user_repository: UserRepository,
    route_repository: RouteRepository
):
    """Получение ФИО водителя (можно часть ФИО для поиска). Сохраняем только выбранного по tg_id."""
    text = message.text.strip()
    await state.update_data(driver=text)
    # Сначала ищем по части ФИО — так мы видим всех подходящих и не путаем при одинаковых именах
    users = user_repository.search_drivers_by_name_part(text, limit=15)
    if not users:
        await state.clear()
        await message.reply("❌ Водители не найдены. Введите ФИО или часть ФИО.", reply_markup=get_routes_keyboard())
        return
    if len(users) == 1:
        u = users[0]
        if not u.tg_id or str(u.tg_id) == "0":
            await state.clear()
            await message.reply("❌ Найденный водитель не активирован в боте.", reply_markup=get_routes_keyboard())
            return
        await state.update_data(driver_tg_id=int(u.tg_id), driver_name=u.name)
        await state.set_state(RouteState.number_auto)
        await message.reply(_get_create_route_number_auto_prompt(), reply_markup=get_routes_keyboard())
        return
    # Несколько кандидатов — показываем список, в callback передаём только tg_id
    builder = InlineKeyboardBuilder()
    for u in users[:10]:
        if u.tg_id and str(u.tg_id) != "0":
            builder.row(types.InlineKeyboardButton(text=u.name, callback_data=f"create_route_driver_{u.tg_id}"))
    await message.reply("Выберите водителя:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("create_route_driver_"))
async def create_route_driver_selected(
    callback: types.CallbackQuery,
    state: FSMContext,
    user_repository: UserRepository,
):
    tg_id_str = callback.data.replace("create_route_driver_", "")
    try:
        tg_id = int(tg_id_str)
    except ValueError:
        await callback.answer("Ошибка.")
        return
    user = user_repository.get_by_tg_id(tg_id)
    if not user:
        await callback.answer("Водитель не найден.")
        return
    await state.update_data(driver_tg_id=user.tg_id, driver_name=user.name)
    await state.set_state(RouteState.number_auto)
    await callback.message.edit_text("Водитель выбран. " + _get_create_route_number_auto_prompt())
    await callback.answer()


@router.message(RouteState.number_auto)
async def create_route_number_auto(
    message: types.Message,
    state: FSMContext,
):
    """Получаем и валидируем номер ТС, затем определяем дальнейший путь в зависимости от формата."""
    number_auto = message.text.strip().upper()

    # Валидация формата (как в заявке на ремонт):
    # 1) А111АА222 или А111АА22 (1 буква, 3 цифры, 2 буквы, 2-3 цифры)
    # 2) ЕН068477 (2 буквы + 6 цифр)
    pattern_std = r'^[А-ЯA-Z]\d{3}[А-ЯA-Z]{2}\d{2,3}$'
    pattern_spec = r'^[А-ЯA-Z]{2}\d{6}$'

    if not (re.match(pattern_std, number_auto) or re.match(pattern_spec, number_auto)):
        await message.reply(
            "❌ Неверный формат номера ТС!\n\n"
            "Номер должен быть в одном из форматов:\n"
            "• А111АА222 (буква-цифра-цифра-цифра-буква-буква-цифра-цифра-цифра)\n"
            "• А111АА22 (буква-цифра-цифра-цифра-буква-буква-цифра-цифра)\n"
            "• ЕН068477 (2 буквы + 6 цифр)\n\n"
            "Примеры корректных номеров:\n"
            "• А123ВС456\n"
            "• М567ОР78\n"
            "• В901ТУ123\n"
            "• ЕН068477\n\n"
            "Пожалуйста, введите номер ТС в правильном формате:",
            reply_markup=get_routes_keyboard(),
        )
        return

    await state.update_data(number_auto=number_auto)
    
    # Проверяем, какой формат был выбран (из состояния)
    data = await state.get_data()
    format_type = data.get("format_type")
    
    if format_type == "manual":
        # Для ручного формата: запрашиваем номер прицепа, затем номер рейса
        await state.set_state(RouteState.trailer_number)
        await message.reply(
            "Введите номер прицепа (или \"-\" для пропуска):",
            reply_markup=get_routes_keyboard(),
        )
    elif format_type == "1c":
        # Для формата 1С: запрашиваем сообщение в формате 1С
        await state.set_state(RouteState.onec_text)
        await message.reply(
            "📄 Вставьте данные рейса в формате 1С одним сообщением.\n\n"
            "Формат: номер рейса, Номер для регистрации, ФИО водителя, Номер ТС, Номер прицепа, "
            "Температура, Контакты; затем блоки Загр/Выгр и Организация. Недостающее можно ввести после (или пропустить).",
            reply_markup=get_routes_keyboard(),
        )
    else:
        # Если формат не выбран, предлагаем выбрать
        await message.reply(
            f"✅ Номер ТС принят: {number_auto}\n\n"
            "Выберите формат создания рейса:",
            reply_markup=_get_route_format_keyboard(),
        )


@router.callback_query(F.data == "route_format_manual")
async def route_format_manual(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    """Выбор ручного формата создания рейса."""
    await state.update_data(format_type="manual")
    
    data = await state.get_data()
    
    # Проверяем, есть ли уже ФИО водителя
    if not data.get("driver_tg_id"):
        # Если нет, начинаем с запроса ФИО водителя
        await state.set_state(RouteState.driver)
        await callback.message.answer("Введите ФИО водителя:", reply_markup=get_routes_keyboard())
    elif not data.get("number_auto"):
        # Если есть ФИО, но нет номера ТС, запрашиваем номер ТС
        await state.set_state(RouteState.number_auto)
        await callback.message.answer(
            "Введите номер ТС.\n\n"
            "Поддерживаемые форматы:\n"
            "• А111АА222\n"
            "• А111АА22\n"
            "• ЕН068477 (спец. номер)\n\n"
            "Примеры корректных номеров:\n"
            "• А123ВС456\n"
            "• М567ОР78\n"
            "• В901ТУ123\n"
            "• ЕН068477",
            reply_markup=get_routes_keyboard(),
        )
    else:
        # Если есть и ФИО, и номер ТС, запрашиваем номер рейса
        await state.set_state(RouteState.route_id)
        await callback.message.answer("Введите номер рейса:", reply_markup=get_routes_keyboard())
    
    await callback.answer()


@router.callback_query(F.data == "route_format_1c")
async def route_format_onec(callback: types.CallbackQuery, state: FSMContext):
    """Выбор формата 1С — сразу запрашиваем сообщение в формате 1С."""
    await state.update_data(format_type="1c")
    await state.set_state(RouteState.onec_text)
    await callback.message.answer(
        "📄 Вставьте данные рейса в формате 1С одним сообщением.\n\n"
        "В сообщении могут быть (в любом порядке, часть можно опустить):\n"
        "• Номер рейса (первая строка или строка с номером)\n"
        "• N регистрации: ...\n"
        "• ФИО водителя: ...\n"
        "• Номер ТС: ...\n"
        "• Номер прицепа: ...\n"
        "• Температура: ...\n"
        "• Контакты ООО \"ДМК\": ...\n"
        "Далее блоки точек: Загр:/Выгр: и Организация: <адрес>\n\n"
        "Недостающие данные запросятся после отправки сообщения (можно будет пропустить, кроме ФИО водителя).",
        reply_markup=get_routes_keyboard(),
    )
    await callback.answer()


@router.message(RouteState.temperature)
async def create_route_temperature(message: types.Message, state: FSMContext):
    """Получение температурного режима для ручного формата"""
    temperature = message.text.strip()
    if temperature == "-":
        temperature = ""
    await state.update_data(temperature=temperature)
    await state.set_state(RouteState.dispatcher_contacts)
    await message.reply("Введите контакты диспетчера (или отправьте \"-\" для пропуска):", reply_markup=get_routes_keyboard())


@router.message(RouteState.dispatcher_contacts)
async def create_route_dispatcher_contacts(message: types.Message, state: FSMContext):
    """Получение контактов диспетчера, далее запрос номера для регистрации"""
    dispatcher_contacts = message.text.strip()
    if dispatcher_contacts == "-":
        dispatcher_contacts = ""
    await state.update_data(dispatcher_contacts=dispatcher_contacts)
    await state.set_state(RouteState.registration_number)
    await message.reply("Введите N регистрации (или \"-\" для пропуска):", reply_markup=get_routes_keyboard())


@router.message(RouteState.registration_number)
async def create_route_registration_number(message: types.Message, state: FSMContext):
    """Получение номера для регистрации, далее запрос номера прицепа"""
    registration_number = message.text.strip()
    if registration_number == "-":
        registration_number = ""
    await state.update_data(registration_number=registration_number)
    await state.set_state(RouteState.trailer_number)
    await message.reply("Введите номер прицепа (или \"-\" для пропуска):", reply_markup=get_routes_keyboard())


@router.message(RouteState.trailer_number)
async def create_route_trailer_or_contacts(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    """Обработка номера прицепа: либо переход к номеру рейса (ручной формат после ТС), либо создание рейса (после регистрации)."""
    trailer_number = message.text.strip().upper()
    if trailer_number == "-":
        trailer_number = ""
    
    data = await state.get_data()
    route_id = data.get("route_id")
    driver_tg_id = data.get("driver_tg_id")
    
    # Если route_id ещё не введён — это ввод прицепа после номера ТС в ручном формате
    if not route_id:
        await state.update_data(trailer_number=trailer_number)
        await state.set_state(RouteState.route_id)
        await message.reply("Введите номер рейса:", reply_markup=get_routes_keyboard())
        return
    
    # Иначе — финальный шаг ручного создания: создаём рейс (номер прицепа из текущего ввода или из state, если введён ранее)
    number_auto = data.get("number_auto", "")
    temperature = data.get("temperature", "")
    dispatcher_contacts = data.get("dispatcher_contacts", "")
    registration_number = data.get("registration_number", "")
    # В финальном шаге прицеп берём из текущего сообщения; если не введён — из state (ввод после ТС)
    trailer_final = trailer_number if trailer_number else data.get("trailer_number", "")
    
    await state.clear()
    
    if not driver_tg_id:
        await message.reply("❌ Не найдено состояние создания рейса. Попробуйте начать заново.", reply_markup=get_routes_keyboard())
        return
    
    route = route_repository.create(
        route_id,
        int(driver_tg_id),
        number_auto=number_auto,
        temperature=temperature,
        dispatcher_contacts=dispatcher_contacts,
        registration_number=registration_number,
        trailer_number=trailer_final,
    )
    
    if not route:
        await message.reply("❌ Ошибка при создании рейса", reply_markup=get_routes_keyboard())
        return
    
    await message.reply("✅ Рейс создан. Добавьте точки и нажмите «Сохранить и отправить водителю» для уведомления.", reply_markup=get_route_point_keyboard())


def _parse_onec_message(raw: str) -> tuple:
    """
    Парсит сообщение в формате 1С.
    Поддерживает: номер рейса в первой строке (00ДМ-000524), блоки Загр/Выгр с датой на строке и адресом на следующей;
    организация с двоеточием или без; «Диспетчер ...: тел» для контактов.
    Возвращает (parsed_dict, points_start_index).
    """
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    parsed = {
        "route_id": "",
        "registration_number": "",
        "driver_fio": "",
        "number_auto": "",
        "trailer_number": "",
        "temperature": "",
        "dispatcher_contacts": "",
    }
    points_start_idx = None

    for i, line in enumerate(lines):
        if line.lower().startswith("загр:") or line.lower().startswith("выгр:"):
            points_start_idx = i
            break
        if ":" in line:
            key, _, value = line.partition(":")
            key_lower = key.strip().lower()
            value = value.strip()
            if "номер для регистрации" in key_lower or "номер регистрации" in key_lower:
                parsed["registration_number"] = value
            elif "фио водителя" in key_lower:
                parsed["driver_fio"] = value
            elif "номер тс" in key_lower:
                parsed["number_auto"] = value
            elif "номер прицепа" in key_lower:
                parsed["trailer_number"] = (value or "").strip().upper()
            elif "температура" in key_lower:
                parsed["temperature"] = value
            elif "контакты" in key_lower or "диспетчер" in key_lower:
                parsed["dispatcher_contacts"] = value or line
        else:
            # Строка без ":" — первая такая считаем номером рейса (формат 00ДМ-000524 и т.п.)
            if not parsed["route_id"] and line:
                parsed["route_id"] = line

    return parsed, points_start_idx


def _validate_number_auto(text: str) -> bool:
    """Проверка формата номера ТС (как в заявке на ремонт)."""
    t = text.strip().upper()
    return bool(re.match(r'^[А-ЯA-Z]\d{3}[А-ЯA-Z]{2}\d{2,3}$', t) or re.match(r'^[А-ЯA-Z]{2}\d{6}$', t))


async def _onec_create_route_and_points(
    route_repository: RouteRepository,
    user_repository: UserRepository,
    parsed: dict,
    raw: str,
    points_start_idx,
    driver_tg_id: int,
) -> tuple:
    """Создаёт рейс и точки из распарсенных данных 1С. Возвращает (route, created_points)."""
    route_id = parsed["route_id"]
    number_auto = parsed.get("number_auto") or ""
    temperature = parsed.get("temperature") or ""
    dispatcher_contacts = parsed.get("dispatcher_contacts") or ""
    registration_number = parsed.get("registration_number") or ""
    trailer_number = parsed.get("trailer_number") or ""

    route = route_repository.create(
        route_id,
        int(driver_tg_id),
        number_auto=number_auto,
        temperature=temperature,
        dispatcher_contacts=dispatcher_contacts,
        registration_number=registration_number,
        trailer_number=trailer_number,
    )
    if not route:
        return None, 0

    created_points = 0
    if points_start_idx is not None and raw:
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        idx = points_start_idx
        while idx < len(lines):
            line = lines[idx]
            if line.lower().startswith("загр:") or line.lower().startswith("выгр:"):
                type_point = "loading" if line.lower().startswith("загр:") else "unloading"
                # Всё после первого ":" (после "Загр:" или "Выгр:")
                after_type = line.split(":", 1)[1].strip()
                after_lower = after_type.lower()
                date_time = ""
                place = ""
                
                # Ищем "организация" или "организация:" в той же строке
                pos_org = after_lower.find("организация:")
                if pos_org < 0:
                    pos_org = after_lower.find("организация ")
                if pos_org < 0:
                    pos_org = after_lower.find("организация")
                
                if pos_org >= 0:
                    # Дата/время и адрес на одной строке
                    date_time = after_type[:pos_org].strip()
                    org_part = after_type[pos_org:].strip()
                    if org_part.lower().startswith("организация:"):
                        place = org_part.split(":", 1)[1].strip()
                    else:
                        # Организация без двоеточия — всё после слова "Организация"
                        place = org_part[len("Организация"):].lstrip(" :").strip()
                else:
                    # Адрес на следующей строке
                    date_time = after_type
                    idx += 1
                    if idx >= len(lines):
                        break
                    org_line = lines[idx]
                    org_lower = org_line.lower()
                    if org_lower.startswith("организация"):
                        if org_lower.startswith("организация:"):
                            place = org_line.split(":", 1)[1].strip()
                        else:
                            place = org_line[len("Организация"):].lstrip(" :").strip()
                    else:
                        # Формат 1С без "Организация": следующая строка — просто адрес (Загр:/Выгр: дата, затем строка с адресом)
                        place = org_line
                
                # Убираем из адреса "Контакт" и всё после него (в т.ч. "Контакт:Ирина тел. ...")
                contact_pos = place.lower().find("контакт")
                if contact_pos >= 0:
                    place = place[:contact_pos].strip()
                
                # Очищаем адрес от лишних пробелов
                place = " ".join(place.split())
                
                if not date_time or not place:
                    idx += 1
                    continue
                    
                last_point_id = route_repository.get_last_point_id()
                point_id = last_point_id + 1 if last_point_id else 1
                points = route.points
                new_points = str(point_id) if points == "0" else f"{points},{point_id}"
                route_repository.add_point_to_route(route.id, new_points)
                route_repository.create_point(
                    point_id=point_id,
                    route_id=route.id,
                    type_point=type_point,
                    date_point=date_time,
                    place_point=place,
                )
                route = route_repository.get_by_id_str(route.id) or route
                created_points += 1
            idx += 1
    return route, created_points


@router.message(RouteState.onec_text)
async def create_route_from_onec(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    """Парсинг сообщения 1С; при недостающих данных — запрос после ввода (ФИО водителя, ТС и т.д.)."""
    raw = message.text or ""
    parsed, points_start_idx = _parse_onec_message(raw)

    route_id = parsed["route_id"]
    if not route_id:
        await message.reply("❌ В сообщении не найден номер рейса (первая строка или строка с номером).", reply_markup=get_routes_keyboard())
        return

    if route_repository.route_id_exists(route_id):
        await state.clear()
        await message.reply("❌ Рейс с таким номером уже существует", reply_markup=get_routes_keyboard())
        return

    # Определяем водителя по ФИО из 1С
    driver_tg_id = None
    if parsed["driver_fio"]:
        user = user_repository.get_by_name(parsed["driver_fio"])
        if user and user.tg_id and user.tg_id != "0":
            driver_tg_id = user.tg_id

    # Недостающие данные до создания рейса (запросим по очереди)
    missing_before = []
    if not driver_tg_id:
        missing_before.append(("driver", "ФИО водителя", True))  # (key, name_ru, required)
    if not parsed["number_auto"]:
        missing_before.append(("number_auto", "номер ТС", False))

    if missing_before:
        await state.update_data(
            onec_phase="before",
            onec_parsed_data=parsed,
            onec_raw=raw,
            onec_points_start_idx=points_start_idx,
            onec_missing=missing_before,
            onec_missing_idx=0,
        )
        await state.set_state(OnecMissingParamState.value)
        name_ru = missing_before[0][1]
        required = missing_before[0][2]
        hint = " (обязательно)" if required else " (или «-» чтобы пропустить)"
        driver_hint = " Можно ввести часть ФИО для поиска." if name_ru == "ФИО водителя" else ""
        await message.reply(
            f"В сообщении 1С не найден параметр: «{name_ru}». Введите значение{hint}.{driver_hint}",
            reply_markup=get_routes_keyboard(),
        )
        return

    # Всё есть — создаём рейс и точки
    route, created_points = await _onec_create_route_and_points(
        route_repository, user_repository, parsed, raw, points_start_idx, driver_tg_id,
    )
    if not route:
        await state.clear()
        await message.reply("❌ Ошибка при создании рейса по формату 1С", reply_markup=get_routes_keyboard())
        return

    registration_number = parsed.get("registration_number") or ""
    trailer_number = parsed.get("trailer_number") or ""
    missing_after = []
    if not registration_number:
        missing_after.append(("registration_number", "номер для регистрации"))
    if not trailer_number:
        missing_after.append(("trailer_number", "номер прицепа"))

    if missing_after:
        await state.update_data(
            onec_phase="after",
            onec_route_id=route.id,
            onec_missing=missing_after,
            onec_missing_idx=0,
        )
        await state.set_state(OnecMissingParamState.value)
        await message.reply(
            f"✅ Рейс создан. Точек: {created_points}.\n\n"
            f"Не указан параметр: «{missing_after[0][1]}». Введите значение или «-» чтобы пропустить:",
            reply_markup=get_routes_keyboard(),
        )
        return

    await state.clear()
    if created_points > 0:
        await _notify_driver_about_new_route(route, route_repository, user_repository, create_bot())
    driver = user_repository.get_by_tg_id(int(driver_tg_id))
    driver_name = driver.name if driver else "Неизвестно"
    summary = (
        f"✅ Рейс создан по формату 1С.\n\n"
        f"Рейс: {route.id}\n"
        f"👤 Водитель: {copy_link_fio(driver_name)}\n"
    )
    if route.number_auto:
        summary += f"🚚 ТС: {html.escape(route.number_auto)}\n"
    if getattr(route, 'trailer_number', None):
        summary += f"🛞 Прицеп: {html.escape(route.trailer_number)}\n"
    if route.temperature:
        summary += f"🌡 Температура: {html.escape(route.temperature)}\n"
    if route.dispatcher_contacts:
        summary += f"☎ Контакты: {html.escape(route.dispatcher_contacts)}\n"
    if getattr(route, 'registration_number', None):
        summary += f"📋 N регистрации: {html.escape(route.registration_number)}\n"
    summary += "\nТочек создано: {}".format(created_points)
    await message.reply(summary, reply_markup=get_routes_keyboard(), parse_mode="HTML")


@router.message(OnecMissingParamState.value)
async def onec_missing_param_value(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    """Обработка введённого значения недостающего параметра 1С (до или после создания рейса)."""
    value = message.text.strip()
    data = await state.get_data()
    phase = data.get("onec_phase", "after")
    missing = data.get("onec_missing", [])
    idx = data.get("onec_missing_idx", 0)

    if idx >= len(missing):
        await state.clear()
        await message.reply("Готово.", reply_markup=get_routes_keyboard())
        return

    param_key, param_name_ru = missing[idx][0], missing[idx][1]
    required = missing[idx][2] if len(missing[idx]) > 2 else False

    if phase == "before":
        # Недостающие данные до создания рейса: ФИО водителя, номер ТС
        parsed = data.get("onec_parsed_data", {})
        if param_key == "driver":
            if value == "-" and required:
                await message.reply("ФИО водителя обязательно. Введите ФИО водителя (или часть ФИО для поиска):", reply_markup=get_routes_keyboard())
                return
            if value != "-":
                # Облегчённый поиск: по части ФИО
                users = user_repository.search_drivers_by_name_part(value, limit=15)
                if not users:
                    await message.reply("❌ Водители не найдены. Введите ФИО или часть ФИО.", reply_markup=get_routes_keyboard())
                    return
                if len(users) == 1:
                    u = users[0]
                    if not u.tg_id or str(u.tg_id) == "0":
                        await message.reply("❌ Найденный водитель не активирован в боте.", reply_markup=get_routes_keyboard())
                        return
                    parsed["driver_tg_id"] = int(u.tg_id)
                else:
                    # Несколько кандидатов — показываем выбор по tg_id
                    builder = InlineKeyboardBuilder()
                    for u in users[:10]:
                        if u.tg_id and str(u.tg_id) != "0":
                            builder.row(types.InlineKeyboardButton(text=u.name, callback_data=f"onec_driver_{u.tg_id}"))
                    await state.update_data(onec_parsed_data=parsed, onec_wait_driver_choice=True)
                    await message.reply("Выберите водителя:", reply_markup=builder.as_markup())
                    return
            else:
                await message.reply("Рейс нельзя создать без водителя. Введите ФИО водителя (или часть ФИО для поиска):", reply_markup=get_routes_keyboard())
                return
        elif param_key == "number_auto":
            if value == "-":
                value = ""
            else:
                if not _validate_number_auto(value):
                    await message.reply(
                        "❌ Неверный формат номера ТС. Примеры: А123ВС456, ЕН068477. Введите снова или «-» чтобы пропустить:",
                        reply_markup=get_routes_keyboard(),
                    )
                    return
                value = value.strip().upper()
            parsed["number_auto"] = value

        await state.update_data(onec_parsed_data=parsed, onec_missing_idx=idx + 1)
        next_idx = idx + 1

        if next_idx >= len(missing):
            # Все «до» собраны — создаём рейс
            driver_tg_id = parsed.get("driver_tg_id")
            if not driver_tg_id:
                await state.clear()
                await message.reply("❌ Водитель не указан. Начните создание рейса заново.", reply_markup=get_routes_keyboard())
                return
            raw = data.get("onec_raw", "")
            points_start_idx = data.get("onec_points_start_idx")
            route, created_points = await _onec_create_route_and_points(
                route_repository, user_repository, parsed, raw, points_start_idx, driver_tg_id,
            )
            if not route:
                await state.clear()
                await message.reply("❌ Ошибка при создании рейса.", reply_markup=get_routes_keyboard())
                return

            registration_number = parsed.get("registration_number") or ""
            trailer_number = parsed.get("trailer_number") or ""
            missing_after = []
            if not registration_number:
                missing_after.append(("registration_number", "номер для регистрации"))
            if not trailer_number:
                missing_after.append(("trailer_number", "номер прицепа"))

            if missing_after:
                await state.update_data(
                    onec_phase="after",
                    onec_route_id=route.id,
                    onec_missing=missing_after,
                    onec_missing_idx=0,
                )
                await message.reply(
                    f"✅ Рейс создан. Точек: {created_points}.\n\n"
                    f"Не указан параметр: «{missing_after[0][1]}». Введите значение или «-» чтобы пропустить:",
                    reply_markup=get_routes_keyboard(),
                )
            else:
                await state.clear()
                if created_points > 0:
                    await _notify_driver_about_new_route(route, route_repository, user_repository, create_bot())
                driver = user_repository.get_by_tg_id(int(driver_tg_id))
                driver_name = driver.name if driver else "Неизвестно"
                summary = f"✅ Рейс создан по формату 1С.\n\nРейс: {route.id}\n👤 Водитель: {copy_link_fio(driver_name)}\n"
                if route.number_auto:
                    summary += f"🚚 ТС: {html.escape(route.number_auto)}\n"
                if getattr(route, 'trailer_number', None):
                    summary += f"🛞 Прицеп: {html.escape(route.trailer_number)}\n"
                if route.temperature:
                    summary += f"🌡 Температура: {html.escape(route.temperature)}\n"
                if route.dispatcher_contacts:
                    summary += f"☎ Контакты: {html.escape(route.dispatcher_contacts)}\n"
                if getattr(route, 'registration_number', None):
                    summary += f"📋 N регистрации: {html.escape(route.registration_number)}\n"
                summary += "\nТочек создано: {}".format(created_points)
                await message.reply(summary, reply_markup=get_routes_keyboard(), parse_mode="HTML")
        else:
            next_name_ru = missing[next_idx][1]
            next_required = missing[next_idx][2] if len(missing[next_idx]) > 2 else False
            hint = " (обязательно)" if next_required else " (или «-» чтобы пропустить)"
            await message.reply(
                f"Принято. Следующий параметр: «{next_name_ru}». Введите значение{hint}:",
                reply_markup=get_routes_keyboard(),
            )
        return

    # Фаза "after" — обновление полей рейса (номер для регистрации, прицеп)
    route_id = data.get("onec_route_id")
    if value == "-":
        value = ""
    if param_key == "trailer_number" and value:
        value = value.strip().upper()
    if param_key == "registration_number":
        route_repository.update_route_extra(route_id, registration_number=value, trailer_number=None)
    elif param_key == "trailer_number":
        route_repository.update_route_extra(route_id, registration_number=None, trailer_number=value)

    next_idx = idx + 1
    if next_idx >= len(missing):
        await state.clear()
        route = route_repository.get_by_id_str(route_id)
        if route:
            await _notify_driver_about_new_route(route, route_repository, user_repository, create_bot())
        await message.reply(
            "✅ Все недостающие параметры учтены. Рейс сохранён, водителю отправлено уведомление.",
            reply_markup=get_routes_keyboard(),
        )
        return

    await state.update_data(onec_missing_idx=next_idx)
    next_name_ru = missing[next_idx][1]
    await message.reply(
        f"Принято. Следующий параметр: «{next_name_ru}». Введите значение или «-» чтобы пропустить:",
        reply_markup=get_routes_keyboard(),
    )


@router.callback_query(F.data.startswith("onec_driver_"))
async def onec_driver_selected(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    """Выбор водителя из списка при облегчённом поиске ФИО в формате 1С."""
    try:
        tg_id = int(callback.data.replace("onec_driver_", ""))
    except ValueError:
        await callback.answer("Ошибка.")
        return
    user = user_repository.get_by_tg_id(tg_id)
    if not user or not user.tg_id or str(user.tg_id) == "0":
        await callback.answer("Водитель не найден или не активирован.")
        return
    data = await state.get_data()
    if not data.get("onec_wait_driver_choice"):
        await callback.answer("Сессия устарела.")
        return
    parsed = data.get("onec_parsed_data", {})
    missing = data.get("onec_missing", [])
    idx = data.get("onec_missing_idx", 0)
    parsed["driver_tg_id"] = int(user.tg_id)
    next_idx = idx + 1
    await state.update_data(onec_parsed_data=parsed, onec_missing_idx=next_idx, onec_wait_driver_choice=None)

    if next_idx >= len(missing):
        driver_tg_id = parsed.get("driver_tg_id")
        raw = data.get("onec_raw", "")
        points_start_idx = data.get("onec_points_start_idx")
        route, created_points = await _onec_create_route_and_points(
            route_repository, user_repository, parsed, raw, points_start_idx, driver_tg_id,
        )
        if not route:
            await state.clear()
            await callback.message.edit_text("❌ Ошибка при создании рейса.")
            await callback.answer()
            return
        registration_number = parsed.get("registration_number") or ""
        trailer_number = parsed.get("trailer_number") or ""
        missing_after = []
        if not registration_number:
            missing_after.append(("registration_number", "номер для регистрации"))
        if not trailer_number:
            missing_after.append(("trailer_number", "номер прицепа"))
        if missing_after:
            await state.update_data(
                onec_phase="after",
                onec_route_id=route.id,
                onec_missing=missing_after,
                onec_missing_idx=0,
            )
            await callback.message.edit_text(
                f"✅ Водитель выбран. Рейс создан. Точек: {created_points}.\n\n"
                f"Не указан параметр: «{missing_after[0][1]}». Введите значение или «-» чтобы пропустить:"
            )
        else:
            await state.clear()
            if created_points > 0:
                await _notify_driver_about_new_route(route, route_repository, user_repository, create_bot())
            driver = user_repository.get_by_tg_id(int(driver_tg_id))
            driver_name = driver.name if driver else "Неизвестно"
            summary = (
                f"✅ Рейс создан по формату 1С.\n\n"
                f"Рейс: {route.id}\n"
                f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            )
            if route.number_auto:
                summary += f"🚚 ТС: {html.escape(route.number_auto)}\n"
            if getattr(route, 'trailer_number', None):
                summary += f"🛞 Прицеп: {html.escape(route.trailer_number)}\n"
            if route.temperature:
                summary += f"🌡 Температура: {html.escape(route.temperature)}\n"
            if route.dispatcher_contacts:
                summary += f"☎ Контакты: {html.escape(route.dispatcher_contacts)}\n"
            if getattr(route, 'registration_number', None):
                summary += f"📋 N регистрации: {html.escape(route.registration_number)}\n"
            summary += "\nТочек создано: {}".format(created_points)
            await callback.message.edit_text(summary, parse_mode="HTML")
    else:
        next_name_ru = missing[next_idx][1]
        next_required = missing[next_idx][2] if len(missing[next_idx]) > 2 else False
        hint = " (обязательно)" if next_required else " (или «-» чтобы пропустить)"
        await callback.message.edit_text(
            f"Водитель выбран. Следующий параметр: «{next_name_ru}». Введите значение{hint}:"
        )
    await callback.answer()


@router.callback_query(F.data == "point_add")
async def add_point(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PointState.type_point)
    await callback.message.answer("Выберите тип точки", reply_markup=get_point_type_keyboard())

@router.callback_query(F.data == "loading")
async def add_loading_point(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(type_point="loading")
    await state.set_state(PointState.date_point)
    await callback.message.answer("Введите дату загрузки")

@router.callback_query(F.data == "unloading")
async def add_unloading_point(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(type_point="unloading")
    await state.set_state(PointState.date_point)
    await callback.message.answer("Введите дату выгрузки")

@router.message(PointState.date_point)
async def get_point_date(message: types.Message, state: FSMContext):
    await state.update_data(date_point=message.text)
    await state.set_state(PointState.place_point)
    await message.reply("Введите место загрузки / выгрузки")

@router.message(PointState.place_point)
async def get_point_place(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository
):
    await state.update_data(place_point=message.text)
    data = await state.get_data()
    
    # Используем ID рейса из состояния, а не последний рейс
    route_id = data.get("created_route_id")
    
    if not route_id:
        # Если нет в состоянии, пытаемся получить последний рейс
        route = route_repository.get_last_route()
        if route:
            route_id = route.id
            await state.update_data(created_route_id=route_id)
        else:
            await message.reply("❌ Рейс не найден. Сначала создайте рейс.")
            await state.clear()
            return
    
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await message.reply("❌ Рейс не найден")
        await state.clear()
        return
    
    # Генерируем ID для новой точки (используем последний ID + 1)
    last_point_id = route_repository.get_last_point_id()
    point_id = last_point_id + 1 if last_point_id else 1
    
    # Обновляем точки маршрута
    points = route.points
    if points == "0":
        new_points = str(point_id)
    else:
        new_points = f"{points},{point_id}"
    
    # Обновляем маршрут с новыми точками
    success = route_repository.add_point_to_route(route.id, new_points)
    
    if not success:
        await message.reply("❌ Ошибка при обновлении точек маршрута")
        await state.clear()
        return
    
    # Создаем точку
    point = route_repository.create_point(
        point_id=point_id,
        route_id=route.id,
        type_point=data["type_point"],
        date_point=data["date_point"],
        place_point=data["place_point"]
    )
    
    if point:
        type_text = "Загрузка" if data["type_point"] == "loading" else "Выгрузка"
        type_emoji = "📦" if data["type_point"] == "loading" else "📤"
        await message.reply(
            f"✅ Точка добавлена!\n\n"
            f"{type_emoji} Тип: {type_text}\n"
            f"📅 Дата: {data['date_point']}\n"
            f"📍 Место: {data['place_point']}\n\n"
            f"Выберите действие:",
            reply_markup=get_route_point_keyboard()
        )
    else:
        # Даже если метод возвращает None, точка могла быть создана
        # Проверяем, есть ли точки у маршрута
        updated_route = route_repository.get_by_id_str(route_id)
        if updated_route and updated_route.points != "0":
            type_text = "Загрузка" if data["type_point"] == "loading" else "Выгрузка"
            type_emoji = "📦" if data["type_point"] == "loading" else "📤"
            await message.reply(
                f"✅ Точка добавлена!\n\n"
                f"{type_emoji} Тип: {type_text}\n"
                f"📅 Дата: {data['date_point']}\n"
                f"📍 Место: {data['place_point']}\n\n"
                f"Выберите действие:",
                reply_markup=get_route_point_keyboard()
            )
        else:
            await message.reply("❌ Ошибка при создании точки")
    
    await state.clear()

# handlers/admin/routes.py (добавляем в функцию save_route)

@router.callback_query(F.data == "save_route")
async def save_route(
    callback: types.CallbackQuery,
    route_repository: RouteRepository,
    user_repository: UserRepository
):
    # Получаем последний созданный рейс для текущего водителя
    route = route_repository.get_last_route()
    if not route:
        await callback.message.answer("❌ Рейс не найден")
        return
    
    # Отправляем уведомление водителю с использованием общей функции
    await _notify_driver_about_new_route(
        route,
        route_repository,
        user_repository,
        create_bot(),
    )
    
    await callback.message.answer("✅ Рейс успешно сохранен и отправлен водителю")

@router.message(F.text == "🚚 Все рейсы")
async def show_all_routes(
    message: types.Message,
    route_repository: RouteRepository,
    user_repository: UserRepository
):
    routes = route_repository.get_all()
    
    if not routes:
        await message.reply("📭 Нет созданных рейсов")
        return

    async def _send(text: str, reply_markup=None, **kwargs):
        await message.reply(text, reply_markup=reply_markup, **kwargs)
    await _send_routes_paginated(_send, routes, "📊 Все рейсы", route_repository, user_repository)


def _get_filter_status_inline_keyboard(status: str):
    """Инлайн-меню после выбора статуса: Все, По водителю, По номеру рейса, По ТС."""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📋 Все", callback_data=f"routes_filter_all_{status}"),
    )
    builder.row(
        types.InlineKeyboardButton(text="👤 По водителю", callback_data=f"routes_filter_driver_{status}"),
        types.InlineKeyboardButton(text="🔢 По номеру рейса", callback_data=f"routes_filter_route_{status}"),
    )
    builder.row(
        types.InlineKeyboardButton(text="🚚 По ТС", callback_data=f"routes_filter_auto_{status}"),
    )
    return builder.as_markup()


@router.message(F.text == "📋 Не принятые")
async def show_new_routes(
    message: types.Message,
    state: FSMContext,
):
    status_titles = {"new": "Не принятые", "process": "В процессе", "success": "Завершённые", "cancelled": "Отменённые"}
    await state.set_state(AdminRouteFilterByState.filter_status)
    await state.update_data(filter_status="new")
    await message.reply(
        f"Рейсы: {status_titles.get('new', 'Не принятые')}. Выберите способ отображения:",
        reply_markup=_get_filter_status_inline_keyboard("new"),
    )


@router.message(F.text == "🚚 В процессе")
async def show_process_routes(
    message: types.Message,
    state: FSMContext,
):
    status_titles = {"new": "Не принятые", "process": "В процессе", "success": "Завершённые", "cancelled": "Отменённые"}
    await state.set_state(AdminRouteFilterByState.filter_status)
    await state.update_data(filter_status="process")
    await message.reply(
        f"Рейсы: {status_titles.get('process', 'В процессе')}. Выберите способ отображения:",
        reply_markup=_get_filter_status_inline_keyboard("process"),
    )


@router.message(F.text == "✅ Завершенные")
async def show_success_routes_start(
    message: types.Message,
    state: FSMContext,
):
    await state.set_state(AdminRouteFilterByState.filter_status)
    await state.update_data(filter_status="success")
    await message.reply(
        "Рейсы: Завершённые. Выберите способ отображения:",
        reply_markup=_get_filter_status_inline_keyboard("success"),
    )


@router.callback_query(F.data.startswith("routes_filter_all_"))
async def routes_filter_all_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    status = callback.data.replace("routes_filter_all_", "")
    await state.clear()
    if status not in ("new", "process", "success", "cancelled"):
        await callback.answer("Неизвестный статус.")
        return
    if status == "success":
        await state.set_state(AdminRouteCompletedPeriodState.period_type)
        await callback.message.edit_text("Выберите период отображения завершённых рейсов:")
        await callback.message.answer(
            "Выберите период:",
            reply_markup=get_admin_completed_routes_period_keyboard(),
        )
        await callback.answer()
        return
    routes = route_repository.get_routes_by_status(status)
    status_titles = {"new": "📋 Не принятые рейсы", "process": "🚚 Рейсы в процессе", "cancelled": "❌ Отменённые рейсы"}
    title = status_titles.get(status, status)
    if not routes:
        await callback.message.edit_text(f"📭 Нет рейсов с таким статусом.")
        await callback.answer()
        return
    async def _send(text: str, reply_markup=None, **kwargs):
        await callback.message.answer(text, reply_markup=reply_markup, **kwargs)
    await _send_routes_paginated(_send, routes, title, route_repository, user_repository, reply_markup=get_routes_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("routes_filter_driver_select_"))
async def routes_filter_driver_select_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    """Выбор водителя из списка совпадений при фильтре по статусу (инлайн-кнопки)."""
    data = await state.get_data()
    status = data.get("filter_status")
    if status not in ("new", "process", "success", "cancelled"):
        await state.clear()
        await callback.message.answer("❌ Сессия истекла. Выберите статус рейсов заново.", reply_markup=get_routes_keyboard())
        await callback.answer()
        return
    tg_id_str = callback.data.replace("routes_filter_driver_select_", "")
    try:
        tg_id = int(tg_id_str)
    except ValueError:
        await callback.answer("Ошибка.")
        return
    user = user_repository.get_by_tg_id(tg_id)
    if not user or not user.tg_id or str(user.tg_id) == "0":
        await callback.answer("Водитель не найден или не активирован.")
        return
    await state.clear()
    routes = route_repository.get_routes_by_driver(tg_id, status)
    status_titles = {"new": "Не принятые", "process": "В процессе", "success": "Завершённые", "cancelled": "Отменённые"}
    title = f"Рейсы водителя {user.name} ({status_titles.get(status, status)})"
    if not routes:
        await callback.message.answer(
            f"📭 Нет рейсов с выбранным статусом у водителя {user.name}.",
            reply_markup=get_routes_keyboard(),
        )
        await callback.answer()
        return
    async def _send(t: str, reply_markup=None, **kwargs):
        await callback.message.answer(t, reply_markup=reply_markup, **kwargs)
    await _send_routes_paginated(_send, routes, title, route_repository, user_repository, reply_markup=get_routes_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("routes_filter_driver_"))
async def routes_filter_driver_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    status = callback.data.replace("routes_filter_driver_", "")
    if status not in ("new", "process", "success", "cancelled"):
        await callback.answer("Неизвестный статус.")
        return
    await state.update_data(filter_status=status)
    await state.set_state(AdminRouteFilterByState.driver_fio)
    await callback.message.edit_text("Введите ФИО водителя (или часть ФИО):")
    await callback.answer()


@router.callback_query(F.data.startswith("routes_filter_route_"))
async def routes_filter_route_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    status = callback.data.replace("routes_filter_route_", "")
    if status not in ("new", "process", "success", "cancelled"):
        await callback.answer("Неизвестный статус.")
        return
    await state.update_data(filter_status=status)
    await state.set_state(AdminRouteFilterByState.route_id)
    await callback.message.edit_text("Введите номер рейса:")
    await callback.answer()


@router.callback_query(F.data.startswith("routes_filter_auto_"))
async def routes_filter_auto_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    status = callback.data.replace("routes_filter_auto_", "")
    if status not in ("new", "process", "success", "cancelled"):
        await callback.answer("Неизвестный статус.")
        return
    await state.update_data(filter_status=status)
    await state.set_state(AdminRouteFilterByState.number_auto)
    await callback.message.edit_text("Введите номер ТС:")
    await callback.answer()


@router.message(AdminRouteFilterByState.driver_fio)
async def routes_filter_driver_entered(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    data = await state.get_data()
    status = data.get("filter_status")
    text = message.text.strip()
    users = user_repository.search_drivers_by_name_part(text, limit=15)
    if not users:
        await message.reply("Водители не найдены. Введите ФИО или часть ФИО:", reply_markup=get_routes_keyboard())
        return
    if len(users) > 1:
        builder = InlineKeyboardBuilder()
        for u in users[:15]:
            if u.tg_id and str(u.tg_id) != "0":
                builder.row(
                    types.InlineKeyboardButton(text=u.name, callback_data=f"routes_filter_driver_select_{u.tg_id}"),
                )
        await message.reply("Выберите водителя:", reply_markup=builder.as_markup())
        return
    u = users[0]
    if not u.tg_id or str(u.tg_id) == "0":
        await state.clear()
        await message.reply("Водитель не активирован в боте.", reply_markup=get_routes_keyboard())
        return
    await state.clear()
    routes = route_repository.get_routes_by_driver(int(u.tg_id), status)
    status_titles = {"new": "Не принятые", "process": "В процессе", "success": "Завершённые", "cancelled": "Отменённые"}
    title = f"Рейсы водителя {u.name} ({status_titles.get(status, status)})"
    if not routes:
        await message.reply(f"📭 Нет рейсов с выбранным статусом у водителя {u.name}.", reply_markup=get_routes_keyboard(), parse_mode="HTML")
        return
    async def _send(t: str, reply_markup=None, **kwargs):
        await message.reply(t, reply_markup=reply_markup, **kwargs)
    await _send_routes_paginated(_send, routes, title, route_repository, user_repository, reply_markup=get_routes_keyboard())


@router.message(AdminRouteFilterByState.route_id)
async def routes_filter_route_entered(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    data = await state.get_data()
    status = data.get("filter_status")
    route_id = message.text.strip()
    await state.clear()
    route = route_repository.get_by_id_str(route_id)
    if not route or route.status != status:
        await message.reply("Рейс не найден или его статус не совпадает с выбранным.", reply_markup=get_routes_keyboard())
        return
    async def _send(t: str, reply_markup=None, **kwargs):
        await message.reply(t, reply_markup=reply_markup, **kwargs)
    await _send_routes_paginated(_send, [route], f"Рейс {route_id}", route_repository, user_repository, reply_markup=get_routes_keyboard())


@router.message(AdminRouteFilterByState.number_auto)
async def routes_filter_auto_entered(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    data = await state.get_data()
    status = data.get("filter_status")
    number_auto = message.text.strip()
    await state.clear()
    routes = route_repository.get_routes_by_number_auto(number_auto, status)
    status_titles = {"new": "Не принятые", "process": "В процессе", "success": "Завершённые", "cancelled": "Отменённые"}
    title = f"Рейсы ТС {number_auto} ({status_titles.get(status, status)})"
    if not routes:
        await message.reply(f"📭 Нет рейсов с таким статусом по ТС {number_auto}.", reply_markup=get_routes_keyboard())
        return
    async def _send(t: str, reply_markup=None, **kwargs):
        await message.reply(t, reply_markup=reply_markup, **kwargs)
    await _send_routes_paginated(_send, routes, title, route_repository, user_repository, reply_markup=get_routes_keyboard())


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(AdminRouteFilterByState))
async def back_from_filter_status(message: types.Message, state: FSMContext):
    await state.clear()
    await message.reply("Выбор отменён.", reply_markup=get_routes_keyboard())


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(AdminRouteCompletedPeriodState))
async def back_from_completed_period(message: types.Message, state: FSMContext):
    """Выход назад при выборе периода завершённых рейсов (должен быть зарегистрирован до обработчиков ввода даты/месяца)."""
    current = await state.get_state() or ""
    if "period_type" in current and current.endswith("period_type"):
        await state.clear()
        await message.reply("Выбор периода отменён.", reply_markup=get_routes_keyboard())
    else:
        await state.set_state(AdminRouteCompletedPeriodState.period_type)
        await message.reply(
            "Выберите период отображения завершённых рейсов:",
            reply_markup=get_admin_completed_routes_period_keyboard(),
        )


async def _send_completed_routes_for_period(message, route_repository, user_repository, start_date_str, end_date_str, period_info):
    routes = route_repository.get_routes_success_in_period(start_date_str, end_date_str)
    if not routes:
        await message.reply(f"📭 Нет завершённых рейсов за период: {period_info}", reply_markup=get_routes_keyboard())
        return
    async def _send(text: str, reply_markup=None, **kwargs):
        await message.reply(text, reply_markup=reply_markup, **kwargs)
    await _send_routes_paginated(_send, routes, f"✅ Завершенные рейсы ({period_info})", route_repository, user_repository, reply_markup=get_routes_keyboard())


@router.message(AdminRouteCompletedPeriodState.period_type)
async def show_success_routes_period_type(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    period_type = message.text
    today = datetime.now()
    if period_type == "📅 За день":
        await state.set_state(AdminRouteCompletedPeriodState.date_day)
        await message.reply(
            "Введите дату (дд.мм.гггг), например 22.02.2026:\n\nИли нажмите «↩️ Назад» для возврата.",
            reply_markup=get_routes_keyboard(),
        )
        return
    if period_type == "📊 С начала месяца":
        start_date = today.replace(day=1)
        start_date_str = start_date.strftime("%d.%m.%Y")
        end_date_str = today.strftime("%d.%m.%Y")
        await state.clear()
        await _send_completed_routes_for_period(
            message, route_repository, user_repository,
            start_date_str, end_date_str,
            f"с начала месяца ({start_date_str} - {end_date_str})",
        )
        return
    if period_type == "📋 Выбрать месяц":
        await state.set_state(AdminRouteCompletedPeriodState.month_year)
        await message.reply("Выберите месяц:", reply_markup=get_admin_months_keyboard())
        return
    if period_type == "📑 Произвольный период":
        await state.set_state(AdminRouteCompletedPeriodState.custom_start)
        await message.reply(
            "Введите начальную дату периода (дд.мм.гггг):\n\nИли нажмите «↩️ Назад» для возврата.",
            reply_markup=get_routes_keyboard(),
        )
        return
    await message.reply("Выберите вариант из меню.", reply_markup=get_admin_completed_routes_period_keyboard())


@router.message(AdminRouteCompletedPeriodState.date_day)
async def show_success_routes_date_day(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        date_str = dt.strftime("%d.%m.%Y")
    except ValueError:
        await message.reply("Неверный формат. Введите дату дд.мм.гггг:", reply_markup=get_routes_keyboard())
        return
    await state.clear()
    await _send_completed_routes_for_period(message, route_repository, user_repository, date_str, date_str, date_str)


@router.message(AdminRouteCompletedPeriodState.month_year)
async def show_success_routes_month(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    month_names = {
        "Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4,
        "Май": 5, "Июнь": 6, "Июль": 7, "Август": 8,
        "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12,
    }
    if message.text not in month_names:
        await message.reply("Выберите месяц из списка.", reply_markup=get_admin_months_keyboard())
        return
    month_num = month_names[message.text]
    year = datetime.now().year
    start_date = datetime(year, month_num, 1)
    start_date_str = start_date.strftime("%d.%m.%Y")
    last_day = calendar.monthrange(year, month_num)[1]
    end_date = datetime(year, month_num, last_day)
    end_date_str = end_date.strftime("%d.%m.%Y")
    await state.clear()
    await _send_completed_routes_for_period(
        message, route_repository, user_repository,
        start_date_str, end_date_str,
        f"за {message.text.lower()} {year} года",
    )


@router.message(AdminRouteCompletedPeriodState.custom_start)
async def show_success_routes_custom_start(
    message: types.Message,
    state: FSMContext,
):
    try:
        datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.reply("Неверный формат. Введите начальную дату (дд.мм.гггг):", reply_markup=get_routes_keyboard())
        return
    await state.update_data(completed_period_start=message.text.strip())
    await state.set_state(AdminRouteCompletedPeriodState.custom_end)
    await message.reply("Введите конечную дату периода (дд.мм.гггг):", reply_markup=get_routes_keyboard())


@router.message(AdminRouteCompletedPeriodState.custom_end)
async def show_success_routes_custom_end(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    try:
        datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.reply("Неверный формат. Введите конечную дату (дд.мм.гггг):", reply_markup=get_routes_keyboard())
        return
    data = await state.get_data()
    start_str = data.get("completed_period_start", "")
    end_str = message.text.strip()
    await state.clear()
    await _send_completed_routes_for_period(
        message, route_repository, user_repository,
        start_str, end_str,
        f"с {start_str} по {end_str}",
    )


def _get_search_status_inline_keyboard(prefix: str):
    """Инлайн-меню выбора статуса рейсов для поиска (Все, Не приняты, В процессе, Завершены)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="Все", callback_data=f"{prefix}_all"),
        types.InlineKeyboardButton(text="Не приняты", callback_data=f"{prefix}_new"),
    )
    builder.row(
        types.InlineKeyboardButton(text="В процессе", callback_data=f"{prefix}_process"),
        types.InlineKeyboardButton(text="Завершены", callback_data=f"{prefix}_success"),
    )
    return builder.as_markup()


@router.message(F.text == "🔍 Рейсы по водителю")
async def search_routes_by_driver_start(message: types.Message, state: FSMContext):
    await state.set_state(AdminRouteSearchState.driver)
    await message.reply(
        "👤 Введите ФИО водителя для поиска рейсов:",
        reply_markup=get_routes_keyboard(),
    )


@router.message(AdminRouteSearchState.driver)
async def search_routes_by_driver_process(
    message: types.Message,
    state: FSMContext,
    user_repository: UserRepository,
    route_repository: RouteRepository,
):
    text = message.text.strip()
    # Всегда ищем по части ФИО и при нескольких — показываем выбор по tg_id
    users = user_repository.search_drivers_by_name_part(text, limit=15)
    if not users:
        await state.clear()
        await message.reply("❌ Водители не найдены. Введите ФИО или часть ФИО.", reply_markup=get_routes_keyboard())
        return
    if len(users) == 1:
        u = users[0]
        if not u.tg_id or str(u.tg_id) == "0":
            await state.clear()
            await message.reply("❌ Найденный водитель не активирован в боте.", reply_markup=get_routes_keyboard())
            return
        await state.update_data(search_driver_tg_id=int(u.tg_id), search_driver_name=u.name)
        await message.reply(
            f"👤 Водитель: {copy_link_fio(u.name)}\nВыберите статус рейсов для отображения:",
            reply_markup=_get_search_status_inline_keyboard("search_driver"),
            parse_mode="HTML",
        )
        return
    builder = InlineKeyboardBuilder()
    for u in users[:10]:
        if u.tg_id and str(u.tg_id) != "0":
            builder.row(
                types.InlineKeyboardButton(text=u.name, callback_data=f"search_driver_select_{u.tg_id}"),
            )
    await message.reply("Выберите водителя:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("search_driver_select_"))
async def search_driver_select_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    user_repository: UserRepository,
):
    tg_id_str = callback.data.replace("search_driver_select_", "")
    try:
        new_tg_id = int(tg_id_str)
    except ValueError:
        await callback.answer("Ошибка.")
        return
    user = user_repository.get_by_tg_id(new_tg_id)
    if not user:
        await callback.answer("Водитель не найден.")
        return
    await state.update_data(search_driver_tg_id=new_tg_id, search_driver_name=user.name)
    await callback.message.edit_text(
        f"👤 Водитель: {copy_link_fio(user.name)}\nВыберите статус рейсов для отображения:",
        reply_markup=_get_search_status_inline_keyboard("search_driver"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("search_driver_"))
async def search_routes_by_driver_status(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    status_key = callback.data.replace("search_driver_", "")
    data = await state.get_data()
    driver_tg_id = data.get("search_driver_tg_id")
    driver_name = data.get("search_driver_name", "Водитель")
    await state.clear()

    if not driver_tg_id:
        await callback.message.answer("❌ Сессия поиска истекла. Запустите поиск заново.", reply_markup=get_routes_keyboard())
        await callback.answer()
        return

    if status_key == "all":
        routes = route_repository.get_routes_by_driver(driver_tg_id)
        title = f"🚚 Все рейсы водителя {driver_name}"
    else:
        routes = route_repository.get_routes_by_driver(driver_tg_id, status=status_key)
        status_titles = {"new": "Не принятые", "process": "В процессе", "success": "Завершённые"}
        title = f"🚚 Рейсы водителя {driver_name} ({status_titles.get(status_key, status_key)})"

    if not routes:
        await callback.message.answer(f"📭 Нет рейсов по выбранному критерию.", reply_markup=get_routes_keyboard())
    else:
        async def _send(text: str, reply_markup=None, **kwargs):
            await callback.message.answer(text, reply_markup=reply_markup, **kwargs)
        await _send_routes_paginated(
            _send, routes, title, route_repository, user_repository, reply_markup=get_routes_keyboard()
        )
    await callback.answer()


@router.message(F.text == "🔍 Рейсы по ТС")
async def search_routes_by_auto_start(message: types.Message, state: FSMContext):
    await state.set_state(AdminRouteSearchByAutoState.number_auto)
    await message.reply(
        "🚚 Введите номер ТС для поиска рейсов (например А344АА43 или ЕН068477):",
        reply_markup=get_routes_keyboard(),
    )


@router.message(AdminRouteSearchByAutoState.number_auto)
async def search_routes_by_auto_process(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
):
    number_auto = message.text.strip().upper()
    routes = route_repository.get_routes_by_number_auto(number_auto)
    if not routes:
        await state.clear()
        await message.reply(f"📭 Рейсов по ТС {number_auto} не найдено.", reply_markup=get_routes_keyboard())
        return
    await state.update_data(search_number_auto=number_auto)
    await message.reply(
        f"🚚 ТС: {number_auto}\nВыберите статус рейсов для отображения:",
        reply_markup=_get_search_status_inline_keyboard("search_auto"),
    )


@router.callback_query(F.data.startswith("search_auto_"))
async def search_routes_by_auto_status(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    status_key = callback.data.replace("search_auto_", "")
    data = await state.get_data()
    number_auto = data.get("search_number_auto", "")
    await state.clear()

    if not number_auto:
        await callback.message.answer("❌ Сессия поиска истекла. Запустите поиск заново.", reply_markup=get_routes_keyboard())
        await callback.answer()
        return

    if status_key == "all":
        routes = route_repository.get_routes_by_number_auto(number_auto)
        title = f"🚚 Все рейсы по ТС {number_auto}"
    else:
        routes = route_repository.get_routes_by_number_auto(number_auto, status=status_key)
        status_titles = {"new": "Не принятые", "process": "В процессе", "success": "Завершённые"}
        title = f"🚚 Рейсы по ТС {number_auto} ({status_titles.get(status_key, status_key)})"

    if not routes:
        await callback.message.answer(f"📭 Нет рейсов по выбранному критерию.", reply_markup=get_routes_keyboard())
    else:
        async def _send(text: str, reply_markup=None, **kwargs):
            await callback.message.answer(text, reply_markup=reply_markup, **kwargs)
        await _send_routes_paginated(
            _send, routes, title, route_repository, user_repository, reply_markup=get_routes_keyboard()
        )
    await callback.answer()


def _get_delete_route_keyboard(route_id: str):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="✅ Подтвердить удаление",
            callback_data=f"confirm_delete_route_{route_id}",
        ),
        types.InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="cancel_delete_route",
        ),
    )
    return builder.as_markup()


@router.message(F.text == "🗑️ Удалить рейс")
async def delete_route_start(message: types.Message, state: FSMContext):
    await state.set_state(AdminRouteDeleteState.route_id)
    await message.reply("Введите номер рейса для удаления:", reply_markup=get_routes_keyboard())


@router.message(AdminRouteDeleteState.route_id)
async def delete_route_get_id(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    route_id = message.text.strip()
    await state.clear()

    route = route_repository.get_route_info(route_id)
    if not route:
        await message.reply("❌ Рейс не найден", reply_markup=get_routes_keyboard())
        return

    # Показываем подробную информацию перед удалением (формат как в «Поиск по номеру рейса»)
    text = _build_route_detail_html(route, route_repository, user_repository)
    text += "\n\n❓ Подтвердить удаление этого рейса и всех его точек?"

    await message.reply(text, reply_markup=_get_delete_route_keyboard(route_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("confirm_delete_route_"))
async def confirm_delete_route_callback(
    callback: types.CallbackQuery,
    route_repository: RouteRepository,
):
    route_id = callback.data.split("_")[-1]
    success = route_repository.delete_route_with_points(route_id)

    if success:
        await callback.message.edit_text(f"✅ Рейс {route_id} и все его точки удалены.")
    else:
        await callback.message.edit_text(f"❌ Рейс {route_id} не найден или уже был удален.")

    await callback.answer()


@router.callback_query(F.data == "cancel_delete_route")
async def cancel_delete_route_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Удаление рейса отменено.")
    await callback.answer()


# --- Отмена рейса ---

def _get_cancel_route_keyboard(route_id: str):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="✅ Подтвердить отмену",
            callback_data=f"confirm_cancel_route_{route_id}",
        ),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_cancel_route"),
    )
    return builder.as_markup()


@router.message(F.text == "🚫 Отменить рейс")
async def cancel_route_start(
    message: types.Message,
    state: FSMContext,
    user_repository: UserRepository,
):
    user = user_repository.get_by_tg_id(message.from_user.id)
    if not user or user.role not in (UserRole.ADMIN, UserRole.LOGISTIC):
        await message.reply("❌ Доступ запрещён. Отмена рейса доступна только администратору и логисту.")
        return
    await state.set_state(AdminRouteCancelState.route_id)
    await message.reply("Введите номер рейса для отмены:", reply_markup=get_routes_keyboard())


@router.message(AdminRouteCancelState.route_id)
async def cancel_route_get_id(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    route_id = message.text.strip()
    await state.clear()
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await message.reply("❌ Рейс не найден.", reply_markup=get_routes_keyboard())
        return
    if route.status == "cancelled":
        await message.reply("❌ Рейс уже отменён.", reply_markup=get_routes_keyboard())
        return
    text = _build_route_detail_html(route, route_repository, user_repository)
    text += "\n\n❓ Отменить этот рейс? Водителю, логистам и администраторам будет отправлено уведомление."
    await message.reply(text, reply_markup=_get_cancel_route_keyboard(route_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("confirm_cancel_route_"))
async def confirm_cancel_route_callback(
    callback: types.CallbackQuery,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    route_id = callback.data.replace("confirm_cancel_route_", "")
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await callback.message.edit_text("❌ Рейс не найден.")
        await callback.answer()
        return
    ok = route_repository.update_status_route(route_id, "cancelled")
    if not ok:
        await callback.message.edit_text("❌ Не удалось отменить рейс.")
        await callback.answer()
        return
    from services.notification_service import NotificationService
    notifier = NotificationService(user_repository)
    await notifier.notify_route_cancelled(route_id, int(route.tg_id))
    await callback.message.edit_text("✅ Рейс {} отменён. Уведомления отправлены.".format(route_id))
    await callback.answer()


@router.callback_query(F.data == "cancel_cancel_route")
async def cancel_cancel_route_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Отмена рейса отменена.")
    await callback.answer()


# --- Переназначение рейса ---

def _get_reassign_route_confirm_keyboard(route_id: str, new_tg_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"confirm_reassign_route_{route_id}_{new_tg_id}",
        ),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_reassign_route"),
    )
    return builder.as_markup()


@router.message(F.text == "🔄 Переназначить рейс")
async def reassign_route_start(message: types.Message, state: FSMContext):
    await state.set_state(AdminRouteReassignState.route_id)
    await message.reply("Введите номер рейса для переназначения:", reply_markup=get_routes_keyboard())


@router.message(AdminRouteReassignState.route_id)
async def reassign_route_id_entered(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
):
    route_id = message.text.strip()
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await state.clear()
        await message.reply("❌ Рейс не найден.", reply_markup=get_routes_keyboard())
        return
    await state.update_data(reassign_route_id=route_id)
    await state.set_state(AdminRouteReassignState.driver_fio)
    await message.reply(
        "Введите ФИО водителя, на которого переназначить рейс (можно часть ФИО для поиска):",
        reply_markup=get_routes_keyboard(),
    )


@router.message(AdminRouteReassignState.driver_fio)
async def reassign_route_driver_entered(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    text = message.text.strip()
    data = await state.get_data()
    route_id = data.get("reassign_route_id")
    if not route_id:
        await state.clear()
        await message.reply("Сессия истекла. Начните заново.", reply_markup=get_routes_keyboard())
        return
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await state.clear()
        await message.reply("Рейс не найден.", reply_markup=get_routes_keyboard())
        return
    users = user_repository.search_drivers_by_name_part(text, limit=15)
    if not users:
        await message.reply("Водители не найдены. Введите ФИО или часть ФИО:", reply_markup=get_routes_keyboard())
        return
    if len(users) == 1:
        u = users[0]
        if not u.tg_id or str(u.tg_id) == "0":
            await message.reply("Найденный водитель не активирован в боте.", reply_markup=get_routes_keyboard())
            return
        await state.update_data(reassign_new_tg_id=int(u.tg_id))
        await state.set_state(AdminRouteReassignState.number_auto)
        await message.reply("Введите номер ТС для переназначенного рейса:", reply_markup=get_routes_keyboard())
        return
    builder = InlineKeyboardBuilder()
    for u in users[:10]:
        if u.tg_id and str(u.tg_id) != "0":
            builder.row(
                types.InlineKeyboardButton(
                    text=u.name,
                    callback_data=f"reassign_route_driver_{u.tg_id}",
                )
            )
    await message.reply("Выберите водителя:", reply_markup=builder.as_markup())


async def _show_reassign_confirm(message, route_id, new_tg_id, route, new_driver, user_repository, number_auto="", trailer_number=""):
    old_driver = user_repository.get_by_tg_id(int(route.tg_id))
    old_name = old_driver.name if old_driver else "Неизвестно"
    text = (
        f"🔄 Переназначение рейса {route_id}\n\n"
        f"Текущий водитель: {copy_link_fio(old_name)}\n"
        f"Новый водитель: {copy_link_fio(new_driver.name)}\n"
        f"🚚 ТС: {html.escape(number_auto or '—')}\n"
        f"🛞 Прицеп: {html.escape(trailer_number or '—')}\n\n"
        "Подтвердить переназначение?"
    )
    await message.reply(text, reply_markup=_get_reassign_route_confirm_keyboard(route_id, new_tg_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("reassign_route_driver_"))
async def reassign_route_driver_selected(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    tg_id = callback.data.replace("reassign_route_driver_", "")
    try:
        new_tg_id = int(tg_id)
    except ValueError:
        await callback.answer("Ошибка.")
        return
    data = await state.get_data()
    route_id = data.get("reassign_route_id")
    if not route_id:
        await callback.message.edit_text("Сессия истекла.")
        await callback.answer()
        return
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await callback.message.edit_text("Рейс не найден.")
        await callback.answer()
        return
    new_driver = user_repository.get_by_tg_id(new_tg_id)
    if not new_driver:
        await callback.message.edit_text("Водитель не найден.")
        await callback.answer()
        return
    await state.update_data(reassign_new_tg_id=new_tg_id)
    await state.set_state(AdminRouteReassignState.number_auto)
    await callback.message.edit_text("Введите номер ТС для переназначенного рейса:")
    await callback.answer()


@router.message(AdminRouteReassignState.number_auto)
async def reassign_number_auto_entered(
    message: types.Message,
    state: FSMContext,
):
    number_auto = message.text.strip().upper() if message.text else ""
    await state.update_data(reassign_number_auto=number_auto)
    await state.set_state(AdminRouteReassignState.trailer_number)
    await message.reply("Введите номер прицепа (или «-» если нет):", reply_markup=get_routes_keyboard())


@router.message(AdminRouteReassignState.trailer_number)
async def reassign_trailer_number_entered(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    trailer = message.text.strip().upper() if message.text else ""
    if trailer == "-":
        trailer = ""
    await state.update_data(reassign_trailer_number=trailer)
    data = await state.get_data()
    route_id = data.get("reassign_route_id")
    new_tg_id = data.get("reassign_new_tg_id")
    number_auto = data.get("reassign_number_auto", "")
    if not route_id or not new_tg_id:
        await state.clear()
        await message.reply("Сессия истекла. Начните переназначение заново.", reply_markup=get_routes_keyboard())
        return
    route = route_repository.get_by_id_str(route_id)
    new_driver = user_repository.get_by_tg_id(new_tg_id)
    if not route or not new_driver:
        await state.clear()
        await message.reply("Рейс или водитель не найден.", reply_markup=get_routes_keyboard())
        return
    await _show_reassign_confirm(message, route_id, new_tg_id, route, new_driver, user_repository, number_auto=number_auto, trailer_number=trailer)


@router.callback_query(F.data.startswith("confirm_reassign_route_"))
async def confirm_reassign_route(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    raw = callback.data.replace("confirm_reassign_route_", "")
    parts = raw.split("_", 1)
    route_id = parts[0]
    new_tg_id = int(parts[1]) if len(parts) > 1 else 0
    data = await state.get_data()
    number_auto = data.get("reassign_number_auto", "")
    trailer_number = data.get("reassign_trailer_number", "")
    await state.clear()
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await callback.message.edit_text("Рейс не найден.")
        await callback.answer()
        return
    old_tg_id = int(route.tg_id)
    ok = route_repository.reassign_driver(route_id, new_tg_id)
    if not ok:
        await callback.message.edit_text("❌ Не удалось переназначить рейс.")
        await callback.answer()
        return
    if number_auto:
        route_repository.update_route_field(route_id, "number_auto", number_auto)
    if trailer_number is not None:
        route_repository.update_route_field(route_id, "trailer_number", trailer_number)
    route = route_repository.get_by_id_str(route_id)
    bot = create_bot()
    new_driver = user_repository.get_by_tg_id(new_tg_id)
    old_driver = user_repository.get_by_tg_id(old_tg_id)
    new_name = new_driver.name if new_driver else "Неизвестно"
    old_name = old_driver.name if old_driver else "Неизвестно"
    msg_old = (
        f"🚫 Рейс отменён\n\n"
        f"N рейса: {route_id}\n"
        f"👤 Водитель: {copy_link_fio(old_name)}"
    )
    try:
        await bot.send_message(old_tg_id, msg_old, parse_mode="HTML")
    except Exception:
        pass
    try:
        await _notify_driver_about_new_route(route, route_repository, user_repository, bot)
    except Exception as e:
        await callback.message.answer(f"⚠️ Переназначено, но не удалось уведомить нового водителя: {e}")
    await callback.message.edit_text(f"✅ Рейс {route_id} переназначен на {new_name}.")
    await callback.answer()


@router.callback_query(F.data == "cancel_reassign_route")
async def cancel_reassign_route_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Переназначение отменено.")
    await callback.answer()


# --- Изменение рейса (упрощённо: только параметры рейса) ---

@router.message(F.text == "✏️ Изменить рейс")
async def edit_route_start(message: types.Message, state: FSMContext):
    await state.set_state(AdminRouteEditState.route_id)
    await message.reply("Введите номер рейса для изменения:", reply_markup=get_routes_keyboard())


@router.message(AdminRouteEditState.route_id)
async def edit_route_id_entered(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
):
    route_id = message.text.strip()
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await state.clear()
        await message.reply("❌ Рейс не найден.", reply_markup=get_routes_keyboard())
        return
    await state.update_data(edit_route_id=route_id)
    await state.set_state(AdminRouteEditState.choosing_field)
    points_ids = [x for x in (route.points or "").split(",") if x.strip() and x.strip() != "0"]
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🚚 ТС", callback_data="edit_route_field_number_auto"),
        types.InlineKeyboardButton(text="🛞 Прицеп", callback_data="edit_route_field_trailer_number"),
    )
    builder.row(
        types.InlineKeyboardButton(text="🌡 Температура", callback_data="edit_route_field_temperature"),
        types.InlineKeyboardButton(text="☎ Контакты", callback_data="edit_route_field_dispatcher_contacts"),
    )
    builder.row(
        types.InlineKeyboardButton(text="📋 N регистрации", callback_data="edit_route_field_registration_number"),
    )
    if points_ids:
        builder.row(types.InlineKeyboardButton(text="📍 Точки рейса", callback_data="edit_route_field_points"))
        if len(points_ids) >= 2:
            builder.row(types.InlineKeyboardButton(text="🔄 Изменить порядок точек", callback_data="edit_route_reorder_points"))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit_route"))
    await message.reply("Что изменить?", reply_markup=builder.as_markup())


def _build_reorder_points_keyboard(route_id: str, points_ids: list, route_repository: RouteRepository):
    """Клавиатура для изменения порядка точек: кнопки ⬆️ Вверх / ⬇️ Вниз для каждой точки.
    Используем индекс (i) в callback — route_id берём из state."""
    builder = InlineKeyboardBuilder()
    for i, pid in enumerate(points_ids):
        try:
            point = route_repository.get_point_by_id(int(pid))
            if not point:
                continue
            ptype = "Загрузка" if point.type_point == "loading" else "Выгрузка"
            row_btns = []
            if i > 0:
                row_btns.append(types.InlineKeyboardButton(
                    text=f"⬆️ {i + 1}. {ptype}",
                    callback_data=f"reorder_point_up_{i}",
                ))
            if i < len(points_ids) - 1:
                row_btns.append(types.InlineKeyboardButton(
                    text=f"⬇️ {i + 1}. {ptype}",
                    callback_data=f"reorder_point_down_{i}",
                ))
            if row_btns:
                builder.row(*row_btns)
        except ValueError:
            continue
    builder.row(types.InlineKeyboardButton(text="✅ Готово", callback_data="edit_route_reorder_done"))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit_route"))
    return builder.as_markup()


def _format_reorder_points_text(points_ids: list, route_repository: RouteRepository) -> str:
    """Форматирует текст списка точек для экрана изменения порядка."""
    lines = ["🔄 Текущий порядок точек:\n"]
    for i, pid in enumerate(points_ids, 1):
        try:
            point = route_repository.get_point_by_id(int(pid))
            if point:
                ptype = "Загрузка" if point.type_point == "loading" else "Выгрузка"
                lines.append(f"{i}. {ptype}: {point.place_point}")
        except ValueError:
            continue
    lines.append("\nНажмите ⬆️ или ⬇️ для перемещения точки.")
    return "\n".join(lines)


@router.callback_query(F.data == "edit_route_reorder_points")
async def edit_route_reorder_points(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
):
    """Показать список точек с возможностью изменить порядок."""
    data = await state.get_data()
    route_id = data.get("edit_route_id")
    if not route_id:
        await callback.answer("Сессия истекла.")
        return
    route = route_repository.get_by_id_str(route_id)
    if not route or not route.points or route.points == "0":
        await callback.message.edit_text("В рейсе нет точек.")
        await callback.answer()
        return
    points_ids = [x for x in route.points.split(",") if x.strip() and x.strip() != "0"]
    if len(points_ids) < 2:
        await callback.message.edit_text("Для изменения порядка нужно минимум 2 точки.")
        await callback.answer()
        return
    text = _format_reorder_points_text(points_ids, route_repository)
    await callback.message.edit_text(
        text,
        reply_markup=_build_reorder_points_keyboard(route_id, points_ids, route_repository),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reorder_point_up_"))
async def reorder_point_up(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
):
    """Переместить точку вверх (на одну позицию)."""
    try:
        idx = int(callback.data.replace("reorder_point_up_", ""))
    except ValueError:
        await callback.answer("Ошибка.")
        return
    data = await state.get_data()
    route_id = data.get("edit_route_id")
    if not route_id:
        await callback.answer("Сессия истекла.")
        return
    route = route_repository.get_by_id_str(route_id)
    if not route or not route.points:
        await callback.answer("Рейс не найден.")
        return
    points_ids = [x for x in route.points.split(",") if x.strip() and x.strip() != "0"]
    if idx <= 0 or idx >= len(points_ids):
        await callback.answer()
        return
    # swap with previous
    points_ids[idx], points_ids[idx - 1] = points_ids[idx - 1], points_ids[idx]
    new_points = ",".join(points_ids)
    route_repository.add_point_to_route(route_id, new_points)
    text = _format_reorder_points_text(points_ids, route_repository)
    await callback.message.edit_text(
        text,
        reply_markup=_build_reorder_points_keyboard(route_id, points_ids, route_repository),
    )
    await callback.answer("Порядок обновлён")


@router.callback_query(F.data.startswith("reorder_point_down_"))
async def reorder_point_down(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
):
    """Переместить точку вниз (на одну позицию)."""
    try:
        idx = int(callback.data.replace("reorder_point_down_", ""))
    except ValueError:
        await callback.answer("Ошибка.")
        return
    data = await state.get_data()
    route_id = data.get("edit_route_id")
    if not route_id:
        await callback.answer("Сессия истекла.")
        return
    route = route_repository.get_by_id_str(route_id)
    if not route or not route.points:
        await callback.answer("Рейс не найден.")
        return
    points_ids = [x for x in route.points.split(",") if x.strip() and x.strip() != "0"]
    if idx < 0 or idx >= len(points_ids) - 1:
        await callback.answer()
        return
    # swap with next
    points_ids[idx], points_ids[idx + 1] = points_ids[idx + 1], points_ids[idx]
    new_points = ",".join(points_ids)
    route_repository.add_point_to_route(route_id, new_points)
    text = _format_reorder_points_text(points_ids, route_repository)
    await callback.message.edit_text(
        text,
        reply_markup=_build_reorder_points_keyboard(route_id, points_ids, route_repository),
    )
    await callback.answer("Порядок обновлён")


async def _notify_driver_route_changed(route, route_repository: RouteRepository):
    """Отправить водителю уведомление об изменении рейса (тот же формат, что при «Завершить»)."""
    if not route or not route.tg_id:
        return
    try:
        bot = create_bot()
        text = "✏️ Рейс изменён\n\n"
        text += _format_route_info_for_driver(route)
        text += "\n\n"
        points_ids = (route.points or "").split(",") if route.points != "0" else []
        if points_ids and points_ids[0] != "0":
            text += "📍 Точки:\n"
            for point_id_str in points_ids:
                if point_id_str == "0":
                    continue
                try:
                    point = route_repository.get_point_by_id(int(point_id_str))
                    if point:
                        type_emoji = "📦" if point.type_point == "loading" else "📤"
                        type_text = "Загрузка" if point.type_point == "loading" else "Выгрузка"
                        text += f"  {type_emoji} {type_text}: {point.place_point} ({point.date_point})\n"
                except ValueError:
                    continue
        await bot.send_message(int(route.tg_id), text, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка уведомления водителю о изменении рейса: {e}")


@router.callback_query(F.data == "edit_route_reorder_done")
async def edit_route_reorder_done(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
):
    """Завершить изменение порядка точек и вернуться в меню редактирования."""
    data = await state.get_data()
    route_id = data.get("edit_route_id")
    if not route_id:
        await callback.message.edit_text("Сессия истекла.")
        await callback.answer()
        return
    await state.set_state(AdminRouteEditState.choosing_field)
    route = route_repository.get_by_id_str(route_id)
    if route and route.tg_id:
        await _notify_driver_route_changed(route, route_repository)
    points_ids = [x for x in (route.points or "").split(",") if x.strip() and x.strip() != "0"]
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🚚 ТС", callback_data="edit_route_field_number_auto"),
        types.InlineKeyboardButton(text="🛞 Прицеп", callback_data="edit_route_field_trailer_number"),
    )
    builder.row(
        types.InlineKeyboardButton(text="🌡 Температура", callback_data="edit_route_field_temperature"),
        types.InlineKeyboardButton(text="☎ Контакты", callback_data="edit_route_field_dispatcher_contacts"),
    )
    builder.row(
        types.InlineKeyboardButton(text="📋 N регистрации", callback_data="edit_route_field_registration_number"),
    )
    if points_ids:
        builder.row(types.InlineKeyboardButton(text="📍 Точки рейса", callback_data="edit_route_field_points"))
        if len(points_ids) >= 2:
            builder.row(types.InlineKeyboardButton(text="🔄 Изменить порядок точек", callback_data="edit_route_reorder_points"))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit_route"))
    await callback.message.edit_text("✅ Порядок точек обновлён.\n\nЧто изменить?", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "edit_route_field_points")
async def edit_route_choose_point(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
):
    data = await state.get_data()
    route_id = data.get("edit_route_id")
    if not route_id:
        await callback.answer("Сессия истекла.")
        return
    route = route_repository.get_by_id_str(route_id)
    if not route or not route.points or route.points == "0":
        await callback.message.edit_text("В рейсе нет точек.")
        await callback.answer()
        return
    points_ids = [x for x in route.points.split(",") if x.strip() and x.strip() != "0"]
    builder = InlineKeyboardBuilder()
    for i, pid in enumerate(points_ids, 1):
        try:
            point = route_repository.get_point_by_id(int(pid))
            if point:
                ptype = "Загрузка" if point.type_point == "loading" else "Выгрузка"
                label = f"{i}. {ptype}: {point.place_point[:30]}…" if len(point.place_point) > 30 else f"{i}. {ptype}: {point.place_point}"
                builder.row(types.InlineKeyboardButton(text=label, callback_data=f"edit_route_point_{pid}"))
        except ValueError:
            continue
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit_route"))
    await callback.message.edit_text("Выберите точку:", reply_markup=builder.as_markup())
    await callback.answer()


# Человекочитаемые названия статусов точки для выбора и уведомлений
POINT_STATUS_LABELS = {
    "new": "— (новая)",
    "process": "Выехал на точку",
    "registration": "Зарегистрировался",
    "load": "На воротах",
    "docs": "Забрал документы",
    "success": "Завершена",
}


@router.callback_query(F.data.startswith("edit_route_point_status_"))
async def edit_route_point_status_selected(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    """Обработка выбора статуса точки (кнопки). Должен быть зарегистрирован выше edit_route_point_, т.к. callback совпадает по префиксу."""
    raw = callback.data.replace("edit_route_point_status_", "")
    parts = raw.split("_", 1)
    if len(parts) != 2:
        await callback.answer("Ошибка данных.")
        return
    point_id = int(parts[0])
    status_value = parts[1]
    if status_value not in POINT_STATUS_LABELS:
        await callback.answer("Неизвестный статус.")
        return
    data = await state.get_data()
    route_id = data.get("edit_route_id")
    if not route_id:
        await callback.message.edit_text("Сессия истекла.")
        await callback.answer()
        return
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await callback.message.edit_text("Рейс не найден.")
        await callback.answer()
        return
    ok = route_repository.update_point_status(point_id, status_value, None)
    if not ok:
        await callback.answer("Не удалось обновить статус.")
        return
    label = POINT_STATUS_LABELS[status_value]
    from services.notification_service import NotificationService
    notifier = NotificationService(user_repository)
    try:
        await notifier.bot.send_message(
            int(route.tg_id),
            f"✏️ В рейсе {route_id} изменён статус точки: {label}",
        )
    except Exception:
        pass
    await callback.message.edit_text(f"✅ Статус точки рейса {route_id} обновлён на «{label}». Водитель уведомлён.")
    await callback.answer()


@router.callback_query(F.data.startswith("edit_route_point_"))
async def edit_route_point_selected(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    raw = callback.data.replace("edit_route_point_", "")
    parts = raw.split("_")
    if len(parts) >= 2:
        point_id = parts[0]
        field = "_".join(parts[1:])
    else:
        point_id = raw
        field = None
    await state.update_data(edit_point_id=int(point_id))
    if field:
        if field == "status":
            # Выбор статуса кнопками, без ручного ввода
            builder = InlineKeyboardBuilder()
            for status_key, label in POINT_STATUS_LABELS.items():
                builder.row(types.InlineKeyboardButton(
                    text=label,
                    callback_data=f"edit_route_point_status_{point_id}_{status_key}",
                ))
            builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit_route"))
            await callback.message.edit_text("Выберите новый статус точки:", reply_markup=builder.as_markup())
            await callback.answer()
            return
        await state.update_data(edit_point_field=field)
        await state.set_state(AdminRouteEditState.value)
        field_names = {"type_point": "Тип (loading/unloading)", "place_point": "Место", "date_point": "Дата",
                       "time_accepted": "Время выезда", "time_registration": "Время регистрации",
                       "time_put_on_gate": "Время на ворота", "time_docs": "Время документов",
                       "time_departure": "Время выезда с точки", "status": "Статус"}
        await callback.message.edit_text(f"Введите новое значение для «{field_names.get(field, field)}»:")
        await callback.answer()
        return
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="Тип (загрузка/выгрузка)", callback_data="edit_route_point_{}_type_point".format(point_id)),
        types.InlineKeyboardButton(text="Место", callback_data="edit_route_point_{}_place_point".format(point_id)),
    )
    builder.row(
        types.InlineKeyboardButton(text="Дата", callback_data="edit_route_point_{}_date_point".format(point_id)),
        types.InlineKeyboardButton(text="Статус", callback_data="edit_route_point_{}_status".format(point_id)),
    )
    builder.row(
        types.InlineKeyboardButton(text="Время выезда", callback_data="edit_route_point_{}_time_accepted".format(point_id)),
        types.InlineKeyboardButton(text="Время регистрации", callback_data="edit_route_point_{}_time_registration".format(point_id)),
    )
    builder.row(
        types.InlineKeyboardButton(text="Время на ворота", callback_data="edit_route_point_{}_time_put_on_gate".format(point_id)),
        types.InlineKeyboardButton(text="Время документов", callback_data="edit_route_point_{}_time_docs".format(point_id)),
    )
    builder.row(types.InlineKeyboardButton(text="Время выезда с точки", callback_data="edit_route_point_{}_time_departure".format(point_id)))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit_route"))
    await callback.message.edit_text("Какой параметр точки изменить?", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("edit_route_field_"))
async def edit_route_field_selected(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    field = callback.data.replace("edit_route_field_", "")
    if field == "points":
        await callback.answer()
        return
    await state.update_data(edit_field=field)
    await state.set_state(AdminRouteEditState.value)
    await callback.message.edit_text(f"Введите новое значение для поля «{field}»:")
    await callback.answer()


@router.message(AdminRouteEditState.value)
async def edit_route_value_entered(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    value = message.text.strip()
    data = await state.get_data()
    route_id = data.get("edit_route_id")
    point_id = data.get("edit_point_id")
    field = data.get("edit_point_field") or data.get("edit_field")
    if not route_id or not field:
        await state.clear()
        await message.reply("Сессия истекла.", reply_markup=get_routes_keyboard())
        return
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await state.clear()
        await message.reply("Рейс не найден.", reply_markup=get_routes_keyboard())
        return
    if point_id is not None:
        ok = route_repository.update_point_field(point_id, field, value)
        if not ok:
            await message.reply("Не удалось обновить параметр точки.", reply_markup=get_routes_keyboard())
            return
        point_field_names = {
            "type_point": "Тип точки", "place_point": "Место точки", "date_point": "Дата точки",
            "time_accepted": "Время выезда", "time_registration": "Время регистрации",
            "time_put_on_gate": "Время на ворота", "time_docs": "Время документов",
            "time_departure": "Время выезда с точки", "status": "Статус точки",
        }
        field_name_ru = point_field_names.get(field, field)
        await state.update_data(edit_point_id=None, edit_point_field=None, edit_field=None)
        await state.set_state(AdminRouteEditState.choosing_field)
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(text="✏️ Продолжить изменения", callback_data="edit_route_continue"),
            types.InlineKeyboardButton(text="✅ Завершить", callback_data="edit_route_finish"),
        )
        await message.reply(f"✅ Точка рейса {route_id} обновлена: {field_name_ru} — {value}\n\nПродолжить изменения или завершить? Уведомление водителю будет отправлено после нажатия «Завершить».", reply_markup=builder.as_markup())
        return
    ok = route_repository.update_route_field(route_id, field, value)
    if not ok:
        await message.reply("Не удалось обновить поле или поле недоступно.", reply_markup=get_routes_keyboard())
        return
    route_field_names = {
        "number_auto": "ТС", "trailer_number": "Прицеп", "temperature": "Температура",
        "dispatcher_contacts": "Контакты", "registration_number": "N регистрации",
    }
    field_name_ru = route_field_names.get(field, field)
    await state.update_data(edit_field=None)
    await state.set_state(AdminRouteEditState.choosing_field)
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="✏️ Продолжить изменения", callback_data="edit_route_continue"),
        types.InlineKeyboardButton(text="✅ Завершить", callback_data="edit_route_finish"),
    )
    await message.reply(f"✅ Рейс {route_id} обновлён: {field_name_ru} — {value}\n\nПродолжить изменения или завершить? Уведомление водителю будет отправлено после нажатия «Завершить».", reply_markup=builder.as_markup())


@router.callback_query(F.data == "edit_route_continue")
async def edit_route_continue_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
):
    """Показать меню выбора поля для изменения рейса (после «Продолжить изменения»)."""
    data = await state.get_data()
    route_id = data.get("edit_route_id")
    if not route_id:
        await callback.message.edit_text("Сессия истекла.")
        await callback.answer()
        return
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await callback.message.edit_text("Рейс не найден.")
        await callback.answer()
        return
    points_ids = [x for x in (route.points or "").split(",") if x.strip() and x.strip() != "0"]
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🚚 ТС", callback_data="edit_route_field_number_auto"),
        types.InlineKeyboardButton(text="🛞 Прицеп", callback_data="edit_route_field_trailer_number"),
    )
    builder.row(
        types.InlineKeyboardButton(text="🌡 Температура", callback_data="edit_route_field_temperature"),
        types.InlineKeyboardButton(text="☎ Контакты", callback_data="edit_route_field_dispatcher_contacts"),
    )
    builder.row(
        types.InlineKeyboardButton(text="📋 N регистрации", callback_data="edit_route_field_registration_number"),
    )
    if points_ids:
        builder.row(types.InlineKeyboardButton(text="📍 Точки рейса", callback_data="edit_route_field_points"))
        if len(points_ids) >= 2:
            builder.row(types.InlineKeyboardButton(text="🔄 Изменить порядок точек", callback_data="edit_route_reorder_points"))
    builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit_route"))
    await callback.message.edit_text("Что изменить?", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "edit_route_finish")
async def edit_route_finish_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    data = await state.get_data()
    route_id = data.get("edit_route_id")
    await state.clear()
    await callback.message.edit_text("✅ Изменения рейса завершены.")
    await callback.message.answer("Меню рейсов:", reply_markup=get_routes_keyboard())
    if route_id:
        route = route_repository.get_by_id_str(route_id)
        if route and route.tg_id:
            await _notify_driver_route_changed(route, route_repository)
    await callback.answer()


@router.callback_query(F.data == "cancel_edit_route")
async def cancel_edit_route_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Изменение рейса отменено.")
    await callback.answer()


# --- Отменённые рейсы ---

@router.message(F.text == "❌ Отменённые рейсы")
async def show_cancelled_routes(
    message: types.Message,
    state: FSMContext,
):
    await state.set_state(AdminRouteFilterByState.filter_status)
    await state.update_data(filter_status="cancelled")
    await message.reply(
        "Рейсы: Отменённые. Выберите способ отображения:",
        reply_markup=_get_filter_status_inline_keyboard("cancelled"),
    )


# --- Поиск по номеру рейса ---

@router.message(F.text == "🔍 Поиск по номеру рейса")
async def search_route_by_id_start(message: types.Message, state: FSMContext):
    await state.set_state(AdminRouteSearchByIdState.route_id)
    await message.reply("Введите номер рейса:", reply_markup=get_routes_keyboard())


@router.message(AdminRouteSearchByIdState.route_id)
async def search_route_by_id_process(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    route_id = message.text.strip()
    await state.clear()
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await message.reply("❌ Рейс не найден.", reply_markup=get_routes_keyboard())
        return
    text = _build_route_detail_html(route, route_repository, user_repository)
    await message.reply("🔍 <b>Информация о рейсе</b>\n\n" + text, reply_markup=get_routes_keyboard(), parse_mode="HTML")


# @router.message(F.text == "↩️ Назад")
# async def exit_to_main(message: types.Message):
#     await message.reply("Назад", reply_markup=get_admin_main_keyboard())