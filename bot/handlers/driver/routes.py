# handlers/driver/routes.py
import asyncio
import html
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton

from keyboards.driver_kb import (
    get_driver_routes_menu_keyboard,
    get_driver_main_keyboard,
    # get_start_point_specific_keyboard,
    # get_registration_point_specific_keyboard,
    # get_proc_loading_specific_keyboard,
    # get_docs_point_specific_keyboard,
    # get_end_point_specific_keyboard,
    # get_route_end_specific_keyboard,
    # get_route_accept_specific_keyboard,
    # get_route_selection_keyboard
)

from states.route_states import RouteState, PointState, DriverPointTimeState
from database.repositories.route_repository import RouteRepository
from database.repositories.user_repository import UserRepository
from core.bot import create_bot
from services.notification_service import NotificationService
from utils.telegram_helpers import format_point_time_display, timezone_to_short

router = Router()

# Блокировка для предотвращения дублирования уведомлений при двойном нажатии
_point_status_locks: dict = {}


def _get_point_lock(route_id: str, point_id: int, status: str) -> asyncio.Lock:
    key = f"{route_id}_{point_id}_{status}"
    if key not in _point_status_locks:
        _point_status_locks[key] = asyncio.Lock()
    return _point_status_locks[key]


# Московский часовой пояс (UTC+3) для единообразной фиксации времени точек
MOSCOW_TZ = timezone(timedelta(hours=3))


def get_current_moscow_time_str() -> str:
    """Возвращает текущее время сервера в московском часовом поясе (формат для записи в БД)."""
    return datetime.now(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")


MANUAL_TIME_SUFFIX = " (ВВ)"
MOSCOW_TIME_SUFFIX = " (Мск)"


def _wialon_suffix(tz_short: str) -> str:
    return f" (🛰️ {tz_short})"


async def _get_vehicle_data_for_status_change(route):
    """
    Получает данные ТС через Wialon: время, timezone, координаты, одометр.
    Та же цепочка, что и в mobile_api / PWA: `vehicle_number_for_wialon` + `get_vehicle_location_data`.
    :return: dict с time_str, timezone_str, lat, lng, odometer или None при ошибке
    """
    from services.wialon_service import get_vehicle_location_data, vehicle_number_for_wialon

    key = vehicle_number_for_wialon(
        getattr(route, "number_auto", None),
        getattr(route, "registration_number", None),
    )
    if not key:
        return None
    try:
        return await asyncio.to_thread(get_vehicle_location_data, key)
    except Exception:
        return None


async def _show_point_time_choice(
    callback,
    route_id: str,
    point_id: int,
    status: str,
    wialon_data: dict | None,
    state: FSMContext,
):
    """Показать выбор времени: Сохранить из Виалон, Сохранить по МСК, Ввести вручную."""
    labels = {
        "process": "Выехал на точку",
        "registration": "Зарегистрировался",
        "load": "Поставил на ворота",
        "docs": "Забрал документы",
        "success": "Выехал с точки",
    }
    label = labels.get(status, status)
    moscow_time = get_current_moscow_time_str()
    builder = InlineKeyboardBuilder()

    if wialon_data:
        tz_short = timezone_to_short(wialon_data.get("timezone_str", ""))
        wialon_time = wialon_data["time_str"] + _wialon_suffix(tz_short)
        builder.row(InlineKeyboardButton(
            text=f"🛰️ Сохранить из Виалон ({tz_short})",
            callback_data=f"point_time_wialon_{route_id}_{point_id}_{status}",
            style="success",
        ))
        await state.update_data(
            pending_point_time=wialon_time,
            pending_point_time_source="wialon",
            pending_point_route_id=route_id,
            pending_point_id=point_id,
            pending_point_status=status,
            pending_wialon_data=wialon_data,
        )
        time_line = f"Время из Wialon: {wialon_time}"
    else:
        await state.update_data(
            pending_point_time=moscow_time + MOSCOW_TIME_SUFFIX,
            pending_point_time_source="moscow",
            pending_point_route_id=route_id,
            pending_point_id=point_id,
            pending_point_status=status,
            pending_wialon_data=None,
        )
        time_line = f"Не удалось получить время через Wialon. Время (Мск): {moscow_time}"

    builder.row(InlineKeyboardButton(
        text="✅ Сохранить по МСК",
        callback_data=f"point_time_keep_{route_id}_{point_id}_{status}",
    ))
    builder.row(InlineKeyboardButton(
        text="✏️ Ввести вручную",
        callback_data=f"point_time_manual_{route_id}_{point_id}_{status}",
    ))
    await callback.message.edit_text(
        f"⏱ Смена статуса: {label}\n\n{time_line}\n\n"
        "Подтвердите корректность времени или выберите другой вариант:",
        reply_markup=builder.as_markup()
    )


def _get_moscow_time_from_message_date(msg_date):
    """
    Конвертирует время из callback.message.date (UTC) в московское время (UTC+3).
    Используется только для отображения; при записи времени точки используйте get_current_moscow_time_str().
    """
    if not msg_date:
        return None
    msg_time = msg_date.replace(tzinfo=timezone.utc).astimezone(MOSCOW_TZ)
    return msg_time.strftime("%d.%m.%Y %H:%M")


def _copy_code(text) -> str:
    """Ссылка для копирования по клику: <a href='tg://copy?text=...'><code>...</code></a>"""
    safe = (text or "").strip() or "—"
    return f'<a href="tg://copy?text={quote(safe)}"><code>{html.escape(safe)}</code></a>'


# Создаем функции для генерации клавиатур с привязкой к конкретным точкам (описания — в тексте сообщения)
def get_start_point_specific_keyboard(route_id: str, point_id: int):
    """Кнопка: нажать, когда выехали на точку."""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Выехал на точку",
        callback_data=f"start_point_{route_id}_{point_id}",
        style="success",
    ))
    return builder.as_markup()

def get_registration_point_specific_keyboard(route_id: str, point_id: int):
    """Кнопка: нажать после регистрации на точке. Отмена — вернуться к статусу «новая» (ещё не выехал)."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="Зарегистрировался",
        callback_data=f"registration_point_{route_id}_{point_id}",
        style="success",
    ))
    builder.row(InlineKeyboardButton(
        text="Отменить (к предыдущему статусу)",
        callback_data=f"point_revert_{route_id}_{point_id}_process",
        style="danger",
    ))
    return builder.as_markup()

def get_proc_loading_specific_keyboard(route_id: str, point_id: int):
    """Кнопка: нажать, когда поставили ТС на ворота. Отмена — к «Зарегистрировался»."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="Поставил на ворота",
        callback_data=f"proc_loading_{route_id}_{point_id}",
        style="success",
    ))
    builder.row(InlineKeyboardButton(
        text="Отменить (к предыдущему статусу)",
        callback_data=f"point_revert_{route_id}_{point_id}_registration",
        style="danger",
    ))
    return builder.as_markup()

def get_docs_point_specific_keyboard(route_id: str, point_id: int):
    """Кнопка: нажать, когда забрали документы. Отмена — к «На воротах»."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="Забрал документы",
        callback_data=f"docs_point_{route_id}_{point_id}",
        style="success",
    ))
    builder.row(InlineKeyboardButton(
        text="Отменить (к предыдущему статусу)",
        callback_data=f"point_revert_{route_id}_{point_id}_load",
        style="danger",
    ))
    return builder.as_markup()

def get_end_point_specific_keyboard(route_id: str, point_id: int):
    """Кнопка: нажать, когда выехали с точки. Отмена — к «Забрал документы»."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="Выехал с точки",
        callback_data=f"end_point_{route_id}_{point_id}",
        style="success",
    ))
    builder.row(InlineKeyboardButton(
        text="Отменить (к предыдущему статусу)",
        callback_data=f"point_revert_{route_id}_{point_id}_docs",
        style="danger",
    ))
    return builder.as_markup()

