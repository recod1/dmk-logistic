# handlers/accountant/salary.py
import html
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile
from utils.telegram_helpers import copy_link_fio, copy_link_text
from keyboards.admin_kb import (
    get_admin_main_keyboard,
    get_admin_salary_keyboard,
    get_admin_period_selection_keyboard,
    get_admin_months_keyboard
)
from states.salary_states import AdminSalaryDateState, AdminExportPeriodState
from database.repositories.user_repository import UserRepository
from database.repositories.salary_repository import SalaryRepository
import csv
import os
import tempfile
from datetime import datetime
import calendar

router = Router()

def create_admin_csv_file(salaries: list, driver_name: str, period_info: str) -> str:
    """Создает CSV файл с расчетами для администратора в хронологическом порядке"""
    temp_dir = tempfile.mkdtemp()
    filename = f"расчеты_{driver_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(temp_dir, filename)
    
    salaries_sorted = sorted(
        salaries, 
        key=lambda x: datetime.strptime(x.date_salary, "%d.%m.%Y")
    )
    
    fieldnames = [
        'ID', 'Дата', 'г/мг/рд/пр', 'Окл', 'Сут', 'Загр 2р', 'Шаттл', 'Загр/выгр', 'Штора', 'Возврат',
        'Доп шаттл', 'Доп точка', 'АЗС', 'Паллет гипер', 'Паллет метро', 'Паллет ашан',
        '3', '3.5', '5', '10', '12', '12.5', 'Пробег', 'Комп. связи', 'Стаж', '10%', 'Премия',
        'Удержать', 'Возмещение', 'ДР', 'Без сут/ДР/прем/стажа', 'В день', 'ЗП',
        'Адрес загрузки', 'Адрес выгрузки', 'Транспорт', 'Прицеп', '№ рейса', 'Статус', 'Комментарий'
    ]
    
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        
        csvfile.write(f'Период: {period_info}\n')
        csvfile.write(f'Водитель: {driver_name}\n\n')
        
        writer.writerow(fieldnames)
        
        total_zp = 0
        confirmed_count = 0
        unconfirmed_count = 0
        commented_count = 0
        
        for salary in salaries_sorted:
            status_text = ""
            if salary.status_driver == "confirmed":
                status_text = "Подтверждено"
                confirmed_count += 1
            elif salary.status_driver == "commented":
                status_text = "С комментарием"
                commented_count += 1
                unconfirmed_count += 1
            else:
                status_text = "Не подтверждено"
                unconfirmed_count += 1
            
            row = [
                salary.id,
                salary.date_salary,
                salary.type_route if salary.type_route and salary.type_route != " " else "",
                str(salary.sum_status) if salary.sum_status > 0 else "",
                str(salary.sum_daily) if salary.sum_daily > 0 else "",
                str(salary.load_2_trips) if salary.load_2_trips > 0 else "",
                str(salary.calc_shuttle) if salary.calc_shuttle > 0 else "",
                str(salary.sum_load_unload) if salary.sum_load_unload > 0 else "",
                str(salary.sum_curtain) if salary.sum_curtain > 0 else "",
                str(salary.sum_return) if salary.sum_return > 0 else "",
                str(salary.sum_add_shuttle) if salary.sum_add_shuttle > 0 else "",
                str(salary.sum_add_point) if salary.sum_add_point > 0 else "",
                str(salary.sum_gas_station) if salary.sum_gas_station > 0 else "",
                str(salary.pallets_hyper) if salary.pallets_hyper > 0 else "",
                str(salary.pallets_metro) if salary.pallets_metro > 0 else "",
                str(salary.pallets_ashan) if salary.pallets_ashan > 0 else "",
                str(salary.rate_3km) if salary.rate_3km > 0 else "",
                str(salary.rate_3_5km) if salary.rate_3_5km > 0 else "",
                str(salary.rate_5km) if salary.rate_5km > 0 else "",
                str(salary.rate_10km) if salary.rate_10km > 0 else "",
                str(salary.rate_12km) if salary.rate_12km > 0 else "",
                str(salary.rate_12_5km) if salary.rate_12_5km > 0 else "",
                str(salary.mileage) if salary.mileage > 0 else "",
                str(salary.sum_cell_compensation) if salary.sum_cell_compensation > 0 else "",
                str(salary.experience) if salary.experience > 0 else "",
                str(salary.percent_10) if salary.percent_10 > 0 else "",
                str(salary.sum_bonus) if salary.sum_bonus > 0 else "",
                str(salary.withhold) if salary.withhold > 0 else "",
                str(salary.compensation) if salary.compensation > 0 else "",
                str(salary.dr) if salary.dr > 0 else "",
                str(salary.sum_without_daily_dr_bonus_exp) if salary.sum_without_daily_dr_bonus_exp > 0 else "",
                str(salary.sum_without_daily_dr_bonus) if salary.sum_without_daily_dr_bonus > 0 else "",
                f"{salary.total:.2f}" if isinstance(salary.total, (int, float)) else str(salary.total),
                salary.load_address if salary.load_address and salary.load_address.strip() else "",
                salary.unload_address if salary.unload_address and salary.unload_address.strip() else "",
                salary.transport if salary.transport and salary.transport.strip() else "",
                salary.trailer_number if salary.trailer_number and salary.trailer_number.strip() else "",
                salary.route_number if salary.route_number and salary.route_number.strip() else "",
                status_text,
                salary.comment_driver if salary.comment_driver and salary.comment_driver != " " else ""
            ]
            writer.writerow(row)
            
            try:
                total_zp += float(salary.total)
            except (ValueError, TypeError):
                pass
        
        csvfile.write('\n')
        csvfile.write(f'ИТОГО ЗП: {total_zp:.2f}\n')
        csvfile.write(f'Всего записей: {len(salaries)}\n')
        csvfile.write(f'Подтверждено: {confirmed_count}\n')
        csvfile.write(f'С комментариями: {commented_count}\n')
        csvfile.write(f'Ожидают подтверждения: {unconfirmed_count}\n')
    
    return filepath

