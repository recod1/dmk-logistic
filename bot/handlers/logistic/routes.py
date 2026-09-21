# handlers/logistic/routes.py
import html
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from utils.telegram_helpers import copy_link_fio, copy_link_text
from keyboards.admin_kb import (
    get_routes_keyboard,
    get_admin_main_keyboard,
)
from database.repositories.route_repository import RouteRepository
from database.repositories.user_repository import UserRepository

router = Router()


@router.message(F.text == "🚚 Рейсы")
async def menu_routes(message: types.Message):
    await message.reply("🚚 Рейсы", reply_markup=get_routes_keyboard())


@router.message(F.text == "🚚 Все рейсы")
async def show_all_routes(
    message: types.Message,
    route_repository: RouteRepository,
    user_repository: UserRepository,
):
    routes = route_repository.get_all()

    if not routes:
        await message.reply("📭 Нет созданных рейсов")
        return

    text = "📊 Все рейсы:\n\n"

    status_texts = {
        "new": "Не принят",
        "process": "В процессе",
        "success": "Завершен",
    }

    for route in routes:
        driver = user_repository.get_by_tg_id(route.tg_id)
        driver_name = driver.name if driver else "Неизвестно"

        status_emoji = {
            "new": "📋",
            "process": "🚚",
            "success": "✅",
        }.get(route.status, "❓")

        human_status = status_texts.get(route.status, route.status)

        text += (
            f"{status_emoji} Рейс: {route.id}\n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"📊 Статус: {human_status}\n"
        )
        if route.number_auto:
            text += f"🚚 ТС: {copy_link_text(route.number_auto)}\n"
        if getattr(route, 'trailer_number', None):
            text += f"🛞 Прицеп: {copy_link_text(route.trailer_number)}\n"
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

    await message.reply(text, parse_mode="HTML")


@router.message(F.text == "➕ Создать рейс")
async def create_route(message: types.Message):
    await message.reply("❌ Создание рейсов доступно только администраторам")


# @router.message(F.text == "↩️ Назад")
# async def exit_to_main(message: types.Message):
#     await message.reply("Назад", reply_markup=get_admin_main_keyboard())