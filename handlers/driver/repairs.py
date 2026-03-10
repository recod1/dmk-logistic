# handlers/driver/repairs.py
import re
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from keyboards.driver_kb import (
    get_driver_repairs_keyboard,
    get_driver_main_keyboard,
    get_ticket_confirm_driver_keyboard,
    get_ticket_proc_repair_driver_keyboard,
    get_ticket_conf_repair_driver_keyboard,
    get_ticket_success_repair_driver_keyboard
)
from states.repair_states import DriverRepairState
from database.repositories.repair_repository import RepairRepository
from database.repositories.user_repository import UserRepository
from config.settings import RepairStatus
from core.bot import create_bot
from config.settings import settings

router = Router()

@router.message(F.text == "🛠 Ремонт")
async def ticket_repair_menu(message: types.Message):
    await message.reply("Меню ремонтов:", reply_markup=get_driver_repairs_keyboard())

@router.message(F.text == "🙎‍♂️ Мои ремонты")
async def my_repairs(
    message: types.Message,
    repair_repository: RepairRepository,
    user_repository: UserRepository
):
    all_tickets = repair_repository.get_by_tg_id(message.from_user.id)
    
    if not all_tickets:
        await message.reply("Активных заявок нет", reply_markup=get_driver_repairs_keyboard())
        return
    
    # Группируем заявки по статусу
    new_tickets = [t for t in all_tickets if t.status == RepairStatus.NEW]
    process_tickets = [t for t in all_tickets if t.status == RepairStatus.PROCESS]
    confirm_tickets = [t for t in all_tickets if t.status == RepairStatus.CONFIRM]
    proc_repair_tickets = [t for t in all_tickets if t.status == RepairStatus.PROC_REPAIR]
    conf_repair_tickets = [t for t in all_tickets if t.status == RepairStatus.CONF_REPAIR]
    success_tickets = [t for t in all_tickets if t.status == RepairStatus.SUCCESS]
    
    if new_tickets:
        text = "🆕 Новые заявки (ожидают обработки администратором):\n\n"
        for ticket in new_tickets:
            text += f"#️⃣ {ticket.id_ticket} - {ticket.number_auto}: {ticket.malfunction}\n"
        await message.reply(text, reply_markup=get_driver_repairs_keyboard())
    
    # Отправляем заявки с кнопками ТОЛЬКО когда администратор обработал их
    for ticket in process_tickets:
        await message.reply(
            f"✉️ Заявка обработана администратором\n\n"
            f"#️⃣ Номер: {ticket.id_ticket}\n"
            f"🚛 ТС: {ticket.number_auto}\n"
            f"📝 Описание: {ticket.malfunction}\n"
            f"📅 Дата ремонта: {ticket.date_repair if ticket.date_repair != '0' else 'не указана'}\n"
            f"🗺 Место ремонта: {ticket.place_repair if ticket.place_repair != '0' else 'не указано'}\n"
            f"🗒 Комментарий: {ticket.comment_repair if ticket.comment_repair != '0' else 'нет'}\n\n"
            f"Подтвердите согласие с назначенным ремонтом:",
            reply_markup=get_ticket_confirm_driver_keyboard(ticket.id_ticket)
        )
    
    for ticket in confirm_tickets:
        await message.reply(
            f"📨 Заявка подтверждена, ожидает выезда на ремонт\n\n"
            f"#️⃣ Номер: {ticket.id_ticket}\n"
            f"🚛 ТС: {ticket.number_auto}\n"
            f"📝 Описание: {ticket.malfunction}\n"
            f"📅 Дата: {ticket.date_repair if ticket.date_repair != '0' else 'не указана'}\n"
            f"🗺 Место: {ticket.place_repair if ticket.place_repair != '0' else 'не указано'}\n"
            f"🗒 Комментарий: {ticket.comment_repair if ticket.comment_repair != '0' else 'нет'}\n\n"
            f"Подтвердите выезд на ремонт:",
            reply_markup=get_ticket_proc_repair_driver_keyboard(ticket.id_ticket)
        )
    
    for ticket in proc_repair_tickets:
        await message.reply(
            f"🛻 Заявка в процессе ремонта\n\n"
            f"#️⃣ Номер: {ticket.id_ticket}\n"
            f"🚛 ТС: {ticket.number_auto}\n"
            f"📝 Описание: {ticket.malfunction}\n"
            f"📅 Дата: {ticket.date_repair if ticket.date_repair != '0' else 'не указана'}\n"
            f"🗺 Место: {ticket.place_repair if ticket.place_repair != '0' else 'не указано'}\n"
            f"🗒 Комментарий: {ticket.comment_repair if ticket.comment_repair != '0' else 'нет'}\n\n"
            f"Подтвердите окончание ремонта:",
            reply_markup=get_ticket_conf_repair_driver_keyboard(ticket.id_ticket)
        )
    
    if conf_repair_tickets:
        text = "🛠 Отремонтированные заявки (ожидают подтверждения администратором):\n\n"
        for ticket in conf_repair_tickets:
            text += f"#️⃣ {ticket.id_ticket} - {ticket.number_auto}: {ticket.malfunction}\n"
        await message.reply(text, reply_markup=get_driver_repairs_keyboard())
    
    if success_tickets:
        text = "✅ Завершенные заявки:\n\n"
        for ticket in success_tickets:
            text += f"#️⃣ {ticket.id_ticket} - {ticket.number_auto}: {ticket.malfunction}\n"
        await message.reply(text, reply_markup=get_driver_repairs_keyboard())