def get_start_new_point_specific_keyboard(route_id: str):
    """Клавиатура для перехода к следующей точке"""
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="➡️ К следующей точке", 
        callback_data=f"next_point_{route_id}"
    ))
    return builder.as_markup()

def get_route_end_specific_keyboard(route_id: str):
    """Клавиатура для окончания конкретного рейса"""
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="✅ Завершить рейс", 
        callback_data=f"end_route_{route_id}"
    ))
    return builder.as_markup()


def get_active_route_choice_keyboard(route_id: str):
    """Клавиатура выбора при нажатии на активный рейс: следующий статус или полное задание."""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="📋 Текущий статус",
            callback_data=f"driver_route_next_{route_id}"
        ),
        types.InlineKeyboardButton(
            text="📄 Посмотреть задание полностью",
            callback_data=f"driver_route_full_{route_id}"
        ),
    )
    return builder.as_markup()

def get_route_accept_specific_keyboard(route_id: str):
    """Клавиатура для принятия конкретного рейса"""
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="✅ Принять рейс", 
        callback_data=f"accept_route_{route_id}"
    ))
    return builder.as_markup()

def get_route_selection_keyboard(routes: list, accept_only_route_id: str = None) -> InlineKeyboardMarkup:
    """Клавиатура для выбора рейса. Принять можно только рейс accept_only_route_id (первый по порядку)."""
    builder = InlineKeyboardBuilder()
    
    for route in routes:
        status_emoji = "📋" if route.status == "new" else "🚚"
        can_accept = (accept_only_route_id is not None and route.id == accept_only_route_id)
        if can_accept:
            builder.add(types.InlineKeyboardButton(
                text=f"✅ Принять рейс {route.id}",
                callback_data=f"accept_route_{route.id}"
            ))
        else:
            builder.add(types.InlineKeyboardButton(
                text=f"{status_emoji} Рейс {route.id} (просмотр)",
                callback_data=f"select_route_{route.id}"
            ))
    
    builder.adjust(1)  # По одной кнопке в строке
    return builder.as_markup()

async def get_active_point_info(route_id: str, route_repository: RouteRepository):
    """Получить информацию об активной точке для конкретного рейса"""
    route = route_repository.get_by_id_str(route_id)
    
    if not route:
        return None, None, None
    
    points = route.points.split(",") if route.points != "0" else []
    
    for point_str in points:
        try:
            point_id = int(point_str)
        except ValueError:
            continue
            
        point = route_repository.get_point_by_id(point_id)
        
        if point and point.status == "new":
            return route, point, "new"
        elif point and point.status == "process":
            return route, point, "process"
        elif point and point.status == "registration":
            return route, point, "registration"
        elif point and point.status == "load":
            return route, point, "load"
        elif point and point.status == "docs":
            return route, point, "docs"
    
    # Если все точки завершены
    return route, None, "completed"

# ИЗМЕНЯЕМ: теперь "🚚 Рейс" открывает меню рейсов
@router.message(F.text == "🚚 Рейс")
async def driver_routes_menu(message: types.Message):
    """Меню рейсов для водителя"""
    await message.reply("🚚 Меню рейсов", reply_markup=get_driver_routes_menu_keyboard())

# ИЗМЕНЯЕМ: переименовываем старую функцию
@router.message(F.text == "🚚 Активный рейс")
async def show_active_route(
    message: types.Message, 
    route_repository: RouteRepository, 
    user_repository: UserRepository
):
    """Показать активный рейс водителя"""
    user_id = message.chat.id
    
    # Получаем все рейсы пользователя с использованием нового метода
    user_routes = route_repository.get_routes_by_driver(user_id)
    
    if not user_routes:
        await message.answer("📭 У вас нет назначенных рейсов", reply_markup=get_driver_routes_menu_keyboard())
        return
    
    # Фильтруем рейсы по статусу
    new_routes = [r for r in user_routes if r.status == "new"]
    process_routes = [r for r in user_routes if r.status == "process"]
    completed_routes = [r for r in user_routes if r.status == "success"]
    
    # Проверяем, есть ли рейс в процессе
    if process_routes:
        # Есть активный рейс — предлагаем выбор: следующий статус или полное задание
        active_route = process_routes[0]
        await message.answer(
            "📍 У вас активный рейс.\n\nВыберите:",
            reply_markup=get_active_route_choice_keyboard(active_route.id),
        )
        return

    if new_routes:
        # Нет активных рейсов, но есть новые — принять можно только первый (по id)
        new_routes.sort(key=lambda x: x.id)  # первый по id = тот, что можно принять
        first_route = new_routes[0]
        text = f"📋 У вас {len(new_routes)} новый(ых) рейс(ов).\nПринять к исполнению можно только первый рейс из списка.\n\n"
        
        for route in new_routes:
            points = route.points.split(",") if route.points != "0" else []
            point_count = len([p for p in points if p != "0"])
            
            text += f"📋 Рейс: {_copy_code(route.id)}\n"
            if route.number_auto:
                text += f"🚚 ТС: {_copy_code(route.number_auto or '—')}\n"
            if getattr(route, 'trailer_number', None):
                text += f"🛞 Прицеп: {_copy_code(route.trailer_number)}\n"
            if route.temperature:
                text += f"🌡 Температура: {route.temperature}\n"
            if route.dispatcher_contacts:
                text += f"☎ Контакты: {route.dispatcher_contacts}\n"
            if getattr(route, 'registration_number', None):
                text += f"📋 N регистрации: {route.registration_number}\n"
            text += f"📍 Точек: {point_count}\n"
            
            # Показываем первую точку для примера
            if points and points[0] != "0":
                try:
                    first_point_id = int(points[0])
                    first_point = route_repository.get_point_by_id(first_point_id)
                    if first_point:
                        type_text = "Загрузка" if first_point.type_point == "loading" else "Выгрузка"
                        text += f"   📦 Первая точка: {type_text}\n"
                except ValueError:
                    pass
            
            text += "\n"
        
        text += "Выберите рейс для просмотра. Кнопка «Принять рейс» доступна только для первого рейса:"
        
        await message.answer(text, reply_markup=get_route_selection_keyboard(new_routes, first_route.id), parse_mode="HTML")
        
    elif completed_routes:
        # Только завершенные рейсы - предлагаем посмотреть прошедшие рейсы
        text = f"✅ У вас {len(completed_routes)} завершенный(ых) рейс(ов).\n"
        text += "Для просмотра нажмите '📋 Прошедшие рейсы'"
        await message.answer(text, reply_markup=get_driver_routes_menu_keyboard())
    else:
        await message.answer("📭 Активных рейсов нет", reply_markup=get_driver_routes_menu_keyboard())