@router.message(F.text == "💸 Зарплата")
async def admin_salary_menu(message: types.Message):
    await message.reply("Меню зарплаты:", reply_markup=get_admin_salary_keyboard())

@router.message(F.text == "💰 Загрузить расчет за день")
async def accountant_load_salary(message: types.Message):
    await message.reply("❌ Загрузка расчетов доступна только администраторам")

@router.message(F.text == "📅 Найти расчет за день")
async def admin_find_salary_start(message: types.Message, state: FSMContext):
    await state.set_state(AdminSalaryDateState.driver)
    await state.update_data(action="find_salary")
    await message.reply(
        "👤 Введите ФИО водителя для поиска расчета:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@router.message(AdminSalaryDateState.driver)
async def admin_find_salary_get_driver(
    message: types.Message,
    state: FSMContext,
    user_repository: UserRepository
):
    data = await state.get_data()
    
    if data.get("action") != "find_salary":
        return
    
    driver_name = message.text.strip()
    await state.update_data(driver=driver_name)
    
    users = user_repository.search_drivers_by_name_part(driver_name, limit=15)
    if not users:
        await state.clear()
        await message.reply("❌ Пользователь не найден или не активирован", reply_markup=get_admin_salary_keyboard())
        return
    if len(users) == 1:
        u = users[0]
        if not u.tg_id or str(u.tg_id) == "0":
            await state.clear()
            await message.reply("❌ Пользователь не активирован в боте.", reply_markup=get_admin_salary_keyboard())
            return
        await state.update_data(driver_tg_id=u.tg_id, driver_name=u.name)
        await state.set_state(AdminSalaryDateState.date)
        await message.reply(
            f"✅ Водитель найден: {copy_link_fio(u.name)}\n"
            f"📞 Телефон: {html.escape(u.phone or '')}\n\n"
            "📅 Введите дату расчета (дд.мм.гггг):",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML",
        )
        return
    builder = InlineKeyboardBuilder()
    for u in users[:10]:
        if u.tg_id and str(u.tg_id) != "0":
            builder.row(types.InlineKeyboardButton(text=u.name, callback_data=f"salary_driver_select_{u.tg_id}"))
    await state.update_data(salary_driver_action="find_salary")
    await message.reply("Выберите водителя:", reply_markup=builder.as_markup())

@router.message(AdminSalaryDateState.date)
async def admin_find_salary_process(
    message: types.Message,
    state: FSMContext,
    salary_repository: SalaryRepository,
    user_repository: UserRepository
):
    data = await state.get_data()
    
    if data.get("action") != "find_salary":
        return
    
    date_salary = message.text.strip()
    driver_tg_id = data.get("driver_tg_id")
    driver_name = data.get("driver_name")
    
    salaries = salary_repository.get_by_id_date(driver_tg_id, date_salary)
    
    if not salaries:
        await message.reply(
            f"📭 Расчетов для водителя {copy_link_fio(driver_name)} за {html.escape(date_salary)} не найдено.",
            reply_markup=get_admin_salary_keyboard(),
            parse_mode="HTML",
        )
        await state.clear()
        return
    
    await message.reply(
        f"📊 Найдено расчетов для {copy_link_fio(driver_name)} за {html.escape(date_salary)}: {len(salaries)}",
        reply_markup=get_admin_salary_keyboard(),
        parse_mode="HTML",
    )
    for salary in salaries:
        text = f"📊 ID расчета: {salary.id}\n"
        text += f"👤 Водитель: {copy_link_fio(driver_name)}\n"
        text += f"📅 Расчет за {salary.date_salary}\n\n"
        
        field_names = {
            'type_route': 'г/мг/рд/пр',
            'sum_status': 'Окл',
            'sum_daily': 'Сут',
            'load_2_trips': 'Загр 2р',
            'calc_shuttle': 'Шаттл',
            'sum_load_unload': 'Загр/выгр',
            'sum_curtain': 'Штора',
            'sum_return': 'Возврат',
            'sum_add_shuttle': 'Доп шаттл',
            'sum_add_point': 'Доп точка',
            'sum_gas_station': 'АЗС',
            'mileage': 'Пробег',
            'sum_cell_compensation': 'Комп. связи',
            'experience': 'Стаж',
            'percent_10': '10%',
            'sum_bonus': 'Премия',
            'withhold': 'Удержать',
            'compensation': 'Возмещение',
            'dr': 'ДР',
            'sum_without_daily_dr_bonus_exp': 'Без сут/ДР/прем/стажа',
            'sum_without_daily_dr_bonus': 'В день',
            'total': 'ЗП'
        }
        
        added_fields = []
        for field, name in field_names.items():
            value = getattr(salary, field, 0)
            if isinstance(value, (int, float)):
                if value > 0:
                    if field == 'total':
                        added_fields.append(f"💰 {name}: {value:.2f}")
                    else:
                        added_fields.append(f"📝 {name}: {value}")
            elif isinstance(value, str):
                if value and value != "0" and value != " ":
                    added_fields.append(f"📝 {name}: {value}")
        
        pallets_total = getattr(salary, 'pallets_hyper', 0) + getattr(salary, 'pallets_metro', 0) + getattr(salary, 'pallets_ashan', 0)
        if pallets_total > 0:
            added_fields.append(f"📦 Паллет: {pallets_total} (гипер: {salary.pallets_hyper}, метро: {salary.pallets_metro}, ашан: {salary.pallets_ashan})")
        
        for rate_f, label in [('rate_3km', '3'), ('rate_3_5km', '3.5'), ('rate_5km', '5'), ('rate_10km', '10'), ('rate_12km', '12'), ('rate_12_5km', '12.5')]:
            v = getattr(salary, rate_f, 0)
            if v and (isinstance(v, (int, float)) and v > 0):
                added_fields.append(f"📝 {label} р/км: {v}")
        
        if getattr(salary, 'load_address', '') and salary.load_address.strip():
            added_fields.append(f"📍 Загрузка: {salary.load_address}")
        if getattr(salary, 'unload_address', '') and salary.unload_address.strip():
            added_fields.append(f"📍 Выгрузка: {salary.unload_address}")
        if getattr(salary, 'transport', '') and salary.transport.strip():
            added_fields.append(f"🚛 Транспорт: {salary.transport}")
        if getattr(salary, 'trailer_number', '') and salary.trailer_number.strip():
            added_fields.append(f"🛞 Прицеп: {copy_link_text(salary.trailer_number)}")
        if getattr(salary, 'route_number', '') and salary.route_number.strip():
            added_fields.append(f"📋 № рейса: {salary.route_number}")
        
        if added_fields:
            text += "\n".join(added_fields)
        else:
            text += "📭 Все значения равны нулю"
        
        if salary.status_driver == "confirmed":
            text += "\n\n✅ Статус: Подтверждено водителем"
        elif salary.status_driver == "commented":
            text += f"\n\n💬 Статус: С комментарием водителя\n📋 Комментарий: {salary.comment_driver}"
        else:
            text += "\n\n⏳ Статус: Ожидает подтверждения водителем"
        
        await message.answer(text, parse_mode="HTML")
    await state.clear()

@router.message(F.text == "⏳ Не подтвержденные расчеты")
async def show_all_unconfirmed_salaries(
    message: types.Message,
    salary_repository: SalaryRepository,
    user_repository: UserRepository
):
    unconfirmed_salaries = salary_repository.get_all_unconfirmed()
    
    if not unconfirmed_salaries:
        await message.reply("✅ Все расчеты подтверждены водителями.", reply_markup=get_admin_salary_keyboard())
        return
    
    salaries_by_driver = {}
    for salary in unconfirmed_salaries:
        driver_id = salary.id_driver
        if driver_id not in salaries_by_driver:
            salaries_by_driver[driver_id] = []
        salaries_by_driver[driver_id].append(salary)
    
    text = "⏳ Неподтвержденные расчеты:\n\n"
    total_count = len(unconfirmed_salaries)
    unconfirmed_count = 0
    commented_count = 0
    
    for driver_id, driver_salaries in salaries_by_driver.items():
        try:
            driver_id_int = int(driver_id) if driver_id.isdigit() else driver_id
            driver = user_repository.get_by_tg_id(driver_id_int)
        except (ValueError, TypeError):
            driver = None
            
        driver_name = driver.name if driver else f"Водитель (ID: {driver_id})"
        text += f"👤 {copy_link_fio(driver_name)}:\n"
        for i, salary in enumerate(driver_salaries, 1):
            total_count += 1
            
            if salary.status_driver == "commented":
                commented_count += 1
            else:
                unconfirmed_count += 1
            
            date_str = salary.date_salary
            
            status = "ожидает подтверждения"
            status_icon = "⏳"
            if salary.status_driver == "commented":
                status = "с комментарием"
                status_icon = "💬"
            elif salary.status_driver == " " or salary.status_driver == "" or salary.status_driver is None:
                status = "не просмотрен"
                status_icon = "👁️"
            
            text += f"  {i}. {status_icon} ID: {salary.id} - {date_str} - {status}\n"
            
            if salary.comment_driver and salary.comment_driver.strip() and salary.comment_driver != " ":
                text += f"     💬 Комментарий: {salary.comment_driver}\n"
        
        text += "\n"
    
    text += f"📊 Статистика:\n"
    text += f"  • Всего: {len(unconfirmed_salaries)}\n"
    text += f"  • Ожидают подтверждения: {unconfirmed_count}\n"
    text += f"  • С комментариями: {commented_count}\n"
    
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
        
        for i, part in enumerate(parts):
            if i == 0:
                await message.reply(part, reply_markup=get_admin_salary_keyboard(), parse_mode="HTML")
            else:
                await message.answer(part, parse_mode="HTML")
    else:
        await message.reply(text, reply_markup=get_admin_salary_keyboard(), parse_mode="HTML")


@router.message(F.text == "💬 С комментариями")
async def show_commented_salaries(
    message: types.Message,
    salary_repository: SalaryRepository,
    user_repository: UserRepository,
):
    """Показать все неподтвержденные расчеты с комментариями водителя."""
    commented_salaries = salary_repository.get_all_unconfirmed_commented()
    if not commented_salaries:
        await message.reply(
            "📭 Нет неподтвержденных расчетов с комментариями.",
            reply_markup=get_admin_salary_keyboard(),
        )
        return
    salaries_by_driver = {}
    for salary in commented_salaries:
        driver_id = salary.id_driver
        if driver_id not in salaries_by_driver:
            salaries_by_driver[driver_id] = []
        salaries_by_driver[driver_id].append(salary)
    text = "💬 Неподтвержденные расчеты с комментариями:\n\n"
    for driver_id, driver_salaries in salaries_by_driver.items():
        try:
            driver_id_int = int(driver_id) if str(driver_id).isdigit() else driver_id
            driver = user_repository.get_by_tg_id(driver_id_int)
        except (ValueError, TypeError):
            driver = None
        driver_name = driver.name if driver else f"Водитель (ID: {driver_id})"
        text += f"👤 {copy_link_fio(driver_name)}:\n"
        for i, salary in enumerate(driver_salaries, 1):
            date_str = salary.date_salary
            text += f"  {i}. 💬 ID: {salary.id} - {html.escape(date_str)}\n"
            if salary.comment_driver and str(salary.comment_driver).strip() and salary.comment_driver != " ":
                text += f"     💬 Комментарий: {salary.comment_driver}\n"
        text += "\n"
    text += f"📊 Всего с комментариями: {len(commented_salaries)}\n"
    if len(text) > 4000:
        parts = []
        while len(text) > 4000:
            last_newline = text[:4000].rfind("\n")
            if last_newline != -1:
                parts.append(text[:last_newline])
                text = text[last_newline + 1 :]
            else:
                parts.append(text[:4000])
                text = text[4000:]
        if text:
            parts.append(text)
        for i, part in enumerate(parts):
            if i == 0:
                await message.reply(part, reply_markup=get_admin_salary_keyboard(), parse_mode="HTML")
            else:
                await message.answer(part, parse_mode="HTML")
    else:
        await message.reply(text, reply_markup=get_admin_salary_keyboard(), parse_mode="HTML")


@router.message(F.text == "📊 Выгрузить расчет за период")
async def admin_export_salaries_start(message: types.Message, state: FSMContext):
    await state.set_state(AdminExportPeriodState.driver)
    await state.update_data(action="admin_export")
    await message.reply(
        "👤 Введите ФИО водителя для выгрузки расчетов:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@router.message(AdminExportPeriodState.driver)
async def admin_export_get_driver(
    message: types.Message,
    state: FSMContext,
    user_repository: UserRepository
):
    data = await state.get_data()
    
    if data.get("action") != "admin_export":
        return
    
    driver_name = message.text.strip()
    await state.update_data(driver=driver_name)
    
    users = user_repository.search_drivers_by_name_part(driver_name, limit=15)
    if not users:
        await state.clear()
        await message.reply("❌ Пользователь не найден или не активирован", reply_markup=get_admin_salary_keyboard())
        return
    if len(users) == 1:
        u = users[0]
        if not u.tg_id or str(u.tg_id) == "0":
            await state.clear()
            await message.reply("❌ Пользователь не активирован в боте.", reply_markup=get_admin_salary_keyboard())
            return
        await state.update_data(driver_tg_id=u.tg_id, driver_name=u.name)
        await state.set_state(AdminExportPeriodState.period_type)
        await message.reply(
            f"✅ Водитель найден: {copy_link_fio(u.name)}\n"
            f"📞 Телефон: {html.escape(u.phone or '')}\n\n"
            "📊 Выберите период для выгрузки расчетов:",
            reply_markup=get_admin_period_selection_keyboard(),
            parse_mode="HTML",
        )
        return
    builder = InlineKeyboardBuilder()
    for u in users[:10]:
        if u.tg_id and str(u.tg_id) != "0":
            builder.row(types.InlineKeyboardButton(text=u.name, callback_data=f"salary_driver_select_{u.tg_id}"))
    await state.update_data(salary_driver_action="admin_export")
    await message.reply("Выберите водителя:", reply_markup=builder.as_markup())

@router.message(AdminExportPeriodState.period_type)
async def admin_handle_period_type(
    message: types.Message,
    state: FSMContext,
    salary_repository: SalaryRepository,
    user_repository: UserRepository
):
    period_type = message.text
    today = datetime.now()
    data = await state.get_data()
    
    # if period_type == "↩️ Назад":
    #     await state.clear()
    #     await message.reply("Меню зарплаты:", reply_markup=get_admin_salary_keyboard())
    #     return
    
    if period_type == "📊 С начала месяца":
        start_date = today.replace(day=1)
        start_date_str = start_date.strftime("%d.%m.%Y")
        end_date_str = today.strftime("%d.%m.%Y")
        
        await state.update_data(
            start_date=start_date_str,
            end_date=end_date_str,
            period_info=f"с начала месяца ({start_date_str} - {end_date_str})"
        )
        await admin_process_export(message, state, salary_repository, user_repository)
        
    elif period_type == "📋 Выбрать месяц":
        await state.set_state(AdminExportPeriodState.month_year)
        await message.reply(
            "Выберите месяц:",
            reply_markup=get_admin_months_keyboard()
        )
        
    elif period_type == "📑 Произвольный период":
        await state.set_state(AdminExportPeriodState.custom_start)
        await message.reply(
            "Введите начальную дату периода (дд.мм.гггг):\nПример: 01.01.2024",
            reply_markup=types.ReplyKeyboardRemove()
        )
        
    else:
        await message.reply("Пожалуйста, выберите вариант из меню.")

@router.message(AdminExportPeriodState.month_year)
async def admin_handle_month_selection(
    message: types.Message,
    state: FSMContext,
    salary_repository: SalaryRepository,
    user_repository: UserRepository
):
    month_name = message.text
    data = await state.get_data()
    
    # if month_name == "↩️ Назад":
    #     await state.set_state(AdminExportPeriodState.period_type)
    #     await message.reply(
    #         "📊 Выберите период для выгрузки расчетов:",
    #         reply_markup=get_admin_period_selection_keyboard()
    #     )
    #     return
    
    month_names = {
        "Январь": 1, "Февраль": 2, "Март": 3, "Апрель": 4,
        "Май": 5, "Июнь": 6, "Июль": 7, "Август": 8,
        "Сентябрь": 9, "Октябрь": 10, "Ноябрь": 11, "Декабрь": 12
    }
    
    if month_name in month_names:
        month_num = month_names[month_name]
        today = datetime.now()
        year = today.year
        
        start_date = datetime(year, month_num, 1)
        start_date_str = start_date.strftime("%d.%m.%Y")
        
        last_day = calendar.monthrange(year, month_num)[1]
        end_date = datetime(year, month_num, last_day)
        end_date_str = end_date.strftime("%d.%m.%Y")
        
        await state.update_data(
            start_date=start_date_str,
            end_date=end_date_str,
            period_info=f"за {month_name.lower()} {year} года"
        )
        await admin_process_export(message, state, salary_repository, user_repository)
    else:
        await message.reply("Пожалуйста, выберите месяц из списка.")

@router.message(AdminExportPeriodState.custom_start)
async def admin_handle_custom_start_date(
    message: types.Message,
    state: FSMContext
):
    data = await state.get_data()
    
    if data.get("action") != "admin_export":
        return
    
    start_date = message.text.strip()
    
    try:
        datetime.strptime(start_date, "%d.%m.%Y")
        await state.update_data(start_date=start_date)
        await state.set_state(AdminExportPeriodState.custom_end)
        await message.reply(
            f"Начальная дата: {start_date}\nВведите конечную дату периода (дд.мм.гггг):\nПример: 31.01.2024"
        )
    except ValueError:
        await message.reply("Неверный формат даты. Пожалуйста, используйте формат дд.мм.гггг")

@router.message(AdminExportPeriodState.custom_end)
async def admin_handle_custom_end_date(
    message: types.Message,
    state: FSMContext,
    salary_repository: SalaryRepository,
    user_repository: UserRepository
):
    data = await state.get_data()
    
    if data.get("action") != "admin_export":
        return
    
    end_date = message.text.strip()
    
    try:
        datetime.strptime(end_date, "%d.%m.%Y")
        data = await state.get_data()
        start_date = data.get("start_date")
        
        start_dt = datetime.strptime(start_date, "%d.%m.%Y")
        end_dt = datetime.strptime(end_date, "%d.%m.%Y")
        
        if start_dt > end_dt:
            await message.reply("Начальная дата не может быть позже конечной. Попробуйте снова.")
            await state.set_state(AdminExportPeriodState.custom_start)
            await message.reply("Введите начальную дату периода (дд.мм.гггг):")
        else:
            await state.update_data(
                end_date=end_date,
                period_info=f"за период с {start_date} по {end_date}"
            )
            await admin_process_export(message, state, salary_repository, user_repository)
    except ValueError:
        await message.reply("Неверный формат даты. Пожалуйста, используйте формат дд.мм.гггг")

async def admin_process_export(
    message: types.Message,
    state: FSMContext,
    salary_repository: SalaryRepository,
    user_repository: UserRepository
):
    data = await state.get_data()
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    period_info = data.get("period_info")
    driver_tg_id = data.get("driver_tg_id")
    driver_name = data.get("driver_name")
    
    all_salaries = salary_repository.get_all()
    driver_salaries = [s for s in all_salaries if s.id_driver == driver_tg_id]
    
    if not driver_salaries:
        await message.reply(
            f"📭 У водителя {copy_link_fio(driver_name)} нет расчетов.",
            reply_markup=get_admin_salary_keyboard(),
            parse_mode="HTML",
        )
        await state.clear()
        return
    filtered_salaries = []
    start_dt = datetime.strptime(start_date, "%d.%m.%Y")
    end_dt = datetime.strptime(end_date, "%d.%m.%Y")
    
    for salary in driver_salaries:
        try:
            salary_date = datetime.strptime(salary.date_salary, "%d.%m.%Y")
            if start_dt <= salary_date <= end_dt:
                filtered_salaries.append(salary)
        except ValueError:
            continue
    
    if not filtered_salaries:
        await message.reply(
            f"📭 За период {html.escape(period_info)} расчетов не найдено для водителя {copy_link_fio(driver_name)}.",
            reply_markup=get_admin_salary_keyboard(),
            parse_mode="HTML",
        )
        await state.clear()
        return
    try:
        filepath = create_admin_csv_file(filtered_salaries, driver_name, period_info)
        
        await message.answer_document(
            FSInputFile(filepath),
            caption=(
                f"📊 Выгрузка расчетов {period_info}\n\n"
                f"📅 Период: {start_date} - {end_date}\n"
                f"📋 Количество записей: {len(filtered_salaries)}\n"
                f"👤 Водитель: {copy_link_fio(driver_name)}"
            ),
            parse_mode="HTML",
        )
        
        os.remove(filepath)
        os.rmdir(os.path.dirname(filepath))
        
    except Exception as e:
        print(f"Ошибка при создании файла: {e}")
        await message.reply(
            f"Произошла ошибка при создании файла: {str(e)}",
            reply_markup=get_admin_salary_keyboard()
        )
    
    await state.clear()

@router.message(F.text == "🗑️ Удалить расчет")
async def delete_salary(message: types.Message):
    await message.reply("❌ Удаление расчетов доступно только администраторам")

# @router.message(F.text == "↩️ Назад")
# async def exit_to_main(message: types.Message, state: FSMContext = None):
#     if state:
#         current_state = await state.get_state()
#         if current_state:
#             await state.clear()
#     await message.reply("Назад", reply_markup=get_admin_main_keyboard())