@router.message(F.text == "🛠 Заявка на ремонт")
async def create_repair_request(message: types.Message, state: FSMContext):
    await state.set_state(DriverRepairState.number_auto)
    await message.reply(
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
        reply_markup=get_driver_repairs_keyboard()
    )

@router.message(DriverRepairState.number_auto)
async def get_repair_number_auto(message: types.Message, state: FSMContext):
    number_auto = message.text.strip().upper()
    
    # Валидация формата:
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
            reply_markup=get_driver_repairs_keyboard()
        )
        return
    
    await state.update_data(number_auto=number_auto)
    await state.set_state(DriverRepairState.malfunction)
    await message.reply(
        f"✅ Номер ТС принят: {number_auto}\n\n"
        "Теперь введите описание неисправности:",
        reply_markup=get_driver_main_keyboard()
    )

@router.message(DriverRepairState.malfunction)
async def get_repair_malfunction(
    message: types.Message,
    state: FSMContext,
    repair_repository: RepairRepository,
    user_repository: UserRepository
):
    await state.update_data(malfunction=message.text)
    data = await state.get_data()
    
    # Создаем новый ID для тикета на основе максимального существующего id_ticket
    id_ticket = repair_repository.get_next_ticket_id()
    
    # Создаем заявку
    repair = repair_repository.create(
        id_ticket=id_ticket,
        tg_id=message.from_user.id,
        number_auto=data['number_auto'],
        malfunction=data['malfunction']
    )
    
    # Отправляем уведомления администраторам
    from services.notification_service import NotificationService
    notification_service = NotificationService(user_repository)
    await notification_service.notify_about_new_repair(
        ticket_id=id_ticket,
        number_auto=data['number_auto'],
        malfunction=data['malfunction'],
        driver_id=message.from_user.id
    )
    
    await message.reply(
        f"✅ Заявка на ремонт создана \n\n"
        f"#️⃣Номер заявки: {id_ticket}\n"
        f"🚛Номер ТС: {data['number_auto']}\n"
        f"📝Описание неисправности: {data['malfunction']}\n\n"
        f"📋 Статус: 🆕 Новая\n"
        f"⏳ Ожидайте обработки администратором",
        reply_markup=get_driver_main_keyboard()
    )
    await state.clear()