async def _driver_show_next_status(
    chat_id: int,
    route_id: str,
    route_repository: RouteRepository,
    user_repository: UserRepository,
    send_func,
):
    """Показать следующий статус по активному рейсу (текущая точка и кнопка действия)."""
    route = route_repository.get_by_id_str(route_id)
    if not route or route.status != "process":
        await send_func("❌ Рейс не найден или не в процессе.", reply_markup=get_driver_routes_menu_keyboard())
        return
    route_info, active_point, point_status = await get_active_point_info(route_id, route_repository)
    point_status_ru = {"new": "Принят", "process": "Выехал на точку", "registration": "Зарегистрировался", "load": "На воротах", "docs": "Забрал документы"}
    status_ru = point_status_ru.get(point_status, point_status)
    active_point_type = ""
    active_point_place = ""
    active_point_time = ""
    if active_point:
        active_point_type = "Загрузка" if active_point.type_point == "loading" else "Выгрузка"
        active_point_place = (active_point.place_point or "").strip() or ""
        times = [t for t in (active_point.time_accepted, active_point.time_registration, active_point.time_put_on_gate, active_point.time_docs, active_point.time_departure) if t and str(t).strip() and str(t) not in ("0", "")]
        active_point_time = format_point_time_display(times[-1]) if times else ""
    status_line = (status_ru if status_ru else "В процессе")
    if active_point_type:
        status_line += f", {active_point_type}"
    if active_point_place:
        status_line += f", {active_point_place}"
    if active_point_time:
        status_line += f", {active_point_time}"
    if active_point:
        type_text = "Загрузка" if active_point.type_point == "loading" else "Выгрузка"
        text = "📍 Текущий рейс:\n\n"
        text += f"N рейса: {_copy_code(route.id)}\n"
        if route.number_auto:
            text += f"🚚 ТС: {_copy_code(route.number_auto or '—')}\n"
        if getattr(route, 'trailer_number', None):
            text += f"🛞 Прицеп: {_copy_code(route.trailer_number)}\n"
        if route.temperature:
            text += f"🌡 Температура: {route.temperature}\n"
        if route.dispatcher_contacts:
            text += f"☎ Контакты: {route.dispatcher_contacts}\n"
        if getattr(route, 'registration_number', None):
            text += f"📋 N регистрации: {route.registration_number}\n"
        text += f"📊 Статус рейса: {status_line}\n\n"
        text += f"📦 Тип точки: {type_text}\n"
        text += f"📅 Дата: {active_point.date_point}\n"
        text += f"📍 Место: {active_point.place_point}\n"
        if point_status == "new":
            await send_func(text + "\n\n⏱ Нажмите кнопку ниже, когда выедете на точку.", reply_markup=get_start_point_specific_keyboard(route_id, active_point.id), parse_mode="HTML")
        elif point_status == "process":
            await send_func(text + "\n\n⏱ Нажмите кнопку ниже, когда зарегистрируетесь на точке.", reply_markup=get_registration_point_specific_keyboard(route_id, active_point.id), parse_mode="HTML")
        elif point_status == "registration":
            await send_func(text + "\n\n⏱ Нажмите кнопку ниже, когда поставите ТС на ворота.", reply_markup=get_proc_loading_specific_keyboard(route_id, active_point.id), parse_mode="HTML")
        elif point_status == "load":
            await send_func(text + "\n\n⏱ Нажмите кнопку ниже, когда заберёте документы.", reply_markup=get_docs_point_specific_keyboard(route_id, active_point.id), parse_mode="HTML")
        elif point_status == "docs":
            points = route.points.split(",") if route.points != "0" else []
            current_point_found = False
            next_point_found = None
            next_point_id = None
            for point_str in points:
                try:
                    check_point_id = int(point_str)
                    if check_point_id == active_point.id:
                        current_point_found = True
                        continue
                    if current_point_found:
                        check_point = route_repository.get_point_by_id(check_point_id)
                        if check_point and check_point.status == "new":
                            next_point_found = check_point
                            next_point_id = check_point_id
                            break
                except ValueError:
                    continue
            if next_point_found:
                type_text = "Загрузка" if next_point_found.type_point == "loading" else "Выгрузка"
                type_emoji = "📦" if next_point_found.type_point == "loading" else "📤"
                text_next = f"{text}\n\n📍 Следующая точка:\n{type_emoji} Тип: {type_text}\n📅 Дата: {next_point_found.date_point}\n📍 Место: {next_point_found.place_point}\n\nНажмите, когда выедете на следующую точку:"
                await send_func(text_next + "\n\n⏱ Нажмите кнопку ниже, когда выедете на следующую точку.", reply_markup=get_start_point_specific_keyboard(route_id, next_point_id), parse_mode="HTML")
            else:
                await send_func(f"{text}\n\n🏁 Все точки рейса выполнены!\n\nВы можете завершить рейс:", reply_markup=get_route_end_specific_keyboard(route_id), parse_mode="HTML")
    else:
        points = route.points.split(",") if route.points != "0" else []
        text_route = "📊 Текущий рейс:\n\n"
        text_route += f"N рейса: {_copy_code(route.id)}\n"
        if route.number_auto:
            text_route += f"🚚 ТС: {_copy_code(route.number_auto or '—')}\n"
        if getattr(route, 'trailer_number', None):
            text_route += f"🛞 Прицеп: {_copy_code(route.trailer_number)}\n"
        if route.temperature:
            text_route += f"🌡 Температура: {route.temperature}\n"
        if route.dispatcher_contacts:
            text_route += f"☎ Контакты: {route.dispatcher_contacts}\n"
        if getattr(route, 'registration_number', None):
            text_route += f"📋 N регистрации: {route.registration_number}\n"
        text_route += "📊 Статус: Все точки выполнены!\n\n"
        for i, point_str in enumerate(points, 1):
            try:
                point_id = int(point_str)
            except ValueError:
                continue
            point = route_repository.get_point_by_id(point_id)
            if point:
                type_text = "Загрузка" if point.type_point == "loading" else "Выгрузка"
                status_text = {"new": "❌ Не начата", "process": "🚗 Выехал", "registration": "📝 Зарегистрирован", "load": "🚪 На воротах", "docs": "📋 Документы", "success": "✅ Завершена"}.get(point.status, "❓ Неизвестно")
                text_route += f"{i}. {type_text}\n   📍 {point.place_point}\n   📅 {point.date_point}\n   📊 {status_text}\n\n"
        await send_func(text_route, reply_markup=get_route_end_specific_keyboard(route_id), parse_mode="HTML")


async def _driver_show_full_assignment(
    route_id: str,
    route_repository: RouteRepository,
    user_repository: UserRepository,
    send_func,
):
    """Показать полное задание по рейсу (все параметры и все точки)."""
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await send_func("❌ Рейс не найден.", reply_markup=get_driver_routes_menu_keyboard())
        return
    point_status_ru = {"new": "Принят", "process": "Выехал на точку", "registration": "Зарегистрировался", "load": "На воротах", "docs": "Забрал документы", "success": "Завершена"}
    text = "📄 Задание по рейсу полностью\n\n"
    text += f"N рейса: {route.id}\n"
    text += f"🚚 ТС: {_copy_code(route.number_auto or '—')}\n"
    text += f"🛞 Прицеп: {_copy_code(getattr(route, 'trailer_number', None) or '—')}\n"
    text += f"🌡 Температура: {route.temperature or '—'}\n"
    text += f"☎ Контакты: {route.dispatcher_contacts or '—'}\n"
    text += f"📋 N регистрации: {getattr(route, 'registration_number', None) or '—'}\n\n"
    text += "📍 Точки:\n"
    points_ids = [x for x in (route.points or "").split(",") if x.strip() and x.strip() != "0"]
    for i, point_id_str in enumerate(points_ids, 1):
        try:
            point = route_repository.get_point_by_id(int(point_id_str))
        except ValueError:
            continue
        if not point:
            continue
        type_text = "Загрузка" if point.type_point == "loading" else "Выгрузка"
        status_pt = point_status_ru.get(point.status, point.status)
        times = [t for t in (point.time_accepted, point.time_registration, point.time_put_on_gate, point.time_docs, point.time_departure) if t and str(t).strip() and str(t) not in ("0", "")]
        time_str = format_point_time_display(times[-1]) if times else "—"
        text += f"{i}. {type_text} | {point.place_point} | {point.date_point} | {status_pt} | {time_str}\n"
    await send_func(text, reply_markup=get_driver_routes_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("driver_route_next_"))
