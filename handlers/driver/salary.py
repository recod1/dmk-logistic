from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from utils.telegram_helpers import copy_link_fio, copy_link_text
from keyboards.driver_kb import (
    get_driver_main_keyboard,
    get_driver_salary_keyboard,
    get_driver_period_selection_keyboard,
    get_driver_months_keyboard
)
from states.salary_states import DriverSalaryDateState, DriverCommentState, DriverExportPeriodState
from database.repositories.salary_repository import SalaryRepository
from database.repositories.user_repository import UserRepository
from aiogram.utils.keyboard import InlineKeyboardBuilder
import csv
import os
import tempfile
from datetime import datetime
import calendar

router = Router()

def format_salary_for_driver(salary) -> str:
    """Форматирует сообщение о зарплате с учетом ID расчета (поля модели Salary)"""
    text = f"📊 Расчет ID: {salary.id}\n"
    text += f"📅 Дата: {salary.date_salary}\n\n"
    
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
        text += "\n\n✅ Статус: Подтверждено"
    elif salary.status_driver == "commented":
        text += f"\n\n💬 Статус: С комментарием\n📋 Комментарий: {salary.comment_driver}"
    else:
        text += "\n\n⏳ Статус: Ожидает подтверждения"
    
    return text

def get_salary_confirmation_keyboard(salary_id: int):
    """Клавиатура для подтверждения конкретного расчета по ID"""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_salary_{salary_id}"),
        types.InlineKeyboardButton(text="💬 Комментарий", callback_data=f"comment_salary_{salary_id}")
    )
    return builder.as_markup()