@router.callback_query(F.data.startswith("ticket_confirm_"))
async def ticket_confirm_specific(
    callback: types.CallbackQuery,
    repair_repository: RepairRepository,
    user_repository: UserRepository
):
    # Извлекаем ID заявки из callback_data
    ticket_id_str = callback.data.split("_")[2]
    try:
        ticket_id = int(ticket_id_str)
        ticket = repair_repository.get_by_ticket_id(ticket_id)
        
        if not ticket:
            await callback.message.answer("❌ Заявка не найдена")
            return
        
        # Проверяем, что заявка принадлежит этому водителю
        if int(ticket.tg_id) != callback.from_user.id:
            await callback.message.answer("❌ Это не ваша заявка")
            return
        
        # Проверяем статус - теперь водитель может подтверждать только заявки, обработанные администратором (статус PROCESS)
        if ticket.status != RepairStatus.PROCESS:
            # Отправляем новое сообщение с текущим статусом
            status_text = {
                RepairStatus.NEW: "🆕 Новая (ожидает обработки администратором)",
                RepairStatus.PROCESS: "✉️ Обработана администратором",
                RepairStatus.CONFIRM: "📨 Ожидает ремонта",
                RepairStatus.PROC_REPAIR: "🛻 Выехал на ремонт",
                RepairStatus.CONF_REPAIR: "🛠 Отремонтирована",
                RepairStatus.SUCCESS: "✅ Завершена"
            }.get(ticket.status, "❓ Неизвестно")
            
            await callback.message.answer(
                f"❌ Заявка уже обработана\n"
                f"Текущий статус: {status_text}",
                reply_markup=get_driver_repairs_keyboard()
            )
            return
        
        # Проверяем, что администратор назначил дату и место
        if ticket.date_repair == "0" or ticket.place_repair == "0":
            await callback.message.answer(
                f"❌ Администратор ещё не назначил дату и место ремонта\n"
                f"Ожидайте обработки заявки администратором",
                reply_markup=get_driver_repairs_keyboard()
            )
            return
        
        success = repair_repository.confirm_ticket_repair(ticket_id)
        
        if not success:
            await callback.message.answer("❌ Ошибка при подтверждении заявки")
            return
        
        # Редактируем сообщение вместо удаления
        await callback.message.edit_text(
            f"✅ Заявка № {ticket_id} подтверждена \n\n"
            f"🚛 ТС: {ticket.number_auto}\n"
            f"📝 Описание: {ticket.malfunction}\n"
            f"📅 Дата ремонта: {ticket.date_repair if ticket.date_repair != '0' else 'не указана'}\n"
            f"🗺 Место ремонта: {ticket.place_repair if ticket.place_repair != '0' else 'не указано'}\n"
            f"🗒 Комментарий: {ticket.comment_repair if ticket.comment_repair != '0' else 'нет'}\n\n"
            f"📊 Статус: 📨 Ожидает выезда на ремонт"
        )
        
        # Отправляем новое сообщение со следующей кнопкой
        await callback.message.answer(
            f"🚚 Заявка готова к выезду\n\n"
            f"#️⃣ Номер: {ticket_id}\n"
            f"Когда будете готовы выехать на ремонт, подтвердите:",
            reply_markup=get_ticket_proc_repair_driver_keyboard(ticket_id)
        )
        
        # Уведомляем администраторов
        from services.notification_service import NotificationService
        notification_service = NotificationService(user_repository)
        await notification_service.notify_about_confirmed_repair(ticket)
        
    except ValueError:
        await callback.message.answer("❌ Ошибка: неверный номер заявки")
    
    await callback.answer()

