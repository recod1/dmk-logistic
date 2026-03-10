import html
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.telegram_helpers import copy_link_fio
from keyboards.role_kb import get_main_keyboard_by_role
from keyboards.admin_kb import (
    get_repairs_keyboard,
    get_repairs_by_status_keyboard,
    get_admin_main_keyboard,
)

from keyboards.driver_kb import (
    get_ticket_confirm_driver_keyboard,
    get_ticket_proc_repair_driver_keyboard,
    get_ticket_conf_repair_driver_keyboard,
    get_ticket_success_repair_driver_keyboard
)
from states.repair_states import (
    AdminRepairState,
    AutoSearchState,
    RepairSuccState,
    RepairDeleteState,
    RepairReassignState,
    RepairCancelState,
    RepairEditState,
    RepairStatusMenuState,
)
from database.repositories.repair_repository import RepairRepository
from database.repositories.user_repository import UserRepository
from config.settings import RepairStatus
from core.bot import create_bot

router = Router()


async def _back_from_repair_flow(message: types.Message, state: FSMContext):
    """Выход из любого сценария ремонтов по кнопке Назад."""
    await state.clear()
    await message.reply("Операция отменена.", reply_markup=get_repairs_keyboard())


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(RepairDeleteState))
async def back_from_repair_delete(message: types.Message, state: FSMContext):
    await _back_from_repair_flow(message, state)


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(RepairReassignState))
async def back_from_repair_reassign(message: types.Message, state: FSMContext):
    await _back_from_repair_flow(message, state)


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(RepairCancelState))
async def back_from_repair_cancel(message: types.Message, state: FSMContext):
    await _back_from_repair_flow(message, state)


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(RepairEditState))
async def back_from_repair_edit(message: types.Message, state: FSMContext):
    await _back_from_repair_flow(message, state)


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(AdminRepairState))
async def back_from_admin_repair(message: types.Message, state: FSMContext):
    await _back_from_repair_flow(message, state)


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(AutoSearchState))
async def back_from_auto_search(message: types.Message, state: FSMContext):
    await _back_from_repair_flow(message, state)


@router.message(F.text.in_(["↩️ Назад", "🔙 Назад"]), StateFilter(RepairStatusMenuState))
async def back_from_repair_status_menu(message: types.Message, state: FSMContext):
    """Возврат из подменю «Заявки по статусам» в меню ремонтов"""
    await state.clear()
    await message.reply("🛠 Заявки на ремонт", reply_markup=get_repairs_keyboard())


@router.message(F.text == "📋 Заявки по статусам")
async def menu_repairs_by_status(message: types.Message, state: FSMContext):
    """Показать подменю выбора заявок по статусам"""
    await state.set_state(RepairStatusMenuState.viewing)
    await message.reply("Выберите статус заявок:", reply_markup=get_repairs_by_status_keyboard())


def get_ticket_repair_keyboard(ticket_id: int):
    """Клавиатура для обработки конкретной заявки"""
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="🔧 Обработать", 
        callback_data=f"ticket_repair_{ticket_id}"
    ))
    return builder.as_markup()

def get_ticket_confirm_admin_keyboard(ticket_id: int):
    """Клавиатура для подтверждения окончания ремонта администратором"""
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="✅ Подтвердить окончание", 
        callback_data=f"ticket_success_admin_{ticket_id}"
    ))
    return builder.as_markup()

@router.message(F.text == "🛠 Заявки на ремонт")
async def menu_repairs(message: types.Message):
    await message.reply("🛠 Заявки на ремонт", reply_markup=get_repairs_keyboard())

@router.message(F.text == "🔧 Обработать заявку")
async def work_repair_ticket(message: types.Message, state: FSMContext):
    await state.set_state(AdminRepairState.ticket_id)
    await message.reply("Введите номер заявки", reply_markup=get_repairs_keyboard())

# ДОБАВЛЯЕМ обработчик для состояния AdminRepairState.ticket_id
@router.message(AdminRepairState.ticket_id)
async def process_ticket_id_from_menu(message: types.Message, state: FSMContext):
    """Обработка номера заявки, введенного из меню"""
    try:
        ticket_id = int(message.text.strip())
        await state.update_data(ticket_id=ticket_id)
        await state.set_state(AdminRepairState.date)
        await message.reply(f"Обработка заявки №{ticket_id}\nВведите дату ремонта (дд.мм.гггг)")
    except ValueError:
        await message.reply("❌ Неверный формат номера заявки. Введите число.")
        await state.clear()

@router.message(F.text == "🔍 Найти заявки ТС")
async def search_repairs_by_auto(message: types.Message, state: FSMContext):
    await state.set_state(AutoSearchState.number_auto)
    await message.reply("Введите номер ТС", reply_markup=get_repairs_keyboard())



