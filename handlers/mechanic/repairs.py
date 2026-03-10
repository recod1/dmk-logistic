# handlers/mechanic/repairs.py
import html
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.telegram_helpers import copy_link_fio
from keyboards.admin_kb import (
    get_repairs_keyboard, 
    get_admin_main_keyboard,
)
from states.repair_states import AutoSearchState
from database.repositories.repair_repository import RepairRepository
from database.repositories.user_repository import UserRepository
from config.settings import RepairStatus

router = Router()

def get_ticket_repair_keyboard(ticket_id: int):
    """Клавиатура для обработки конкретной заявки"""
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="🔧 Обработать", 
        callback_data=f"ticket_repair_{ticket_id}"
    ))
    return builder.as_markup()

@router.message(F.text == "🛠 Заявки на ремонт")
async def menu_repairs(message: types.Message):
    await message.reply("🛠 Заявки на ремонт", reply_markup=get_repairs_keyboard())

@router.message(F.text == "🔧 Обработать заявку")
async def work_repair_ticket(message: types.Message):
    await message.reply("❌ Обработка заявок доступна только администраторам")

@router.message(F.text == "🔍 Найти заявки ТС")
async def search_repairs_by_auto(message: types.Message, state: FSMContext):
    await state.set_state(AutoSearchState.number_auto)
    await message.reply("Введите номер ТС", reply_markup=get_repairs_keyboard())

# @router.message(F.text == "↩️ Назад")
# async def exit_to_main(message: types.Message):
#     await message.reply("Назад", reply_markup=get_admin_main_keyboard())

@router.message(F.text == "🆕 Новые")
async def show_new_repairs(
    message: types.Message,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    repairs = repair_repository.get_by_status(RepairStatus.NEW)
    
    if not repairs:
        await message.reply("Нет новых заявок", reply_markup=get_repairs_keyboard())
        return
    
    for repair in repairs:
        driver = user_repository.get_by_tg_id(int(repair.tg_id))
        driver_name = driver.name if driver else "Неизвестно"
        await message.answer(
            f"#️⃣ Номер заявки: {repair.id_ticket} \n"
            f"👤 Водитель: {copy_link_fio(driver_name)}\n"
            f"🚛 Номер ТС: {html.escape(repair.number_auto)}\n"
            f"📝 Описание неисправности: {html.escape(repair.malfunction)}",
            reply_markup=get_ticket_repair_keyboard(repair.id_ticket),
            parse_mode="HTML",
        )
    
    await message.reply(f"📊 Всего новых заявок: {len(repairs)}", reply_markup=get_repairs_keyboard())

@router.message(F.text == "✉️ Ожидают подтверждения")
async def show_process_repairs(
    message: types.Message,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    repairs = repair_repository.get_by_status(RepairStatus.PROCESS)
    
    if not repairs:
        await message.reply("Нет заявок, ожидающих подтверждения", reply_markup=get_repairs_keyboard())
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
    
    await message.reply(all_text_repair, reply_markup=get_repairs_keyboard(), parse_mode="HTML")

@router.message(F.text == "📨 Ожидают ремонта")
async def show_confirm_repairs(
    message: types.Message,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    repairs = repair_repository.get_by_status(RepairStatus.CONFIRM)
    
    if not repairs:
        await message.reply("Нет заявок, ожидающих ремонта", reply_markup=get_repairs_keyboard())
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
    
    await message.reply(all_text_repair, reply_markup=get_repairs_keyboard(), parse_mode="HTML")

@router.message(F.text == "🛻 Выехали на ремонт")
async def show_proc_repair_repairs(
    message: types.Message,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    repairs = repair_repository.get_by_status(RepairStatus.PROC_REPAIR)
    
    if not repairs:
        await message.reply("Нет заявок, в процессе ремонта", reply_markup=get_repairs_keyboard())
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
    
    await message.reply(all_text_repair, reply_markup=get_repairs_keyboard(), parse_mode="HTML")

@router.message(F.text == "🛠 Отремонтированы")
async def show_conf_repair_repairs(
    message: types.Message,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    repairs = repair_repository.get_by_status(RepairStatus.CONF_REPAIR)
    
    if not repairs:
        await message.reply("Нет заявок, после ремонта", reply_markup=get_repairs_keyboard())
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
    
    await message.reply(all_text_repair, reply_markup=get_repairs_keyboard(), parse_mode="HTML")

@router.message(F.text == "✅ Завершены")
async def show_success_repairs(
    message: types.Message,
    repair_repository: RepairRepository,
    user_repository: UserRepository,
):
    repairs = repair_repository.get_by_status(RepairStatus.SUCCESS)
    
    if not repairs:
        await message.reply("Нет завершенных заявок", reply_markup=get_repairs_keyboard())
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
    
    await message.reply(all_text_repair, reply_markup=get_repairs_keyboard(), parse_mode="HTML")

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