@router.callback_query(F.data.startswith("ticket_proc_repair_"))
async def ticket_proc_repair_specific(
    callback: types.CallbackQuery,
    repair_repository: RepairRepository,
    user_repository: UserRepository
):
    ticket_id_str = callback.data.split("_")[3]
    try:
        ticket_id = int(ticket_id_str)
        ticket = repair_repository.get_by_ticket_id(ticket_id)
        
        if not ticket:
            await callback.message.answer("❌ Заявка не найдена")
            return
        
        if int(ticket.tg_id) != callback.from_user.id:
            await callback.message.answer("❌ Это не ваша заявка")
            return
        
        if ticket.status != RepairStatus.CONFIRM:
            # Отправляем новое сообщение с текущим статусом
            status_text = {
                RepairStatus.NEW: "🆕 Новая (ожидает обработки администратором)",
                RepairStatus.PROCESS: "✉️ Обработана администратором",
                RepairStatus.CONFIRM: "📨 Ожидает ремонта",
                RepairStatus.PROC_REPAIR: "🛻 Выехал на ремонт",
                RepairStatus.CONF_REPAIR: "🛠 Отремонтирована",
                RepairStatus.SUCCESS: "✅ Завершена"
            }.get(ticket.status, "❓ Неизвестно")
            
            await callback.message.answer(
                f"❌ Заявка уже обработана\n"
                f"Текущий статус: {status_text}",
                reply_markup=get_driver_repairs_keyboard()
            )
            return
        
        success = repair_repository.proc_repair_ticket_repair(ticket_id)
        
        if not success:
            await callback.message.answer("❌ Ошибка при обновлении статуса")
            return
        
        # Редактируем предыдущее сообщение с кнопкой
        await callback.message.edit_text(
            f"✅ Вы подтвердили выезд на ремонт\n\n"
            f"#️⃣ Номер: {ticket_id}\n"
            f"🚛 ТС: {ticket.number_auto}\n"
            f"📝 Описание: {ticket.malfunction}\n"
            f"📊 Статус: 🛻 Выехал на ремонт"
        )
        
        # Отправляем новое сообщение со следующей кнопкой
        await callback.message.answer(
            f"🛠 Заявка в процессе ремонта\n\n"
            f"#️⃣ Номер: {ticket_id}\n"
            f"Когда закончите ремонт, подтвердите его окончание:",
            reply_markup=get_ticket_conf_repair_driver_keyboard(ticket_id)
        )
        
        # Уведомляем администраторов
        from services.notification_service import NotificationService
        notification_service = NotificationService(user_repository)
        await notification_service.notify_admins_about_departure_for_repair(ticket)
        
    except ValueError:
        await callback.message.answer("❌ Ошибка: неверный номер заявки")
    
    await callback.answer()

@router.callback_query(F.data.startswith("ticket_conf_repair_"))
async def ticket_conf_repair_specific(
    callback: types.CallbackQuery,
    repair_repository: RepairRepository,
    user_repository: UserRepository
):
    ticket_id_str = callback.data.split("_")[3]
    try:
        ticket_id = int(ticket_id_str)
        ticket = repair_repository.get_by_ticket_id(ticket_id)
        
        if not ticket:
            await callback.message.answer("❌ Заявка не найдена")
            return
        
        if int(ticket.tg_id) != callback.from_user.id:
            await callback.message.answer("❌ Это не ваша заявка")
            return
        
        if ticket.status != RepairStatus.PROC_REPAIR:
            # Отправляем новое сообщение с текущим статусом
            status_text = {
                RepairStatus.NEW: "🆕 Новая (ожидает обработки администратором)",
                RepairStatus.PROCESS: "✉️ Обработана администратором",
                RepairStatus.CONFIRM: "📨 Ожидает ремонта",
                RepairStatus.PROC_REPAIR: "🛻 Выехал на ремонт",
                RepairStatus.CONF_REPAIR: "🛠 Отремонтирована",
                RepairStatus.SUCCESS: "✅ Завершена"
            }.get(ticket.status, "❓ Неизвестно")
            
            await callback.message.answer(
                f"❌ Заявка уже обработана\n"
                f"Текущий статус: {status_text}",
                reply_markup=get_driver_repairs_keyboard()
            )
            return
        
        success = repair_repository.conf_repair_ticket_repair(ticket_id)
        
        if not success:
            await callback.message.answer("❌ Ошибка при подтверждении окончания ремонта")
            return
        
        # Редактируем предыдущее сообщение с кнопкой
        await callback.message.edit_text(
            f"✅ Вы подтвердили окончание ремонта\n\n"
            f"#️⃣ Номер: {ticket_id}\n"
            f"🚛 ТС: {ticket.number_auto}\n"
            f"📝 Описание: {ticket.malfunction}\n"
            f"📊 Статус: 🛠 Отремонтирована"
        )
        
        # Отправляем финальное сообщение
        await callback.message.answer(
            f"🎉 Ремонт завершен!\n\n"
            f"Заявка № {ticket_id} успешно отремонтирована.\n"
        )
        
        # Уведомляем администраторов
        from services.notification_service import NotificationService
        notification_service = NotificationService(user_repository)
        await notification_service.notify_admins_about_completed_repair(ticket)
        
    except ValueError:
        await callback.message.answer("❌ Ошибка: неверный номер заявки")
    
    await callback.answer()