async def callback_driver_route_next(callback: types.CallbackQuery, route_repository: RouteRepository, user_repository: UserRepository):
    route_id = callback.data.replace("driver_route_next_", "")
    async def send(text, reply_markup=None, parse_mode=None):
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    await _driver_show_next_status(callback.from_user.id, route_id, route_repository, user_repository, send)
    await callback.answer()


@router.callback_query(F.data.startswith("driver_route_full_"))
async def callback_driver_route_full(callback: types.CallbackQuery, route_repository: RouteRepository, user_repository: UserRepository):
    route_id = callback.data.replace("driver_route_full_", "")
    async def send(text, reply_markup=None, parse_mode=None):
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    await _driver_show_full_assignment(route_id, route_repository, user_repository, send)
    await callback.answer()


# Добавляем обработчик для кнопки "Назад" в меню рейсов
@router.message(F.text == "🔙 Назад")
async def back_from_routes_menu(message: types.Message, state: FSMContext = None):
    """Возврат из меню рейсов в главное меню"""
    if state:
        current_state = await state.get_state()
        if current_state:
            await state.clear()
    
    await message.reply("Назад", reply_markup=get_driver_main_keyboard())

@router.message(F.text == "📋 Все назначенные рейсы")
async def show_all_assigned_routes(
    message: types.Message,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    """Показать только активные назначенные рейсы, к которым водитель ещё не приступил (status=new)."""
    user_id = message.chat.id
    new_routes = route_repository.get_routes_by_driver(user_id, "new")
    if not new_routes:
        await message.answer("📭 У вас нет назначенных рейсов, к которым вы ещё не приступили.", reply_markup=get_driver_routes_menu_keyboard())
        return
    new_routes.sort(key=lambda x: x.id)
    process_routes = route_repository.get_routes_by_driver(user_id, "process")
    first_acceptable = new_routes[0].id if new_routes and not process_routes else None
    text = "📋 Ваши назначенные рейсы (ещё не начаты):\n\n"
    for r in new_routes:
        text += f"📋 Рейс {_copy_code(r.id)}\n"
        if r.number_auto:
            text += f"   🚚 ТС: {_copy_code(r.number_auto)}\n"
        if getattr(r, 'trailer_number', None):
            text += f"   🛞 Прицеп: {_copy_code(r.trailer_number)}\n"
        points = (r.points or "0").split(",")
        point_count = len([p for p in points if p and p != "0"])
        text += f"   📍 Точек: {point_count}\n\n"
    text += "Выберите рейс для просмотра:"
    await message.answer(
        text,
        reply_markup=get_route_selection_keyboard(new_routes, accept_only_route_id=first_acceptable),
        parse_mode="HTML",
    )


# ДОБАВЛЯЕМ: функцию для прошедших рейсов
@router.message(F.text == "📋 Прошедшие рейсы")
async def show_completed_routes(
    message: types.Message,
    route_repository: RouteRepository,
    user_repository: UserRepository
):
    user_id = message.chat.id
    
    # Получаем все завершенные рейсы водителя
    completed_routes = route_repository.get_routes_by_driver(user_id, "success")
    
    if not completed_routes:
        await message.answer("📭 У вас нет завершенных рейсов.", reply_markup=get_driver_routes_menu_keyboard())
        return
    
    # Сортируем по ID (предполагаем, что ID содержит дату или порядковый номер)
    completed_routes.sort(key=lambda x: x.id, reverse=True)
    
    text = f"📋 Ваши завершенные рейсы ({len(completed_routes)}):\n\n"
    
    for i, route in enumerate(completed_routes, 1):
        # Извлекаем дату из ID или используем первую точку
        date_info = "Дата не указана"
        points = route.points.split(",") if route.points != "0" else []
        
        if points and points[0] != "0":
            try:
                first_point_id = int(points[0])
                first_point = route_repository.get_point_by_id(first_point_id)
                if first_point and first_point.date_point:
                    date_info = first_point.date_point
            except ValueError:
                pass
        
        text += f"{i}. N рейса: {_copy_code(route.id)}\n"
        text += f"   📅 Дата: {date_info}\n"
        
        # Добавляем информацию о точках
        if points and points[0] != "0":
            point_count = len([p for p in points if p != "0"])
            text += f"   📍 Точек: {point_count}\n"
            
            # Показываем первую и последнюю точку
            try:
                if points[0] != "0":
                    first_point_id = int(points[0])
                    first_point = route_repository.get_point_by_id(first_point_id)
                    if first_point:
                        type_text = "Загрузка" if first_point.type_point == "loading" else "Выгрузка"
                        text += f"   🚚 Начало: {type_text} в {first_point.place_point}\n"
                
                if len(points) > 1 and points[-1] != "0":
                    last_point_id = int(points[-1])
                    last_point = route_repository.get_point_by_id(last_point_id)
                    if last_point:
                        type_text = "Загрузка" if last_point.type_point == "loading" else "Выгрузка"
                        text += f"   🏁 Конец: {type_text} в {last_point.place_point}\n"
            except ValueError:
                pass
        
        text += "\n"
    
    # Если много рейсов, разбиваем на части
    if len(text) > 4000:
        parts = []
        while len(text) > 4000:
            part = text[:4000]
            last_newline = part.rfind('\n')
            if last_newline != -1:
                parts.append(text[:last_newline])
                text = text[last_newline+1:]
            else:
                parts.append(part)
                text = text[4000:]
        if text:
            parts.append(text)
        
        for part in parts:
            await message.answer(part, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=get_driver_routes_menu_keyboard(), parse_mode="HTML")

# Обработчик выбора рейса из списка
@router.callback_query(F.data.startswith("select_route_"))
async def select_route_specific(callback: types.CallbackQuery, route_repository: RouteRepository):
    route_id = callback.data.split("_")[2]
    
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await callback.message.answer("❌ Рейс не найден")
        return
    
    # Проверяем, что этот рейс принадлежит текущему пользователю
    if int(route.tg_id) != callback.from_user.id:
        await callback.message.answer("❌ Это не ваш рейс")
        return

    # Первым по порядку считается рейс с минимальным id среди новых (для кнопки «Принять»)
    user_new_routes = route_repository.get_routes_by_driver(callback.from_user.id, "new")
    user_new_routes.sort(key=lambda x: x.id)
    first_route_id = user_new_routes[0].id if user_new_routes else None
    user_process_routes = route_repository.get_routes_by_driver(callback.from_user.id, "process")
    can_accept_this = (
        route.status == "new"
        and first_route_id == route_id
        and not user_process_routes
    )

    # Показываем информацию о рейсе
    points = route.points.split(",") if route.points != "0" else []
    text_route = f"📋 Рейс: {_copy_code(route.id)}\n\n"
    
    for i, point_str in enumerate(points, 1):
        try:
            point_id = int(point_str)
        except ValueError:
            continue
            
        point = route_repository.get_point_by_id(point_id)
        if point:
            type_text = "Загрузка" if point.type_point == "loading" else "Выгрузка"
            text_route += (
                f"{i}. {type_text}\n"
                f"   📅 Дата: {point.date_point}\n"
                f"   📍 Место: {point.place_point}\n\n"
            )
    
    await callback.message.edit_text(text_route, parse_mode="HTML")
    
    if can_accept_this:
        await callback.message.answer(
            "Нажмите, чтобы принять рейс:",
            reply_markup=get_route_accept_specific_keyboard(route.id)
        )
    else:
        await callback.message.answer(
            f"Принять к исполнению можно только первый рейс (№ {first_route_id}). Сначала примите его из списка выше."
        )
    await callback.answer()

# Обработчик принятия рейса
@router.callback_query(F.data.startswith("point_revert_"))
async def point_revert_callback(
    callback: types.CallbackQuery,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    """Отмена смены статуса точки: возврат к предыдущему статусу и очистка сохранённого времени."""
    parts = callback.data.split("_")
    if len(parts) != 5:
        await callback.answer("Ошибка.")
        return
    route_id = parts[2]
    point_id = int(parts[3])
    from_status = parts[4]
    to_status_map = {"process": "new", "registration": "process", "load": "registration", "docs": "load", "success": "docs"}
    to_status = to_status_map.get(from_status)
    if not to_status:
        await callback.answer("Неизвестный статус.")
        return
    route = route_repository.get_by_id_str(route_id)
    if not route or int(route.tg_id) != callback.from_user.id:
        await callback.answer("Рейс не найден или это не ваш рейс.")
        return
    point = route_repository.get_point_by_id(point_id)
    if not point or point.id_route != route_id:
        await callback.answer("Точка не найдена.")
        return
    ok = route_repository.revert_point_status(point_id, from_status, to_status)
    if not ok:
        await callback.answer("Не удалось отменить статус.")
        return
    from services.notification_service import NotificationService
    notifier = NotificationService(user_repository)
    point_type_text = "Загрузка" if point.type_point == "loading" else "Выгрузка"
    await notifier.notify_point_status_reverted(
        route_id, point_id, callback.from_user.id,
        from_status, to_status,
        point_type=point_type_text,
        point_place=(point.place_point or "").strip(),
        point_date=(point.date_point or "").strip(),
    )
    type_text = "Загрузка" if point.type_point == "loading" else "Выгрузка"
    type_emoji = "📦" if point.type_point == "loading" else "📤"
    status_labels = {"new": "новая", "process": "Выехал на точку", "registration": "Зарегистрировался", "load": "На воротах", "docs": "Забрал документы"}
    prompt_by_status = {
        "new": "⏱ Нажмите кнопку ниже, когда выедете на точку.",
        "process": "⏱ Когда зарегистрируетесь на точке — нажмите кнопку «Зарегистрировался».",
        "registration": "⏱ Когда поставите ТС на ворота — нажмите кнопку «Поставил на ворота».",
        "load": "⏱ Когда заберёте документы — нажмите кнопку «Забрал документы».",
        "docs": "⏱ Когда выедете с точки — нажмите кнопку «Выехал с точки».",
    }
    point_block = (
        f"↩️ Статус точки отменён. Текущий статус: {status_labels.get(to_status, to_status)}\n\n"
        f"Рейс: {_copy_code(route_id)}\n"
        f"{type_emoji} Тип точки: {type_text}\n"
        f"📅 Дата: {point.date_point}\n"
        f"📍 Место: {point.place_point}\n\n"
        f"{prompt_by_status.get(to_status, '')}"
    )
    await callback.message.edit_text(point_block, parse_mode="HTML")
    kb = {
        "new": get_start_point_specific_keyboard(route_id, point_id),
        "process": get_registration_point_specific_keyboard(route_id, point_id),
        "registration": get_proc_loading_specific_keyboard(route_id, point_id),
        "load": get_docs_point_specific_keyboard(route_id, point_id),
        "docs": get_end_point_specific_keyboard(route_id, point_id),
    }.get(to_status)
    await callback.message.answer("Выберите действие:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("accept_route_"))
async def accept_route_specific(
    callback: types.CallbackQuery,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    route_id = callback.data.split("_")[2]
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await callback.message.answer("❌ Рейс не найден")
        return
    if int(route.tg_id) != callback.from_user.id:
        await callback.message.answer("❌ Это не ваш рейс")
        return
    if route.status != "new":
        await callback.message.answer(f"❌ Рейс уже имеет статус: {'В процессе' if route.status == 'process' else 'Завершен'}")
        return
    user_process_routes = route_repository.get_routes_by_driver(callback.from_user.id, "process")
    if user_process_routes:
        await callback.message.answer(f"❌ У вас уже есть активный рейс: {user_process_routes[0].id}\nСначала завершите его.")
        return
    route_repository.update_status_route(route_id, "process")
    try:
        notifier = NotificationService(user_repository)
        await notifier.notify_admins_logistics_route_accepted(route_id, callback.from_user.id)
    except Exception:
        pass
    
    # Находим первую точку
    points = route.points.split(",") if route.points != "0" else []
    if points:
        try:
            first_point_id = int(points[0])
            first_point = route_repository.get_point_by_id(first_point_id)
            
            if first_point:
                type_text = "Загрузка" if first_point.type_point == "loading" else "Выгрузка"
                
                # Редактируем предыдущее сообщение
                await callback.message.edit_text(
                    f"✅ Рейс принят!\n\n"
                    f"Рейс: {_copy_code(route.id)}\n"
                    f"📊 Статус: В процессе 🚚",
                    parse_mode="HTML"
                )
                
                # Отправляем новое сообщение с первой точкой
                await callback.message.answer(
                    f"📍 Первая точка:\n\n"
                    f"Рейс: {_copy_code(route.id)}\n"
                    f"📦 Тип: {type_text}\n"
                    f"📅 Дата: {first_point.date_point}\n"
                    f"📍 Место: {first_point.place_point}\n\n"
                    f"Нажмите, когда выедете на точку:",
                    reply_markup=get_start_point_specific_keyboard(route_id, first_point_id),
                    parse_mode="HTML"
                )
                return
        except ValueError:
            pass
    
    await callback.message.edit_text(f"✅ Рейс {_copy_code(route_id)} принят!", parse_mode="HTML")

@router.callback_query(F.data.startswith("start_point_"))
async def start_point_specific(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    parts = callback.data.split("_")
    route_id = parts[2]
    point_id = int(parts[3])
    
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await callback.message.answer("❌ Рейс не найден")
        return
    
    if int(route.tg_id) != callback.from_user.id:
        await callback.message.answer("❌ Это не ваш рейс")
        return
    
    if route.status != "process":
        await callback.message.answer(f"❌ Рейс не в процессе. Статус: {route.status}")
        return
    
    point = route_repository.get_point_by_id(point_id)
    if not point or point.id_route != route_id:
        await callback.message.answer("❌ Точка не найдена")
        return
    
    wialon_data = await _get_vehicle_data_for_status_change(route)
    await _show_point_time_choice(callback, route_id, point_id, "process", wialon_data, state)
    await callback.answer()

@router.callback_query(F.data.startswith("registration_point_"))
async def registration_point_specific(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    parts = callback.data.split("_")
    route_id = parts[2]
    point_id = int(parts[3])
    
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await callback.message.answer("❌ Рейс не найден")
        return
    
    if int(route.tg_id) != callback.from_user.id:
        await callback.message.answer("❌ Это не ваш рейс")
        return
    
    if route.status != "process":
        await callback.message.answer(f"❌ Рейс не в процессе. Статус: {route.status}")
        return
    
    point = route_repository.get_point_by_id(point_id)
    if not point or point.id_route != route_id:
        await callback.message.answer("❌ Точка не найдена")
        return
    
    if point.status != "process":
        await callback.message.answer(f"❌ Точка уже обработана. Текущий статус: {point.status}")
        return
    
    wialon_data = await _get_vehicle_data_for_status_change(route)
    await _show_point_time_choice(callback, route_id, point_id, "registration", wialon_data, state)
    await callback.answer()


async def _apply_point_status_and_continue(
    callback_or_message,
    route_id: str,
    point_id: int,
    status: str,
    time_str: str,
    route_repository: RouteRepository,
    user_repository: UserRepository,
    wialon_data: dict | None = None,
):
    """Применить смену статуса точки с заданным временем и показать следующую клавиатуру."""
    lat = (wialon_data or {}).get("lat")
    lng = (wialon_data or {}).get("lng")
    odometer = (wialon_data or {}).get("odometer")
    prev_status = {"process": "new", "registration": "process", "load": "registration", "docs": "load", "success": "docs"}.get(status)
    updated = route_repository.update_point_status(
        point_id, status, time_str, lat=lat, lng=lng, odometer=odometer,
        expected_prev_status=prev_status,
    )
    if not updated:
        return  # Дубликат — уже обработано другим запросом
    point = route_repository.get_point_by_id(point_id)
    type_text = "Загрузка" if point.type_point == "loading" else "Выгрузка"
    type_emoji = "📦" if point.type_point == "loading" else "📤"
    coords_str = f"{lat:.6f}, {lng:.6f}" if lat is not None and lng is not None else None
    notification_service = NotificationService(user_repository)
    await notification_service.notify_about_status_point(
        route_id, status, "",
        point_time=time_str,
        point_type=type_text,
        point_address=point.place_point,
        point_date=point.date_point,
        point_coords=coords_str,
        point_odometer=odometer,
    )
    is_callback = hasattr(callback_or_message, "message") and hasattr(callback_or_message.message, "edit_text")
    send_edit = callback_or_message.message.edit_text if is_callback else None
    send_answer = callback_or_message.message.answer if is_callback else callback_or_message.reply

    if status == "process":
        if send_edit:
            await send_edit(
                f"🚗 Вы выехали на точку!\n\n"
                f"Рейс: {route_id}\n"
                f"{type_emoji} Тип: {type_text}\n"
                f"📅 Дата: {point.date_point}\n"
                f"📍 Место: {point.place_point}\n\n"
                f"📊 Статус: 🚗 Выехал"
            )
        else:
            await send_answer(
                f"🚗 Вы выехали на точку!\n\n"
                f"Рейс: {route_id}\n"
                f"{type_emoji} Тип: {type_text}\n"
                f"📅 Дата: {point.date_point}\n"
                f"📍 Место: {point.place_point}\n\n"
                f"📊 Статус: 🚗 Выехал"
            )
        await send_answer(
            f"📦 Тип: {type_text}\n"
            f"📍 Место: {point.place_point}\n\n"
            f"⏱ Когда зарегистрируетесь на точке — нажмите кнопку «Зарегистрировался».",
            reply_markup=get_registration_point_specific_keyboard(route_id, point_id)
        )
        return

    if status == "registration":
        if send_edit:
            await send_edit(
                f"📝 Вы зарегистрировались на точке!\n\n"
                f"Рейс: {route_id}\n"
                f"📍 Место: {point.place_point}\n\n"
                f"📊 Статус: 📝 Зарегистрирован"
            )
        else:
            await send_answer(
                f"📝 Вы зарегистрировались на точке!\n\n"
                f"Рейс: {route_id}\n"
                f"📍 Место: {point.place_point}\n\n"
                f"📊 Статус: 📝 Зарегистрирован"
            )
        await send_answer(
            f"✅ Регистрация завершена\n\n"
            f"📍 Место: {point.place_point}\n\n"
            f"Нажмите, когда поставите на ворота:",
            reply_markup=get_proc_loading_specific_keyboard(route_id, point_id)
        )
        return

    if status == "load":
        if send_edit:
            await send_edit(
                f"🚪 Вы поставили на ворота!\n\n"
                f"Рейс: {route_id}\n"
                f"📍 Место: {point.place_point}\n\n"
                f"📊 Статус: 🚪 На воротах"
            )
        else:
            await send_answer(
                f"🚪 Вы поставили на ворота!\n\n"
                f"Рейс: {route_id}\n"
                f"📍 Место: {point.place_point}\n\n"
                f"📊 Статус: 🚪 На воротах"
            )
        await send_answer(
            f"✅ На воротах\n\n"
            f"📍 Место: {point.place_point}\n\n"
            f"Нажмите, когда заберете документы:",
            reply_markup=get_docs_point_specific_keyboard(route_id, point_id)
        )
        return

    if status == "docs":
        if send_edit:
            await send_edit(
                f"📋 Вы забрали документы!\n\n"
                f"Рейс: {route_id}\n"
                f"📍 Место: {point.place_point}\n\n"
                f"📊 Статус: 📋 Документы получены"
            )
        else:
            await send_answer(
                f"📋 Вы забрали документы!\n\n"
                f"Рейс: {route_id}\n"
                f"📍 Место: {point.place_point}\n\n"
                f"📊 Статус: 📋 Документы получены"
            )
        route = route_repository.get_by_id_str(route_id)
        points = (route.points or "0").split(",") if route else []
        current_found = False
        for point_str in points:
            try:
                check_point_id = int(point_str.strip())
                if check_point_id == point_id:
                    current_found = True
                    continue
                if current_found:
                    next_point = route_repository.get_point_by_id(check_point_id)
                    if next_point and next_point.status == "new":
                        route_repository.update_point_status(point_id, "success", time_str, expected_prev_status="docs")
                        type_text_n = "Загрузка" if next_point.type_point == "loading" else "Выгрузка"
                        type_emoji_n = "📦" if next_point.type_point == "loading" else "📤"
                        await send_answer(
                            f"📍 Следующая точка:\n\n"
                            f"Рейс: {route_id}\n"
                            f"{type_emoji_n} Тип: {type_text_n}\n"
                            f"📅 Дата: {next_point.date_point}\n"
                            f"📍 Место: {next_point.place_point}\n\n"
                            f"Нажмите, когда выедете на следующую точку:",
                            reply_markup=get_start_point_specific_keyboard(route_id, check_point_id)
                        )
                        return
            except ValueError:
                continue
        route_repository.update_point_status(point_id, "success", time_str, expected_prev_status="docs")
        route_repository.update_status_route(route_id, "success")
        await notification_service.notify_about_status_point(
            route_id, "completed", "", point_time=time_str,
            point_type=type_text, point_address=point.place_point, point_date=point.date_point
        )
        await send_answer(
            f"✅ Рейс успешно завершен!\n\n"
            f"N рейса: {route_id}\n"
            f"📊 Статус: ✅ Завершен"
        )
        await send_answer(f"🎉 Рейс {_copy_code(route_id)} завершен!\nСпасибо за работу!", parse_mode="HTML")
        return

    if status == "success":
        if send_edit:
            await send_edit(
                f"🏁 Вы выехали с точки!\n\n"
                f"Рейс: {route_id}\n"
                f"📍 Место: {point.place_point}\n\n"
                f"📊 Статус: ✅ Завершена"
            )
        else:
            await send_answer(
                f"🏁 Вы выехали с точки!\n\n"
                f"Рейс: {route_id}\n"
                f"📍 Место: {point.place_point}\n\n"
                f"📊 Статус: ✅ Завершена"
            )
        route = route_repository.get_by_id_str(route_id)
        points = (route.points or "0").split(",") if route else []
        for point_str in points:
            try:
                next_point_id = int(point_str.strip())
                next_point = route_repository.get_point_by_id(next_point_id)
                if next_point and next_point.status == "new":
                    type_text_n = "Загрузка" if next_point.type_point == "loading" else "Выгрузка"
                    type_emoji_n = "📦" if next_point.type_point == "loading" else "📤"
                    await send_answer(
                        f"📍 Следующая точка:\n\n"
                        f"Рейс: {route_id}\n"
                        f"{type_emoji_n} Тип: {type_text_n}\n"
                        f"📅 Дата: {next_point.date_point}\n"
                        f"📍 Место: {next_point.place_point}\n\n"
                        f"Нажмите, когда выедете на следующую точку:",
                        reply_markup=get_start_point_specific_keyboard(route_id, next_point_id)
                    )
                    return
            except ValueError:
                continue
        await send_answer(
            f"🏁 Все точки рейса выполнены!\n\n"
            f"Рейс: {route_id}\n\n"
            f"Вы можете завершить рейс:",
            reply_markup=get_route_end_specific_keyboard(route_id)
        )


def _needs_odometer_confirmation(status: str) -> bool:
    """Для process, registration и docs требуется подтверждение/ввод одометра."""
    return status in ("process", "registration", "docs")


async def _show_odometer_step(callback_or_message, state: FSMContext, route_id: str, point_id: int, status: str, wialon_data: dict | None):
    """Показать шаг подтверждения одометра для process и docs."""
    odometer_from_wialon = (wialon_data or {}).get("odometer")
    if odometer_from_wialon:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"point_odometer_ok_{route_id}_{point_id}_{status}",
            style="success",
        ))
        builder.row(InlineKeyboardButton(
            text="✏️ Ввести вручную",
            callback_data=f"point_odometer_manual_{route_id}_{point_id}_{status}",
        ))
        text = f"📏 Одометр из Wialon: {odometer_from_wialon}\n\nПодтвердите корректность или введите вручную:"
    else:
        await state.update_data(
            pending_point_route_id=route_id,
            pending_point_id=point_id,
            pending_point_status=status,
            pending_wialon_data=wialon_data,
        )
        await state.set_state(DriverPointTimeState.odometer_manual)
        text = "📏 Введите одометр вручную (км):"
        if hasattr(callback_or_message, "message"):
            await callback_or_message.message.edit_text(text)
        else:
            await callback_or_message.reply(text)
        return
    if hasattr(callback_or_message, "message"):
        await callback_or_message.message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await callback_or_message.reply(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("point_time_wialon_"))
async def point_time_wialon_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    """Сохранить время из Wialon (выбрано водителем)."""
    parts = callback.data.split("_")
    if len(parts) != 6:
        await callback.answer("Ошибка.")
        return
    route_id = parts[3]
    point_id = int(parts[4])
    status = parts[5]
    data = await state.get_data()
    time_str = data.get("pending_point_time")
    wialon_data = data.get("pending_wialon_data")
    if not time_str or status not in ("process", "registration", "load", "docs", "success"):
        await callback.answer("Сессия истекла.")
        return
    if _needs_odometer_confirmation(status):
        await state.update_data(
            pending_point_time=time_str,
            pending_point_route_id=route_id,
            pending_point_id=point_id,
            pending_point_status=status,
            pending_wialon_data=wialon_data,
        )
        await _show_odometer_step(callback, state, route_id, point_id, status, wialon_data)
        await callback.answer()
        return
    await state.clear()
    await _apply_point_status_and_continue(
        callback, route_id, point_id, status, time_str, route_repository, user_repository,
        wialon_data=wialon_data,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("point_odometer_ok_"))
async def point_odometer_ok_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    """Одометр корректный — применить смену статуса."""
    parts = callback.data.replace("point_odometer_ok_", "").split("_", 2)
    if len(parts) != 3:
        await callback.answer("Ошибка.")
        return
    route_id, point_id, status = parts[0], int(parts[1]), parts[2]
    data = await state.get_data()
    time_str = data.get("pending_point_time")
    wialon_data = data.get("pending_wialon_data")
    await state.clear()
    if not time_str or status not in ("process", "registration", "docs"):
        await callback.answer("Сессия истекла.")
        return
    await _apply_point_status_and_continue(
        callback, route_id, point_id, status, time_str, route_repository, user_repository,
        wialon_data=wialon_data,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("point_odometer_manual_"))
async def point_odometer_manual_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    """Запросить ввод одометра вручную."""
    parts = callback.data.replace("point_odometer_manual_", "").split("_", 2)
    if len(parts) != 3:
        await callback.answer("Ошибка.")
        return
    route_id, point_id, status = parts[0], int(parts[1]), parts[2]
    data = await state.get_data()
    await state.update_data(
        pending_point_route_id=route_id,
        pending_point_id=point_id,
        pending_point_status=status,
        pending_wialon_data=data.get("pending_wialon_data"),
    )
    await state.set_state(DriverPointTimeState.odometer_manual)
    await callback.message.edit_text("📏 Введите одометр вручную (км):")
    await callback.answer()


@router.callback_query(F.data.startswith("point_time_keep_"))
async def point_time_keep_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    """Сохранить по МСК (московское время)."""
    parts = callback.data.split("_")
    if len(parts) != 6:
        await callback.answer("Ошибка.")
        return
    route_id = parts[3]
    point_id = int(parts[4])
    status = parts[5]
    data = await state.get_data()
    time_str = data.get("pending_point_time") or get_current_moscow_time_str()
    await state.update_data(pending_point_time=time_str)
    if status not in ("process", "registration", "load", "docs", "success"):
        await callback.answer("Неизвестный статус.")
        return
    if " (ВВ)" not in time_str and " (Мск)" not in time_str and " (🛰️ " not in time_str:
        time_str = time_str + MOSCOW_TIME_SUFFIX
        await state.update_data(pending_point_time=time_str)
    if _needs_odometer_confirmation(status):
        await state.update_data(
            pending_point_route_id=route_id,
            pending_point_id=point_id,
            pending_point_status=status,
            pending_wialon_data=None,
        )
        await _show_odometer_step(callback, state, route_id, point_id, status, None)
        await callback.answer()
        return
    await state.clear()
    await _apply_point_status_and_continue(
        callback, route_id, point_id, status, time_str, route_repository, user_repository,
        wialon_data=None,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("point_time_manual_"))
async def point_time_manual_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    parts = callback.data.split("_")
    if len(parts) != 6:
        await callback.answer("Ошибка.")
        return
    route_id = parts[3]
    point_id = int(parts[4])
    status = parts[5]
    await state.update_data(
        pending_point_route_id=route_id,
        pending_point_id=point_id,
        pending_point_status=status,
    )
    await state.set_state(DriverPointTimeState.manual_time)
    await callback.message.edit_text(
        "Введите время смены статуса в формате дд.мм.гггг чч:мм (например 26.02.2026 14:30):"
    )
    await callback.answer()


@router.message(DriverPointTimeState.odometer_manual)
async def point_odometer_manual_entered(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    """Ввод одометра вручную (для process и docs)."""
    data = await state.get_data()
    route_id = data.get("pending_point_route_id")
    point_id = data.get("pending_point_id")
    status = data.get("pending_point_status")
    time_str = data.get("pending_point_time")
    wialon_data = data.get("pending_wialon_data")
    await state.clear()
    if not route_id or not point_id or not time_str:
        await message.reply("Сессия истекла.", reply_markup=get_driver_routes_menu_keyboard())
        return
    if status not in ("process", "registration", "docs"):
        await message.reply("Ошибка статуса.", reply_markup=get_driver_routes_menu_keyboard())
        return
    raw = (message.text or "").strip()
    if not raw:
        await message.reply("Введите значение одометра (км):")
        return
    odometer = raw + " км" if "км" not in raw.lower() else raw
    wialon_with_odometer = dict(wialon_data) if wialon_data else {}
    wialon_with_odometer["odometer"] = odometer
    await _apply_point_status_and_continue(
        message, route_id, point_id, status, time_str, route_repository, user_repository,
        wialon_data=wialon_with_odometer,
    )


@router.message(DriverPointTimeState.manual_time)
async def point_time_manual_entered(
    message: types.Message,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    data = await state.get_data()
    route_id = data.get("pending_point_route_id")
    point_id = data.get("pending_point_id")
    status = data.get("pending_point_status")
    await state.clear()
    if not route_id or not point_id:
        await message.reply("Сессия истекла. Выберите действие заново.", reply_markup=get_driver_routes_menu_keyboard())
        return
    if status not in ("process", "registration", "load", "docs", "success"):
        await message.reply("Неизвестный статус. Выберите действие заново.", reply_markup=get_driver_routes_menu_keyboard())
        return
    text = (message.text or "").strip()
    try:
        dt = datetime.strptime(text, "%d.%m.%Y %H:%M")
        time_str = dt.strftime("%d.%m.%Y %H:%M") + MANUAL_TIME_SUFFIX
    except ValueError:
        await message.reply("Неверный формат. Введите дд.мм.гггг чч:мм (например 26.02.2026 14:30):")
        return
    if _needs_odometer_confirmation(status):
        await state.update_data(
            pending_point_time=time_str,
            pending_point_route_id=route_id,
            pending_point_id=point_id,
            pending_point_status=status,
            pending_wialon_data=None,
        )
        await state.set_state(DriverPointTimeState.odometer_manual)
        await message.reply("📏 Введите одометр вручную (км):")
        return
    await state.clear()
    await _apply_point_status_and_continue(
        message, route_id, point_id, status, time_str, route_repository, user_repository,
        wialon_data=None,
    )


@router.callback_query(F.data.startswith("point_time_cancel_"))
async def point_time_cancel_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
):
    """Отмена выбора времени: вернуть клавиатуру текущего шага без смены статуса."""
    parts = callback.data.split("_")
    if len(parts) != 6:
        await callback.answer("Ошибка.")
        return
    route_id = parts[3]
    point_id = int(parts[4])
    status = parts[5]
    await state.clear()
    route = route_repository.get_by_id_str(route_id)
    if not route or int(route.tg_id) != callback.from_user.id:
        await callback.answer("Рейс не найден или это не ваш рейс.")
        return
    point = route_repository.get_point_by_id(point_id)
    if not point or point.id_route != route_id:
        await callback.answer("Точка не найдена.")
        return
    labels = {
        "process": ("⏱ Нажмите кнопку ниже, когда выедете на точку.", get_start_point_specific_keyboard),
        "registration": ("⏱ Когда зарегистрируетесь на точке — нажмите кнопку «Зарегистрировался».", get_registration_point_specific_keyboard),
        "load": ("⏱ Когда поставите ТС на ворота — нажмите кнопку «Поставил на ворота».", get_proc_loading_specific_keyboard),
        "docs": ("⏱ Когда заберёте документы — нажмите кнопку «Забрал документы».", get_docs_point_specific_keyboard),
        "success": ("⏱ Когда выедете с точки — нажмите кнопку «Выехал с точки».", get_end_point_specific_keyboard),
    }
    text, get_kb = labels.get(status, (None, None))
    if not text:
        await callback.answer("Неизвестный статус.")
        return
    await callback.message.edit_text(
        f"↩️ Ввод отменён.\n\n"
        f"Рейс: {route_id}\n"
        f"📍 Место: {point.place_point}\n\n"
        f"{text}",
        reply_markup=get_kb(route_id, point_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("proc_loading_"))
async def proc_loading_specific(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    parts = callback.data.split("_")
    route_id = parts[2]
    point_id = int(parts[3])
    
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await callback.message.answer("❌ Рейс не найден")
        return
    
    if int(route.tg_id) != callback.from_user.id:
        await callback.message.answer("❌ Это не ваш рейс")
        return
    
    if route.status != "process":
        await callback.message.answer(f"❌ Рейс не в процессе. Статус: {route.status}")
        return
    
    point = route_repository.get_point_by_id(point_id)
    if not point or point.id_route != route_id:
        await callback.message.answer("❌ Точка не найдена")
        return
    
    if point.status != "registration":
        await callback.message.answer(f"❌ Точка уже обработана. Текущий статус: {point.status}")
        return
    
    wialon_data = await _get_vehicle_data_for_status_change(route)
    await _show_point_time_choice(callback, route_id, point_id, "load", wialon_data, state)
    await callback.answer()

@router.callback_query(F.data.startswith("docs_point_"))
async def docs_point_specific(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    parts = callback.data.split("_")
    route_id = parts[2]
    point_id = int(parts[3])
    
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await callback.message.answer("❌ Рейс не найден")
        return
    
    if int(route.tg_id) != callback.from_user.id:
        await callback.message.answer("❌ Это не ваш рейс")
        return
    
    if route.status != "process":
        await callback.message.answer(f"❌ Рейс не в процессе. Статус: {route.status}")
        return
    
    point = route_repository.get_point_by_id(point_id)
    if not point or point.id_route != route_id:
        await callback.message.answer("❌ Точка не найдена")
        return
    
    if point.status != "load":
        await callback.message.answer(f"❌ Точка уже обработана. Текущий статус: {point.status}")
        return
    
    wialon_data = await _get_vehicle_data_for_status_change(route)
    await _show_point_time_choice(callback, route_id, point_id, "docs", wialon_data, state)
    await callback.answer()

@router.callback_query(F.data.startswith("end_point_"))
async def end_point_specific(
    callback: types.CallbackQuery,
    state: FSMContext,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    parts = callback.data.split("_")
    route_id = parts[2]
    point_id = int(parts[3])
    
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await callback.message.answer("❌ Рейс не найден")
        return
    
    if int(route.tg_id) != callback.from_user.id:
        await callback.message.answer("❌ Это не ваш рейс")
        return
    
    if route.status != "process":
        await callback.message.answer(f"❌ Рейс не в процессе. Статус: {route.status}")
        return
    
    point = route_repository.get_point_by_id(point_id)
    if not point or point.id_route != route_id:
        await callback.message.answer("❌ Точка не найдена")
        return
    
    if point.status != "docs":
        await callback.message.answer(f"❌ Точка уже обработана. Текущий статус: {point.status}")
        return
    
    wialon_data = await _get_vehicle_data_for_status_change(route)
    await _show_point_time_choice(callback, route_id, point_id, "success", wialon_data, state)
    await callback.answer()

@router.callback_query(F.data.startswith("end_route_"))
async def end_route_specific(callback: types.CallbackQuery, route_repository: RouteRepository, user_repository: UserRepository):
    route_id = callback.data.split("_")[2]
    
    route = route_repository.get_by_id_str(route_id)
    if not route:
        await callback.message.answer("❌ Рейс не найден")
        return
    
    # Проверяем, что этот рейс принадлежит текущему пользователю
    if int(route.tg_id) != callback.from_user.id:
        await callback.message.answer("❌ Это не ваш рейс")
        return
    
    # Проверяем, все ли точки рейса завершены (пропускаем 0 и пустые; только точки с id_route == route_id)
    points_raw = (route.points or "0").split(",")
    points = [s.strip() for s in points_raw if s.strip() and s.strip() != "0"]
    all_points_completed = True
    
    for point_str in points:
        try:
            point_id = int(point_str)
            point = route_repository.get_point_by_id(point_id)
            if point and str(point.id_route) == str(route_id) and point.status != "success":
                all_points_completed = False
                break
        except ValueError:
            continue
    
    if not all_points_completed:
        await callback.message.answer("❌ Не все точки рейса завершены. Завершите все точки перед завершением рейса.")
        return
    
    route_repository.update_status_route(route_id, "success")
    
    # Уведомляем администраторов
    notification_service = NotificationService(user_repository)
    await notification_service.notify_about_status_point(route_id, "completed", "")
    
    # Редактируем предыдущее сообщение
    await callback.message.edit_text(
        f"✅ Рейс успешно завершен!\n\n"
        f"N рейса: {_copy_code(route_id)}\n"
        f"📊 Статус: ✅ Завершен"
    )
    
    # Отправляем финальное сообщение
    await callback.message.answer(
        f"🎉 Рейс {route_id} завершен!\n"
        f"Спасибо за работу!"
    )