@router.message(F.text == "🆕 Новые")
async def show_new_repairs(
    message: types.Message,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    repairs = repair_repository.get_by_status(RepairStatus.NEW)
    
    if not repairs:
        await message.reply("Нет новых заявок", reply_markup=get_repairs_by_status_keyboard())
        return
    
    all_text_repair = "--- Новые заявки ---\n\n"
    
    for repair in repairs:
        driver = user_repository.get_by_tg_id(int(repair.tg_id))
        driver_name = driver.name if driver else "Неизвестно"
        all_text_repair += (
            f"#️⃣ Номер заявки: {repair.id_ticket} \n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"🚛 Номер ТС: {repair.number_auto} \n"
            f"📝 Описание неисправности: {repair.malfunction} \n\n"
        )
        
        await message.answer(
            f"#️⃣ Номер заявки: {repair.id_ticket} \n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"🚛 Номер ТС: {repair.number_auto} \n"
            f"📝 Описание неисправности: {repair.malfunction}",
            reply_markup=get_ticket_repair_keyboard(repair.id_ticket)
        )
    
    await message.reply(all_text_repair, reply_markup=get_repairs_by_status_keyboard(), parse_mode="HTML")

@router.message(F.text == "✉️ Ожидают подтверждения")
async def show_process_repairs(
    message: types.Message,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    repairs = repair_repository.get_by_status(RepairStatus.PROCESS)
    
    if not repairs:
        await message.reply("Нет заявок, ожидающих подтверждения", reply_markup=get_repairs_by_status_keyboard())
        return
    
    all_text_repair = "--- Заявки, ожидающие подтверждения ---\n\n"
    
    for repair in repairs:
        driver = user_repository.get_by_tg_id(int(repair.tg_id))
        driver_name = driver.name if driver else "Неизвестно"
        all_text_repair += (
            f"#️⃣ Номер заявки: {repair.id_ticket} \n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"🚛 Номер ТС: {repair.number_auto} \n"
            f"📝 Описание неисправности: {repair.malfunction} \n\n"
        )
    
    await message.reply(all_text_repair, reply_markup=get_repairs_by_status_keyboard(), parse_mode="HTML")

@router.message(F.text == "📨 Ожидают ремонта")
async def show_confirm_repairs(
    message: types.Message,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    repairs = repair_repository.get_by_status(RepairStatus.CONFIRM)
    
    if not repairs:
        await message.reply("Нет заявок, ожидающих ремонта", reply_markup=get_repairs_by_status_keyboard())
        return
    
    all_text_repair = "--- Заявки, ожидающие ремонта ---\n\n"
    
    for repair in repairs:
        driver = user_repository.get_by_tg_id(int(repair.tg_id))
        driver_name = driver.name if driver else "Неизвестно"
        all_text_repair += (
            f"#️⃣ Номер заявки: {repair.id_ticket} \n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"🚛 Номер ТС: {repair.number_auto} \n"
            f"📝 Описание неисправности: {repair.malfunction} \n\n"
        )
    
    await message.reply(all_text_repair, reply_markup=get_repairs_by_status_keyboard(), parse_mode="HTML")

@router.message(F.text == "🛻 Выехали на ремонт")
async def show_proc_repair_repairs(
    message: types.Message,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    repairs = repair_repository.get_by_status(RepairStatus.PROC_REPAIR)
    
    if not repairs:
        await message.reply("Нет заявок, в процессе ремонта", reply_markup=get_repairs_by_status_keyboard())
        return
    
    all_text_repair = "--- Заявки, в процессе ремонта ---\n\n"
    
    for repair in repairs:
        driver = user_repository.get_by_tg_id(int(repair.tg_id))
        driver_name = driver.name if driver else "Неизвестно"
        all_text_repair += (
            f"#️⃣ Номер заявки: {repair.id_ticket} \n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"🚛 Номер ТС: {repair.number_auto} \n"
            f"📝 Описание неисправности: {repair.malfunction} \n\n"
        )
    
    await message.reply(all_text_repair, reply_markup=get_repairs_by_status_keyboard(), parse_mode="HTML")

@router.message(F.text == "🛠 Отремонтированы")
async def show_conf_repair_repairs(
    message: types.Message,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    repairs = repair_repository.get_by_status(RepairStatus.CONF_REPAIR)
    
    if not repairs:
        await message.reply("Нет заявок, после ремонта", reply_markup=get_repairs_by_status_keyboard())
        return
    
    all_text_repair = "--- Отремонтированные заявки ---\n\n"
    
    for repair in repairs:
        driver = user_repository.get_by_tg_id(int(repair.tg_id))
        driver_name = driver.name if driver else "Неизвестно"
        all_text_repair += (
            f"#️⃣ Номер заявки: {repair.id_ticket} \n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"🚛 Номер ТС: {repair.number_auto} \n"
            f"📝 Описание неисправности: {repair.malfunction} \n\n"
        )
        
        await message.answer(
            f"#️⃣ Номер заявки: {repair.id_ticket} \n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"🚛 Номер ТС: {repair.number_auto} \n"
            f"📝 Описание неисправности: {repair.malfunction}",
            reply_markup=get_ticket_confirm_admin_keyboard(repair.id_ticket)
        )
    
    await message.reply(all_text_repair, reply_markup=get_repairs_by_status_keyboard(), parse_mode="HTML")

@router.message(F.text == "✅ Завершены")
async def show_success_repairs(
    message: types.Message,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    repairs = repair_repository.get_by_status(RepairStatus.SUCCESS)
    
    if not repairs:
        await message.reply("Нет завершенных заявок", reply_markup=get_repairs_by_status_keyboard())
        return
    
    all_text_repair = "--- Завершенные заявки ---\n\n"
    
    for repair in repairs:
        driver = user_repository.get_by_tg_id(int(repair.tg_id))
        driver_name = driver.name if driver else "Неизвестно"
        all_text_repair += (
            f"#️⃣ Номер заявки: {repair.id_ticket} \n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"🚛 Номер ТС: {repair.number_auto} \n"
            f"📝 Описание неисправности: {repair.malfunction} \n\n"
        )
    
    await message.reply(all_text_repair, reply_markup=get_repairs_by_status_keyboard(), parse_mode="HTML")


# Константы для постраничного вывода
REPAIRS_PAGE_SIZE = 10
TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def _format_repair_line(repair, user_repository: UserRepository) -> str:
    driver = user_repository.get_by_tg_id(int(repair.tg_id))
    driver_name = driver.name if driver else "Неизвестно"
    return (
        f"#️⃣ {repair.id_ticket} | ТС: {html.escape(repair.number_auto)} | 👤 {copy_link_fio(driver_name)}\n"
        f"   📝 {repair.malfunction}\n"
    )


async def _send_repairs_paginated(repairs, title: str, user_repository, send_func, reply_markup=None):
    """Отправляет список заявок постранично."""
    if not repairs:
        return
    total = len(repairs)
    for i in range(0, total, REPAIRS_PAGE_SIZE):
        chunk = repairs[i : i + REPAIRS_PAGE_SIZE]
        page = i // REPAIRS_PAGE_SIZE + 1
        total_pages = (total + REPAIRS_PAGE_SIZE - 1) // REPAIRS_PAGE_SIZE
        page_title = f"{title}" if total_pages <= 1 else f"{title} (стр. {page}/{total_pages})"
        lines = [page_title, ""]
        for r in chunk:
            lines.append(_format_repair_line(r, user_repository))
        text = "\n".join(lines)
        if len(text) > TELEGRAM_MAX_MESSAGE_LENGTH:
            for r in chunk:
                text_single = f"{page_title}\n\n" + _format_repair_line(r, user_repository)
                await send_func(text_single, reply_markup=None)
        else:
            use_markup = reply_markup if (i + len(chunk)) >= total else None
            await send_func(text, reply_markup=use_markup)


@router.message(F.text == "❌ Отмененные")
async def show_cancelled_repairs(
    message: types.Message,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    repairs = repair_repository.get_by_status(RepairStatus.CANCELLED)
    if not repairs:
        await message.reply("Нет отменённых заявок", reply_markup=get_repairs_by_status_keyboard())
        return

    async def _send(text: str, reply_markup=None):
        await message.reply(text, reply_markup=reply_markup or get_repairs_by_status_keyboard(), parse_mode="HTML")
    await _send_repairs_paginated(
        repairs, "❌ Отменённые заявки на ремонт", user_repository, _send, get_repairs_by_status_keyboard()
    )


# --- Удаление заявки ---

def _get_delete_repair_keyboard(ticket_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="✅ Подтвердить удаление", callback_data=f"confirm_delete_repair_{ticket_id}"),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_repair"),
    )
    return builder.as_markup()


@router.message(F.text == "🗑 Удалить заявку")
async def delete_repair_start(message: types.Message, state: FSMContext):
    await state.set_state(RepairDeleteState.ticket_id)
    await message.reply("Введите номер заявки на ремонт для удаления:", reply_markup=get_repairs_keyboard())


@router.message(RepairDeleteState.ticket_id)
async def delete_repair_ticket_id(
    message: types.Message,
    state: FSMContext,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    try:
        ticket_id = int(message.text.strip())
    except ValueError:
        await message.reply("❌ Неверный формат. Введите число — номер заявки.", reply_markup=get_repairs_keyboard())
        await state.clear()
        return
    repair = repair_repository.get_by_ticket_id(ticket_id)
    if not repair:
        await state.clear()
        await message.reply(f"Заявка №{ticket_id} не найдена.", reply_markup=get_repairs_keyboard())
        return
    driver = user_repository.get_by_tg_id(int(repair.tg_id))
    driver_name = driver.name if driver else "Неизвестно"
    text = (
        f"🗑 Удаление заявки №{ticket_id}\n\n"
        f"🚛 ТС: {repair.number_auto}\n"
        f"👤 Водитель: {copy_link_fio(driver_name)}\n"
        f"📝 {repair.malfunction}\n\n"
        f"Удалить заявку?"
    )
    await message.reply(text, reply_markup=_get_delete_repair_keyboard(ticket_id), parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data.startswith("confirm_delete_repair_"))
async def confirm_delete_repair(callback: types.CallbackQuery, repair_repository: RepairRepository):
    ticket_id = int(callback.data.replace("confirm_delete_repair_", ""))
    ok = repair_repository.delete(ticket_id)
    if ok:
        await callback.message.edit_text(f"✅ Заявка №{ticket_id} удалена.")
    else:
        await callback.message.edit_text(f"❌ Не удалось удалить заявку №{ticket_id}.")
    await callback.answer()


@router.callback_query(F.data == "cancel_delete_repair")
async def cancel_delete_repair(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ Удаление отменено.")
    await callback.answer()


# --- Переназначение заявки ---

def _get_reassign_repair_keyboard(ticket_id: int, new_driver_tg_id: str):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"confirm_reassign_repair_{ticket_id}_{new_driver_tg_id}",
        ),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_reassign_repair"),
    )
    return builder.as_markup()


@router.message(F.text == "🔄 Переназначить заявку")
async def reassign_repair_start(message: types.Message, state: FSMContext):
    await state.set_state(RepairReassignState.ticket_id)
    await message.reply("Введите номер заявки на ремонт:", reply_markup=get_repairs_keyboard())


@router.message(RepairReassignState.ticket_id)
async def reassign_repair_ticket_id(
    message: types.Message,
    state: FSMContext,
    repair_repository: RepairRepository,
):
    try:
        ticket_id = int(message.text.strip())
    except ValueError:
        await message.reply("❌ Введите число — номер заявки.", reply_markup=get_repairs_keyboard())
        await state.clear()
        return
    repair = repair_repository.get_by_ticket_id(ticket_id)
    if not repair:
        await state.clear()
        await message.reply(f"Заявка №{ticket_id} не найдена.", reply_markup=get_repairs_keyboard())
        return
    await state.update_data(reassign_ticket_id=ticket_id)
    await state.set_state(RepairReassignState.driver_fio)
    await message.reply(
        f"Заявка №{ticket_id} найдена.\n\nВведите ФИО водителя, на которого переназначить заявку:",
        reply_markup=get_repairs_keyboard(),
    )


async def _reassign_repair_show_confirm(message, ticket_id, user, repair_repository, user_repository):
    repair = repair_repository.get_by_ticket_id(ticket_id)
    if not repair:
        await message.reply(f"Заявка №{ticket_id} не найдена.", reply_markup=get_repairs_keyboard())
        return
    old_driver = user_repository.get_by_tg_id(int(repair.tg_id))
    old_name = old_driver.name if old_driver else "Неизвестно"
    text = (
        f"🔄 Переназначение заявки №{ticket_id}\n\n"
        f"Текущий водитель: {copy_link_fio(old_name)}\n"
        f"Новый водитель: {copy_link_fio(user.name)}\n\n"
        "Подтвердить переназначение?"
    )
    await message.reply(text, reply_markup=_get_reassign_repair_keyboard(ticket_id, user.tg_id), parse_mode="HTML")


@router.message(RepairReassignState.driver_fio)
async def reassign_repair_driver(
    message: types.Message,
    state: FSMContext,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    text = message.text.strip()
    data = await state.get_data()
    ticket_id = data.get("reassign_ticket_id")
    if not ticket_id:
        await state.clear()
        await message.reply("Сессия истекла. Начните заново.", reply_markup=get_repairs_keyboard())
        return
    user = user_repository.get_by_name(text)
    if user and user.tg_id and str(user.tg_id) != "0":
        await state.clear()
        await _reassign_repair_show_confirm(message, ticket_id, user, repair_repository, user_repository)
        return
    users = user_repository.search_drivers_by_name_part(text, limit=15)
    if not users:
        await message.reply("Водители не найдены. Введите ФИО или часть ФИО:", reply_markup=get_repairs_keyboard())
        return
    if len(users) == 1:
        await state.clear()
        await _reassign_repair_show_confirm(message, ticket_id, users[0], repair_repository, user_repository)
        return
    builder = InlineKeyboardBuilder()
    for u in users[:10]:
        builder.row(
            types.InlineKeyboardButton(text=u.name, callback_data=f"reassign_repair_driver_{u.tg_id}"),
        )
    await message.reply("Выберите водителя:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("reassign_repair_driver_"))
async def reassign_repair_driver_selected(
    callback: types.CallbackQuery,
    state: FSMContext,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    tg_id_str = callback.data.replace("reassign_repair_driver_", "")
    try:
        new_tg_id = int(tg_id_str)
    except ValueError:
        await callback.answer("Ошибка.")
        return
    data = await state.get_data()
    ticket_id = data.get("reassign_ticket_id")
    await state.clear()
    if not ticket_id:
        await callback.message.edit_text("Сессия истекла.")
        await callback.answer()
        return
    user = user_repository.get_by_tg_id(new_tg_id)
    if not user:
        await callback.message.edit_text("Водитель не найден.")
        await callback.answer()
        return
    await _reassign_repair_show_confirm(callback.message, ticket_id, user, repair_repository, user_repository)
    await callback.message.edit_text("Водитель выбран. Подтвердите переназначение выше.")
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_reassign_repair_"))
async def confirm_reassign_repair(
    callback: types.CallbackQuery,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    raw = callback.data.replace("confirm_reassign_repair_", "")
    parts = raw.split("_", 1)
    ticket_id = int(parts[0])
    new_tg_id = parts[1] if len(parts) > 1 else ""
    repair = repair_repository.get_by_ticket_id(ticket_id)
    if not repair:
        await callback.message.edit_text("Заявка не найдена.")
        await callback.answer()
        return
    old_tg_id = repair.tg_id
    ok = repair_repository.reassign_driver(ticket_id, new_tg_id)
    if not ok:
        await callback.message.edit_text("❌ Не удалось переназначить заявку.")
        await callback.answer()
        return
    bot = create_bot()
    new_driver = user_repository.get_by_tg_id(int(new_tg_id))
    old_driver = user_repository.get_by_tg_id(int(old_tg_id))
    new_name = new_driver.name if new_driver else "Неизвестно"
    old_name = old_driver.name if old_driver else "Неизвестно"
    msg_old = (
        f"🔄 Заявка №{ticket_id} переназначена другому водителю.\n\n"
        f"#️⃣ {ticket_id} | ТС: {html.escape(repair.number_auto)}\n"
        f"👤 Водитель (заявитель): {copy_link_fio(old_name)}\n"
        f"📝 {html.escape(repair.malfunction)}\n\n"
        f"Новый исполнитель: {copy_link_fio(new_name)}"
    )
    msg_new = (
        f"✅ Вам назначена заявка на ремонт №{ticket_id}\n\n"
        f"👤 Заявитель: {copy_link_fio(old_name)}\n"
        f"🚛 ТС: {html.escape(repair.number_auto)}\n"
        f"📝 {html.escape(repair.malfunction)}\n"
    )
    if repair.date_repair and repair.date_repair != "0":
        msg_new += f"📅 Дата: {repair.date_repair}\n"
    if repair.place_repair and repair.place_repair != "0":
        msg_new += f"🗺 Место: {repair.place_repair}\n"
    if repair.comment_repair and repair.comment_repair != "0":
        msg_new += f"🗒 Комментарий: {repair.comment_repair}\n"
    try:
        await bot.send_message(int(old_tg_id), msg_old, parse_mode="HTML")
    except Exception:
        pass
    try:
        await bot.send_message(int(new_tg_id), msg_new, parse_mode="HTML")
    except Exception as e:
        await callback.message.answer(f"⚠️ Переназначено, но не удалось уведомить нового водителя: {e}")
    await callback.message.edit_text(f"✅ Заявка №{ticket_id} переназначена на {new_name}.")
    await callback.answer()


@router.callback_query(F.data == "cancel_reassign_repair")
async def cancel_reassign_repair(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ Переназначение отменено.")
    await callback.answer()


# --- Отмена ремонта ---

def _get_cancel_repair_keyboard(ticket_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="✅ Подтвердить отмену", callback_data=f"confirm_cancel_repair_{ticket_id}"),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_cancel_repair"),
    )
    return builder.as_markup()


@router.message(F.text == "🚫 Отменить ремонт")
async def cancel_repair_start(message: types.Message, state: FSMContext):
    await state.set_state(RepairCancelState.ticket_id)
    await message.reply("Введите номер заявки на ремонт для отмены:", reply_markup=get_repairs_keyboard())


@router.message(RepairCancelState.ticket_id)
async def cancel_repair_ticket_id(
    message: types.Message,
    state: FSMContext,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    try:
        ticket_id = int(message.text.strip())
    except ValueError:
        await message.reply("❌ Введите число — номер заявки.", reply_markup=get_repairs_keyboard())
        await state.clear()
        return
    repair = repair_repository.get_by_ticket_id(ticket_id)
    if not repair:
        await state.clear()
        await message.reply(f"Заявка №{ticket_id} не найдена.", reply_markup=get_repairs_keyboard())
        return
    driver = user_repository.get_by_tg_id(int(repair.tg_id))
    driver_name = driver.name if driver else "Неизвестно"
    text = (
        f"🚫 Отмена ремонта №{ticket_id}\n\n"
        f"🚛 ТС: {repair.number_auto}\n"
        f"👤 Водитель: {copy_link_fio(driver_name)}\n"
        f"📝 {repair.malfunction}\n\n"
        f"Отменить ремонт? Водителю будет отправлено уведомление."
    )
    await message.reply(text, reply_markup=_get_cancel_repair_keyboard(ticket_id), parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data.startswith("confirm_cancel_repair_"))
async def confirm_cancel_repair(
    callback: types.CallbackQuery,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    ticket_id = int(callback.data.replace("confirm_cancel_repair_", ""))
    repair = repair_repository.get_by_ticket_id(ticket_id)
    if not repair:
        await callback.message.edit_text("Заявка не найдена.")
        await callback.answer()
        return
    ok = repair_repository.update_status(ticket_id, RepairStatus.CANCELLED)
    if not ok:
        await callback.message.edit_text("❌ Не удалось отменить заявку.")
        await callback.answer()
        return
    bot = create_bot()
    driver = user_repository.get_by_tg_id(int(repair.tg_id))
    driver_name = driver.name if driver else "Неизвестно"
    msg = (
        f"🚫 Заявка на ремонт №{ticket_id} отменена.\n\n"
        f"#️⃣ {ticket_id} | ТС: {repair.number_auto}\n"
        f"👤 Водитель: {copy_link_fio(driver_name)}\n"
        f"📝 {repair.malfunction}\n\n"
        f"Статус: Отменена"
    )
    try:
        await bot.send_message(int(repair.tg_id), msg)
    except Exception:
        pass
    await callback.message.edit_text(f"✅ Заявка №{ticket_id} отменена. Водителю отправлено уведомление.")
    await callback.answer()


@router.callback_query(F.data == "cancel_cancel_repair")
async def cancel_cancel_repair(callback: types.CallbackQuery):
    await callback.message.edit_text("❌ Отмена ремонта отменена.")
    await callback.answer()


# --- Изменение деталей ремонта ---

def _get_edit_repair_params_keyboard(ticket_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🚛 ТС", callback_data=f"edit_repair_param_{ticket_id}_number_auto"),
        types.InlineKeyboardButton(text="📝 Описание", callback_data=f"edit_repair_param_{ticket_id}_malfunction"),
    )
    builder.row(
        types.InlineKeyboardButton(text="📅 Дата", callback_data=f"edit_repair_param_{ticket_id}_date_repair"),
        types.InlineKeyboardButton(text="🗺 Место", callback_data=f"edit_repair_param_{ticket_id}_place_repair"),
    )
    builder.row(
        types.InlineKeyboardButton(text="🗒 Комментарий", callback_data=f"edit_repair_param_{ticket_id}_comment_repair"),
    )
    return builder.as_markup()


@router.message(F.text == "✏️ Изменить детали ремонта")
async def edit_repair_start(message: types.Message, state: FSMContext):
    await state.set_state(RepairEditState.ticket_id)
    await message.reply("Введите номер заявки на ремонт:", reply_markup=get_repairs_keyboard())


@router.message(RepairEditState.ticket_id)
async def edit_repair_ticket_id(
    message: types.Message,
    state: FSMContext,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    try:
        ticket_id = int(message.text.strip())
    except ValueError:
        await message.reply("❌ Введите число.", reply_markup=get_repairs_keyboard())
        await state.clear()
        return
    repair = repair_repository.get_by_ticket_id(ticket_id)
    if not repair:
        await state.clear()
        await message.reply(f"Заявка №{ticket_id} не найдена.", reply_markup=get_repairs_keyboard())
        return
    driver = user_repository.get_by_tg_id(int(repair.tg_id))
    driver_name = driver.name if driver else "Неизвестно"
    text = (
        f"✏️ Изменение заявки №{ticket_id}\n\n"
        f"🚛 ТС: {repair.number_auto}\n"
        f"👤 Водитель: {copy_link_fio(driver_name)}\n"
        f"📝 Описание: {repair.malfunction}\n"
        f"📅 Дата: {repair.date_repair or '—'}\n"
        f"🗺 Место: {repair.place_repair or '—'}\n"
        f"🗒 Комментарий: {repair.comment_repair or '—'}\n\n"
        f"Выберите параметр для изменения:"
    )
    await state.clear()
    await message.reply(text, reply_markup=_get_edit_repair_params_keyboard(ticket_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("edit_repair_param_"))
async def edit_repair_choose_param(callback: types.CallbackQuery, state: FSMContext):
    raw = callback.data.replace("edit_repair_param_", "")
    idx = raw.find("_")
    ticket_id = int(raw[:idx])
    param = raw[idx + 1:]
    param_labels = {
        "number_auto": "номер ТС",
        "malfunction": "описание неисправности",
        "date_repair": "дату ремонта",
        "place_repair": "место ремонта",
        "comment_repair": "комментарий",
    }
    label = param_labels.get(param, param)
    await state.update_data(edit_repair_ticket_id=ticket_id, edit_repair_param=param)
    await state.set_state(RepairEditState.value)
    await callback.message.edit_text(f"Введите новое значение для параметра «{label}»:")
    await callback.answer()


@router.message(RepairEditState.value)
async def edit_repair_value(
    message: types.Message,
    state: FSMContext,
):
    value = message.text.strip()
    data = await state.get_data()
    ticket_id = data.get("edit_repair_ticket_id")
    param = data.get("edit_repair_param")
    if not ticket_id or not param:
        await state.clear()
        await message.reply("Сессия истекла.", reply_markup=get_repairs_keyboard())
        return
    await state.update_data(edit_repair_confirm_value=value)
    param_labels = {"number_auto": "ТС", "malfunction": "Описание", "date_repair": "Дата", "place_repair": "Место", "comment_repair": "Комментарий"}
    label = param_labels.get(param, param)
    text = f"Изменить «{label}» на: {value}\n\nПодтвердите:"
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"confirm_edit_repair_{ticket_id}_{param}",
        ),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit_repair"),
    )
    await message.reply(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("confirm_edit_repair_"))
async def confirm_edit_repair(
    callback: types.CallbackQuery,
    state: FSMContext,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    raw = callback.data.replace("confirm_edit_repair_", "")
    parts = raw.split("_")
    ticket_id = int(parts[0])
    param = "_".join(parts[1:]) if len(parts) > 1 else ""
    data = await state.get_data()
    value = data.get("edit_repair_confirm_value", "")
    await state.clear()
    if not param or param not in ("number_auto", "malfunction", "date_repair", "place_repair", "comment_repair"):
        await callback.message.edit_text("❌ Ошибка: неизвестный параметр.")
        await callback.answer()
        return
    repair = repair_repository.get_by_ticket_id(ticket_id)
    if not repair:
        await callback.message.edit_text("Заявка не найдена.")
        await callback.answer()
        return
    updates = {param: value}
    ok = repair_repository.update_details(ticket_id, **updates)
    if not ok:
        await callback.message.edit_text("❌ Не удалось изменить заявку.")
        await callback.answer()
        return
    param_labels = {"number_auto": "ТС", "malfunction": "Описание", "date_repair": "Дата", "place_repair": "Место", "comment_repair": "Комментарий"}
    label = param_labels.get(param, param)
    bot = create_bot()
    repair = repair_repository.get_by_ticket_id(ticket_id)
    driver = user_repository.get_by_tg_id(int(repair.tg_id))
    driver_name = driver.name if driver else "Неизвестно"
    msg = (
        f"✏️ В заявке №{ticket_id} изменены детали:\n\n"
        f"Параметр «{label}» обновлён на: {value}\n\n"
        f"#️⃣ {ticket_id} | ТС: {repair.number_auto}\n"
        f"👤 Водитель: {copy_link_fio(driver_name)}\n"
        f"📝 {repair.malfunction}\n"
    )
    if repair.date_repair and repair.date_repair != "0":
        msg += f"📅 Дата: {repair.date_repair}\n"
    if repair.place_repair and repair.place_repair != "0":
        msg += f"🗺 Место: {repair.place_repair}\n"
    if repair.comment_repair and repair.comment_repair != "0":
        msg += f"🗒 Комментарий: {repair.comment_repair}\n"
    try:
        await bot.send_message(int(repair.tg_id), msg)
    except Exception:
        pass
    await callback.message.edit_text(f"✅ Заявка №{ticket_id} обновлена. Водителю отправлено уведомление.")
    await callback.answer()


@router.callback_query(F.data == "cancel_edit_repair")
async def cancel_edit_repair(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Изменение отменено.")
    await callback.answer()


@router.callback_query(F.data.startswith("ticket_repair_"))
async def process_ticket_repair(callback: types.CallbackQuery, state: FSMContext):
    # Извлекаем ID заявки из callback_data
    ticket_id_str = callback.data.split("_")[2]
    try:
        ticket_id = int(ticket_id_str)
        await state.update_data(ticket_id=ticket_id)
        await state.set_state(AdminRepairState.date)
        await callback.message.answer(f"Обработка заявки №{ticket_id}\nВведите дату ремонта (дд.мм.гггг)")
    except ValueError:
        await callback.message.answer("Ошибка: неверный номер заявки")

@router.message(AdminRepairState.date)
async def ticket_repair_date(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text)
    await state.set_state(AdminRepairState.place)
    await message.answer("Введите место ремонта")

@router.message(AdminRepairState.place)
async def ticket_repair_place(message: types.Message, state: FSMContext):
    await state.update_data(place=message.text)
    await state.set_state(AdminRepairState.comment)
    await message.answer("Введите комментарий для водителя")

@router.message(AdminRepairState.comment)
async def ticket_repair_finish(
    message: types.Message,
    state: FSMContext,
    repair_repository: RepairRepository,
    user_repository: UserRepository
):
    await state.update_data(comment=message.text)
    data = await state.get_data()
    
    success = repair_repository.process_ticket(
        data["ticket_id"],
        data["date"],
        data["place"],
        data["comment"]
    )
    
    if not success:
        await message.answer(f"Заявка № {data['ticket_id']} не найдена")
        await state.clear()
        return
    
    # Получаем информацию о заявке
    repair = repair_repository.get_by_ticket_id(data["ticket_id"])
    if not repair:
        await message.answer(f"Заявка № {data['ticket_id']} не найдена")
        await state.clear()
        return
    
    # Получаем информацию о водителе
    driver = user_repository.get_by_tg_id(int(repair.tg_id))
    driver_name = driver.name if driver else "Неизвестно"
    
    # Отправляем уведомление водителю
    bot = create_bot()
    
    try:
        await bot.send_message(
            repair.tg_id,
            f"✅ Ремонт согласован администратором\n\n"
            f"#️⃣ Номер заявки: {data['ticket_id']} \n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"🚛 Номер ТС: {html.escape(repair.number_auto)}\n"
            f"📝 Описание: {html.escape(repair.malfunction)}\n"
            f"📅 Дата ремонта: {html.escape(data['date'])} \n"
            f"🗺 Место ремонта: {html.escape(data['place'])}\n"
            f"🗒 Комментарий для водителя: {html.escape(data['comment'])}\n\n"
            "Подтвердите согласие с назначенным ремонтом:",
            reply_markup=get_ticket_confirm_driver_keyboard(data['ticket_id']),
            parse_mode="HTML",
        )
        await message.answer(
            f"✅ Заявка обработана\n\n"
            f"#️⃣ Номер заявки: {data['ticket_id']} \n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"🚛 Номер ТС: {html.escape(repair.number_auto)}\n"
            f"📝 Описание: {html.escape(repair.malfunction)}\n"
            f"📅 Дата ремонта: {html.escape(data['date'])} \n"
            f"🗺 Место ремонта: {html.escape(data['place'])}\n"
            f"🗒 Комментарий для водителя: {html.escape(data['comment'])} \n\n"
            "📊 Статус: ✉️ Обработана администратором\n"
            "⏳ Ожидаем подтверждения водителя",
            parse_mode="HTML",
        )

    except Exception as e:
        await message.answer(f"Ошибка при отправке уведомления водителю: {e}")

    await state.clear()


@router.callback_query(F.data.startswith("ticket_success_admin_"))
async def ticket_repair_success_admin(callback: types.CallbackQuery, repair_repository: RepairRepository):
    # Извлекаем ID заявки из callback_data
    ticket_id_str = callback.data.split("_")[3]
    try:
        ticket_id = int(ticket_id_str)
        success = repair_repository.success_repair_ticket_repair(ticket_id)
        
        if success:
            # Редактируем сообщение вместо удаления
            await callback.message.edit_text(
                f"✅ Окончание ремонта заявки №{ticket_id} подтверждено\n\n"
                f"Статус заявки: ✅ Завершена"
            )
        else:
            await callback.message.edit_text(f"❌ Ошибка при подтверждении заявки №{ticket_id}")
    except ValueError:
        await callback.message.edit_text("❌ Ошибка: неверный номер заявки")
    
    await callback.answer()

# Старый метод через ввод номера (оставляем для обратной совместимости)
@router.callback_query(F.data == "ticket_repair")
async def process_ticket_repair_old(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminRepairState.ticket_id)
    await callback.message.answer("Введите номер заявки")

# Старый метод через ввод номера (оставляем для обратной совместимости)
@router.callback_query(F.data == "ticket_repair_success_repair")
async def ticket_repair_success_old(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminRepairState.ticket_id_conf)
    await callback.message.answer("Введите номер заявки")

@router.message(AdminRepairState.ticket_id_conf)
async def ticket_repair_success_conf(message: types.Message, state: FSMContext, repair_repository: RepairRepository):
    try:
        ticket_id = int(message.text)
        success = repair_repository.success_repair_ticket_repair(ticket_id)
        
        if success:
            await message.answer(f"✅ Окончание ремонта заявки №{ticket_id} подтверждено")
        else:
            await message.answer(f"❌ Заявка №{ticket_id} не найдена")
    except ValueError:
        await message.answer("❌ Неверный формат номера заявки")
    
    await state.clear()

@router.message(AutoSearchState.number_auto)
async def search_repairs_by_auto_result(
    message: types.Message,
    state: FSMContext,
    repair_repository: RepairRepository,
    user_repository: UserRepository
):
    await state.update_data(number_auto=message.text)
    data = await state.get_data()
    await state.clear()
    
    all_tickets = repair_repository.get_by_number_auto(data['number_auto'])
    
    if not all_tickets:
        await message.answer("Заявок не найдено")
        return
    
    all_ticket_text = f"🚛 Заявки ТС: {all_tickets[0].number_auto}\n\n"
    
    for ticket in all_tickets:
        driver = user_repository.get_by_tg_id(ticket.tg_id)
        driver_name = driver.name if driver else "Неизвестно"
        driver_phone = driver.phone if driver else "Неизвестно"
        
        status_text = {
            RepairStatus.NEW: "🆕 Новая",
            RepairStatus.PROCESS: "✉️ Ожидает подтверждения",
            RepairStatus.CONFIRM: "📨 Ожидает ремонта",
            RepairStatus.PROC_REPAIR: "🛻 Выехал на ремонт",
            RepairStatus.CONF_REPAIR: "🛠 Отремонтирована",
            RepairStatus.SUCCESS: "✅ Завершена",
            RepairStatus.CANCELLED: "❌ Отменена",
        }.get(ticket.status, "❓ Неизвестно")
        
        ticket_text = (
            f"#️⃣ Номер заявки: {ticket.id_ticket} \n"
            f"📙 Статус: {status_text} \n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"📞 Телефон: {driver_phone} \n"
            f"📝 Описание: {ticket.malfunction} \n"
        )
        
        if ticket.date_repair and ticket.date_repair != "0":
            ticket_text += f"📅 Дата ремонта: {ticket.date_repair} \n"
        
        if ticket.place_repair and ticket.place_repair != "0":
            ticket_text += f"🗺 Место ремонта: {ticket.place_repair} \n"
        
        if ticket.comment_repair and ticket.comment_repair != "0":
            ticket_text += f"🗒 Комментарий: {ticket.comment_repair} \n"
        
        await message.answer(ticket_text, parse_mode="HTML")
    await message.answer(f"📊 Всего найдено заявок: {len(all_tickets)}")