def get_salary_confirmed_keyboard(salary_id: int):
    """Клавиатура для подтверждённого расчёта: возможность добавить комментарий (если нашли ошибку)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="💬 Добавить комментарий", callback_data=f"comment_salary_{salary_id}")
    )
    return builder.as_markup()

def create_csv_file(salaries: list, driver_name: str, period_info: str) -> str:
    """Создает CSV файл с расчетами в хронологическом порядке"""
    temp_dir = tempfile.mkdtemp()
    filename = f"расчеты_{driver_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(temp_dir, filename)
    
    # СОРТИРУЕМ по дате в хронологическом порядке
    salaries_sorted = sorted(
        salaries, 
        key=lambda x: datetime.strptime(x.date_salary, "%d.%m.%Y")
    )
    
    fieldnames = [
        'ID', 'Дата', 'г/мг/рд/пр', 'Окл', 'Сут', 'Загр 2р', 'Шаттл', 'Загр/выгр', 'Штора', 'Возврат',
        'Доп шаттл', 'Доп точка', 'АЗС', 'Паллет гипер', 'Паллет метро', 'Паллет ашан',
        '3', '3.5', '5', '10', '12', '12.5', 'Пробег', 'Комп. связи', 'Стаж', '10%', 'Премия',
        'Удержать', 'Возмещение', 'ДР', 'Без сут/ДР/прем/стажа', 'В день', 'ЗП',
        'Адрес загрузки', 'Адрес выгрузки', 'Транспорт', 'Прицеп', '№ рейса', 'Статус'
    ]
    
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        
        csvfile.write(f'Период: {period_info}\n')
        csvfile.write(f'Водитель: {driver_name}\n\n')
        
        writer.writerow(fieldnames)
        
        total_zp = 0
        confirmed_count = 0
        unconfirmed_count = 0
        
        for salary in salaries_sorted:
            status_text = ""
            if salary.status_driver == "confirmed":
                status_text = "Подтверждено"
                confirmed_count += 1
            elif salary.status_driver == "commented":
                status_text = "С комментарием"
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
                status_text
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
        csvfile.write(f'Ожидают подтверждения: {unconfirmed_count}\n')
    
    return filepath

@router.message(F.text == "💵 Зарплата")
async def ticket_repair_menu(message: types.Message):
    await message.reply("Меню зарплаты:", reply_markup=get_driver_salary_keyboard())

@router.message(F.text == "📅 Показать расчет за день")
async def show_salary_for_day(message: types.Message, state: FSMContext):
    await state.set_state(DriverSalaryDateState.date)
    await message.reply(
        "Введите день расчета в формате 'дд.мм.гггг'\nПример: 15.01.2026", 
        reply_markup=get_driver_salary_keyboard()
    )

@router.message(DriverSalaryDateState.date)
async def get_salary_date_driver(
    message: types.Message,
    state: FSMContext,
    salary_repository: SalaryRepository
):
    user_id = str(message.chat.id)
    date_input = message.text.strip()
    
    try:
        # Проверяем формат даты
        datetime.strptime(date_input, "%d.%m.%Y")
    except ValueError:
        await message.reply(
            "❌ Неверный формат даты. Используйте формат 'дд.мм.гггг'\nПример: 15.01.2026",
            reply_markup=get_driver_salary_keyboard()
        )
        await state.clear()
        return
    
    salaries = salary_repository.get_by_id_date(user_id, date_input)
    
    if not salaries:
        await message.reply(
            f"📭 Расчетов за {date_input} не найдено",
            reply_markup=get_driver_salary_keyboard()
        )
        await state.clear()
        return
    
    # Отправляем каждый расчет отдельным сообщением с кнопками
    for salary in salaries:
        text = format_salary_for_driver(salary)
        
        if salary.status_driver != "confirmed":
            await message.answer(text, reply_markup=get_salary_confirmation_keyboard(salary.id), parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=get_salary_confirmed_keyboard(salary.id), parse_mode="HTML")
    
    await message.answer(
        f"📊 Найдено расчетов за {date_input}: {len(salaries)}",
        reply_markup=get_driver_salary_keyboard()
    )
    
    await state.clear()

@router.message(F.text == "🔄 Не подтвержденные расчеты")
async def show_unconfirmed_salaries(
    message: types.Message,
    salary_repository: SalaryRepository,
    user_repository: UserRepository
):
    user_id = str(message.chat.id)
    
    unconfirmed_salaries = salary_repository.get_unconfirmed_by_driver(user_id)
    
    if not unconfirmed_salaries:
        await message.reply(
            "✅ У вас нет неподтвержденных расчетов.",
            reply_markup=get_driver_salary_keyboard()
        )
        return
    
    # Группируем по датам
    salaries_by_date = {}
    for salary in unconfirmed_salaries:
        if salary.date_salary not in salaries_by_date:
            salaries_by_date[salary.date_salary] = []
        salaries_by_date[salary.date_salary].append(salary)
    
    text = f"⏳ Неподтвержденные расчеты ({len(unconfirmed_salaries)}):\n\n"
    
    for date_str, date_salaries in salaries_by_date.items():
        text += f"📅 {date_str} ({len(date_salaries)} расчетов):\n"
        
        for salary in date_salaries:
            status_icon = "⏳"
            if salary.status_driver == "commented":
                status_icon = "💬"
            elif salary.status_driver == " " or salary.status_driver == "" or salary.status_driver is None:
                status_icon = "👁️"
            
            text += f"  {status_icon} ID: {salary.id}"
            
            if salary.comment_driver and salary.comment_driver.strip() and salary.comment_driver != " ":
                text += f" - с комментарием"
            
            text += "\n"
        
        text += "\n"
    
    text += "\n👇 Выберите расчет для подтверждения:"
    
    # Отправляем список
    if len(text) > 4000:
        # Разбиваем длинное сообщение
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
                await message.reply(part, reply_markup=get_driver_salary_keyboard(), parse_mode="HTML")
            else:
                await message.answer(part, parse_mode="HTML")
    else:
        await message.reply(text, reply_markup=get_driver_salary_keyboard(), parse_mode="HTML")
    
    # Отправляем каждый расчет отдельным сообщением с кнопками
    for salary in unconfirmed_salaries:
        text = format_salary_for_driver(salary)
        await message.answer(text, reply_markup=get_salary_confirmation_keyboard(salary.id), parse_mode="HTML")

@router.message(F.text == "🗂 Выгрузить расчет за период")
async def driver_export_salaries_start(message: types.Message, state: FSMContext):
    await state.set_state(DriverExportPeriodState.period_type)
    await message.reply(
        "📊 Выберите период для выгрузки расчетов:",
        reply_markup=get_driver_period_selection_keyboard()
    )

@router.message(DriverExportPeriodState.period_type)
async def driver_handle_period_type(
    message: types.Message,
    state: FSMContext,
    salary_repository: SalaryRepository,
    user_repository: UserRepository
):
    period_type = message.text
    today = datetime.now()
    
    # if period_type == "🔙 Назад":
    #     await state.clear()
    #     await message.reply("Меню зарплаты:", reply_markup=get_driver_salary_keyboard())
    #     return
    
    if period_type == "📅 С начала месяца":
        start_date = today.replace(day=1)
        start_date_str = start_date.strftime("%d.%m.%Y")
        end_date_str = today.strftime("%d.%m.%Y")
        
        await state.update_data(
            start_date=start_date_str,
            end_date=end_date_str,
            period_info=f"с начала месяца ({start_date_str} - {end_date_str})"
        )
        await driver_process_export(message, state, salary_repository, user_repository)
        
    elif period_type == "🗓️ Выбрать месяц":
        await state.set_state(DriverExportPeriodState.month_year)
        await message.reply(
            "Выберите месяц:",
            reply_markup=get_driver_months_keyboard()
        )
        
    elif period_type == "📝 Произвольный период":
        await state.set_state(DriverExportPeriodState.custom_start)
        await message.reply(
            "Введите начальную дату периода (дд.мм.гггг):\nПример: 01.01.2024",
            reply_markup=types.ReplyKeyboardRemove()
        )
        
    else:
        await message.reply("Пожалуйста, выберите вариант из меню.")

@router.message(DriverExportPeriodState.month_year)
async def driver_handle_month_selection(
    message: types.Message,
    state: FSMContext,
    salary_repository: SalaryRepository,
    user_repository: UserRepository
):
    month_name = message.text
    
    # if month_name == "🔙 Назад":
    #     await state.set_state(DriverExportPeriodState.period_type)
    #     await message.reply(
    #         "📊 Выберите период для выгрузки расчетов:",
    #         reply_markup=get_driver_period_selection_keyboard()
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
        await driver_process_export(message, state, salary_repository, user_repository)
    else:
        await message.reply("Пожалуйста, выберите месяц из списка.")

@router.message(DriverExportPeriodState.custom_start)
async def driver_handle_custom_start_date(
    message: types.Message,
    state: FSMContext
):
    start_date = message.text.strip()
    
    try:
        datetime.strptime(start_date, "%d.%m.%Y")
        await state.update_data(start_date=start_date)
        await state.set_state(DriverExportPeriodState.custom_end)
        await message.reply(
            f"Начальная дата: {start_date}\nВведите конечную дату периода (дд.мм.гггг):\nПример: 31.01.2024"
        )
    except ValueError:
        await message.reply("Неверный формат даты. Пожалуйста, используйте формат дд.мм.гггг")

@router.message(DriverExportPeriodState.custom_end)
async def driver_handle_custom_end_date(
    message: types.Message,
    state: FSMContext,
    salary_repository: SalaryRepository,
    user_repository: UserRepository
):
    end_date = message.text.strip()
    
    try:
        datetime.strptime(end_date, "%d.%m.%Y")
        data = await state.get_data()
        start_date = data.get("start_date")
        
        start_dt = datetime.strptime(start_date, "%d.%m.%Y")
        end_dt = datetime.strptime(end_date, "%d.%m.%Y")
        
        if start_dt > end_dt:
            await message.reply("Начальная дата не может быть позже конечной. Попробуйте снова.")
            await state.set_state(DriverExportPeriodState.custom_start)
            await message.reply("Введите начальную дату периода (дд.мм.гггг):")
        else:
            await state.update_data(
                end_date=end_date,
                period_info=f"за период с {start_date} по {end_date}"
            )
            await driver_process_export(message, state, salary_repository, user_repository)
    except ValueError:
        await message.reply("Неверный формат даты. Пожалуйста, используйте формат дд.мм.гггг")

async def driver_process_export(
    message: types.Message,
    state: FSMContext,
    salary_repository: SalaryRepository,
    user_repository: UserRepository
):
    data = await state.get_data()
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    period_info = data.get("period_info")
    
    user_id = str(message.chat.id)
    
    # Получаем все расчеты водителя
    all_salaries = salary_repository.get_all()
    driver_salaries = [s for s in all_salaries if s.id_driver == user_id]
    
    if not driver_salaries:
        await message.reply(
            f"📭 У вас нет расчетов за указанный период.",
            reply_markup=get_driver_salary_keyboard()
        )
        await state.clear()
        return
    
    # Фильтруем по дате
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
            f"📭 За период {period_info} расчетов не найдено.",
            reply_markup=get_driver_salary_keyboard()
        )
        await state.clear()
        return
    
    driver = user_repository.get_by_tg_id(int(user_id))
    driver_name = driver.name if driver else f"Водитель {user_id}"
    
    try:
        filepath = create_csv_file(filtered_salaries, driver_name, period_info)
        
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
            reply_markup=get_driver_salary_keyboard()
        )
    
    await state.clear()

@router.callback_query(F.data.startswith("confirm_salary_"))
async def confirm_salary_callback(
    callback: types.CallbackQuery,
    salary_repository: SalaryRepository,
    user_repository: UserRepository
):
    try:
        salary_id = int(callback.data.split("_")[2])
        user_id = str(callback.from_user.id)
        
        salary = salary_repository.get_by_id_int(salary_id)
        
        if not salary:
            await callback.message.edit_text("❌ Расчет не найден")
            return
        
        # Проверяем, что расчет принадлежит этому водителю
        if salary.id_driver != user_id:
            await callback.message.edit_text("❌ Это не ваш расчет")
            return
        
        # Обновляем статус
        success = salary_repository.update_status(salary_id, "confirmed")
        
        if not success:
            await callback.message.edit_text("❌ Ошибка при подтверждении расчета")
            return
        
        # Редактируем сообщение
        new_text = callback.message.text + "\n\n✅ **ПОДТВЕРЖДЕНО**"
        await callback.message.edit_text(new_text)
        
        # Уведомляем администраторов и бухгалтеров
        from services.notification_service import MessageSalary
        message_salary = MessageSalary(salary_repository, user_repository)
        
        driver = user_repository.get_by_tg_id(callback.from_user.id)
        driver_name = driver.name if driver else "Неизвестно"
        
        # ВЫЗОВ НОВОГО МЕТОДА ДЛЯ УВЕДОМЛЕНИЯ БУХГАЛТЕРОВ
        await message_salary.notify_accountants_about_salary_confirmation(
            driver_name=driver_name,
            salary_id=salary_id,
            date_salary=salary.date_salary,
            zp=salary.total
        )
        
    except (ValueError, IndexError):
        await callback.message.edit_text("❌ Ошибка при обработке подтверждения")
    
    await callback.answer()

@router.callback_query(F.data.startswith("comment_salary_"))
async def comment_salary_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    salary_repository: SalaryRepository
):
    try:
        salary_id = int(callback.data.split("_")[2])
        user_id = str(callback.from_user.id)
        
        salary = salary_repository.get_by_id_int(salary_id)
        
        if not salary:
            await callback.message.edit_text("❌ Расчет не найден")
            return
        
        # Проверяем, что расчет принадлежит этому водителю
        if salary.id_driver != user_id:
            await callback.message.edit_text("❌ Это не ваш расчет")
            return
        
        await state.update_data(salary_id=salary_id)
        await state.set_state(DriverCommentState.comment)
        
        await callback.message.edit_text(
            f"✏️ Введите комментарий к расчету:\n\n"
            f"📊 ID расчета: {salary_id}\n"
            f"📅 Дата: {salary.date_salary}\n\n"
            f"Напишите ваш комментарий в следующем сообщении."
        )
        
    except (ValueError, IndexError):
        await callback.message.edit_text("❌ Ошибка при обработке запроса")
    
    await callback.answer()

@router.message(DriverCommentState.comment)
async def save_comment(
    message: types.Message,
    state: FSMContext,
    salary_repository: SalaryRepository,
    user_repository: UserRepository
):
    data = await state.get_data()
    comment = message.text.strip()
    salary_id = data.get("salary_id")
    
    if not salary_id:
        await message.reply("❌ Ошибка: ID расчета не найден", reply_markup=get_driver_main_keyboard())
        await state.clear()
        return
    
    if not comment:
        await message.reply("❌ Комментарий не может быть пустым", reply_markup=get_driver_main_keyboard())
        return
    
    # Обновляем комментарий
    success = salary_repository.update_comment(salary_id, comment)
    
    if not success:
        await message.reply("❌ Ошибка при сохранении комментария", reply_markup=get_driver_main_keyboard())
        await state.clear()
        return
    
    # Получаем обновленный расчет
    salary = salary_repository.get_by_id_int(salary_id)
    
    # Уведомляем администраторов и бухгалтеров
    from services.notification_service import MessageSalary
    message_salary = MessageSalary(salary_repository, user_repository)
    
    driver = user_repository.get_by_tg_id(message.from_user.id)
    driver_name = driver.name if driver else "Неизвестно"
    
    # ВЫЗОВ НОВОГО МЕТОДА ДЛЯ УВЕДОМЛЕНИЯ БУХГАЛТЕРОВ О КОММЕНТАРИИ
    await message_salary.notify_accountants_about_salary_comment(
        driver_name=driver_name,
        salary_id=salary_id,
        date_salary=salary.date_salary if salary else 'неизвестно',
        comment=comment
    )
    
    await message.reply(
        (
            f"✅ Ваш комментарий к расчету ID: {salary_id} сохранен и отправлен администратору.\n\n"
            f"{format_salary_for_driver(salary) if salary else ''}"
        ),
        reply_markup=get_driver_main_keyboard(),
        parse_mode="HTML",
    )
    
    await state.clear()

# @router.message(F.text == "🔙 Назад")
# async def exit_to_main_driver(message: types.Message, state: FSMContext = None):
#     if state:
#         current_state = await state.get_state()
#         if current_state:
#             await state.clear()
    
#     await message.reply("Назад", reply_markup=get_driver_main_keyboard())