# Старые функции (оставляем для обратной совместимости)
@router.callback_query(F.data == "ticket_repair_confirm")
async def ticket_repair_confirm_old(
    callback: types.CallbackQuery,
    repair_repository: RepairRepository,
    user_repository: UserRepository
):
    tickets = repair_repository.get_by_tg_id(callback.from_user.id)
    process_tickets = [t for t in tickets if t.status == RepairStatus.PROCESS]
    
    if not process_tickets:
        await callback.message.answer("Нет заявок для подтверждения")
        return
    
    ticket = process_tickets[0]
    
    # Проверяем, что администратор назначил дату и место
    if ticket.date_repair == "0" or ticket.place_repair == "0":
        await callback.message.answer(
            f"❌ Администратор ещё не назначил дату и место ремонта\n"
            f"Ожидайте обработки заявки администратором"
        )
        return
    
    success = repair_repository.confirm_ticket_repair(ticket.id_ticket)
    
    if not success:
        await callback.message.answer("Ошибка при подтверждении заявки")
        return
    
    from services.notification_service import NotificationService
    notification_service = NotificationService(user_repository)
    await notification_service.notify_about_confirmed_repair(ticket)
    
    # Редактируем сообщение вместо удаления
    await callback.message.edit_text(
        f"✅ Заявка № {ticket.id_ticket} подтверждена\n"
        f"Статус: 📨 Ожидает ремонта"
    )
    
    # Отправляем новое сообщение со следующей кнопкой
    await callback.message.answer(
        f"Заявка № {ticket.id_ticket} готова к выезду\n"
        f"Подтвердите, когда будете готовы выехать на ремонт:",
        reply_markup=get_ticket_proc_repair_driver_keyboard(ticket.id_ticket)
    )

@router.callback_query(F.data == "ticket_repair_proc_repair")
async def ticket_repair_proc_repair_old(
    callback: types.CallbackQuery,
    repair_repository: RepairRepository,
    user_repository: UserRepository
):
    tickets = repair_repository.get_by_tg_id(callback.from_user.id)
    confirm_tickets = [t for t in tickets if t.status == RepairStatus.CONFIRM]
    
    if not confirm_tickets:
        await callback.message.answer("Нет заявок для обработки")
        return
    
    ticket = confirm_tickets[0]
    success = repair_repository.proc_repair_ticket_repair(ticket.id_ticket)
    
    if not success:
        await callback.message.answer("Ошибка при обновлении статуса")
        return
    
    from services.notification_service import NotificationService
    notification_service = NotificationService(user_repository)
    await notification_service.notify_admins_about_departure_for_repair(ticket)
    
    # Редактируем сообщение вместо удаления
    await callback.message.edit_text(
        f"✅ Вы подтвердили выезд на ремонт\n"
        f"Статус: 🛻 Выехал на ремонт"
    )
    
    # Отправляем новое сообщение со следующей кнопкой
    await callback.message.answer(
        f"Заявка № {ticket.id_ticket} в процессе ремонта\n"
        f"Когда закончите ремонт, подтвердите его окончание:",
        reply_markup=get_ticket_conf_repair_driver_keyboard(ticket.id_ticket)
    )

@router.callback_query(F.data == "ticket_repair_conf_repair")
async def ticket_repair_conf_repair_old(
    callback: types.CallbackQuery,
    repair_repository: RepairRepository,
    user_repository: UserRepository
):
    tickets = repair_repository.get_by_tg_id(callback.from_user.id)
    proc_repair_tickets = [t for t in tickets if t.status == RepairStatus.PROC_REPAIR]
    
    if not proc_repair_tickets:
        await callback.message.answer("Нет заявок для подтверждения окончания ремонта")
        return
    
    ticket = proc_repair_tickets[0]
    success = repair_repository.conf_repair_ticket_repair(ticket.id_ticket)
    
    if not success:
        await callback.message.answer("Ошибка при подтверждении окончания ремонта")
        return
    
    from services.notification_service import NotificationService
    notification_service = NotificationService(user_repository)
    await notification_service.notify_admins_about_completed_repair(ticket)
    
    # Редактируем сообщение вместо удаления
    await callback.message.edit_text(
        f"✅ Вы подтвердили окончание ремонта\n"
        f"Статус: 🛠 Отремонтирована"
    )
    
    # Отправляем финальное сообщение
    await callback.message.answer(
        f"🎉 Ремонт заявки № {ticket.id_ticket} завершен!\n"
        f"Ожидайте подтверждения администратора."
    )