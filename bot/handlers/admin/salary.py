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
from states.salary_states import SalaryState, AdminSalaryDateState, DeleteSalaryState, AdminExportPeriodState
from database.repositories.user_repository import UserRepository
from database.repositories.salary_repository import SalaryRepository
from services.notification_service import MessageSalary
import csv
import os
import tempfile
from datetime import datetime
import calendar

router = Router()


def _parse_float(s: str) -> float:
    """Парсит число с запятой или точкой в качестве десятичного разделителя."""
    if not s or not s.strip():
        return 0.0
    return float(s.strip().replace(",", "."))


def _parse_int(s: str) -> int:
    """Парсит целое число (допускается ввод с запятой, например 5,0)."""
    if not s or not s.strip():
        return 0
    return int(round(_parse_float(s)))


def format_salary_message(driver_name: str, salary, show_all: bool = False) -> str:
    """Форматирует сообщение о зарплате с учетом ID расчета (поля модели Salary). HTML, ФИО копируемое."""
    text = f"📊 ID расчета: {salary.id}\n"
    text += f"👤 Водитель: {copy_link_fio(driver_name)}\n"
    text += f"📅 Расчет за {html.escape(salary.date_salary)}\n\n"
    
    # Соответствие полей модели Salary и подписей
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
    
    # Поддоны (сумма или по типам)
    pallets_total = getattr(salary, 'pallets_hyper', 0) + getattr(salary, 'pallets_metro', 0) + getattr(salary, 'pallets_ashan', 0)
    if pallets_total > 0:
        added_fields.append(f"📦 Паллет: {pallets_total} (гипер: {salary.pallets_hyper}, метро: {salary.pallets_metro}, ашан: {salary.pallets_ashan})")
    
    # Тарифы за км
    for rate_f, label in [('rate_3km', '3'), ('rate_3_5km', '3.5'), ('rate_5km', '5'), ('rate_10km', '10'), ('rate_12km', '12'), ('rate_12_5km', '12.5')]:
        v = getattr(salary, rate_f, 0)
        if v and (isinstance(v, (int, float)) and v > 0):
            added_fields.append(f"📝 {label} р/км: {v}")
    
    # Адреса и рейс
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
    
    return text

def get_delete_confirmation_keyboard(salary_id: int):
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="✅ Подтвердить удаление", callback_data=f"confirm_delete_{salary_id}"),
        types.InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_delete")
    )
    return builder.as_markup()

def create_admin_csv_file(salaries: list, driver_name: str, period_info: str) -> str:
    """Создает CSV файл с расчетами для администратора в хронологическом порядке"""
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
async def admin_load_salary_start(message: types.Message, state: FSMContext):
    await state.set_state(SalaryState.driver)
    await state.update_data(action="load_salary")
    await message.reply(
        "👤 Введите ФИО водителя для загрузки расчета:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@router.message(SalaryState.driver)
async def admin_load_salary_get_driver(
    message: types.Message,
    state: FSMContext,
    user_repository: UserRepository
):
    data = await state.get_data()
    
    if data.get("action") != "load_salary":
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
        await state.set_state(SalaryState.salary)
        await message.reply(
            f"✅ Водитель найден: {copy_link_fio(u.name)}\n"
            f"📞 Телефон: {html.escape(u.phone or '')}\n\n"
            "📝 Введите данные расчета (37 значений через пробел):\n"
            "дата г/мг/рд/пр оклад сутки загр2р шаттл загр/выгр дт возврат доп_шаттл доп_точка азс "
            "паллет_гипер паллет_метро паллет_ашан 3т 3.5т 5т 10т 12т 12.5т пробег комп_связи стаж 10% премия удержать возмещение др "
            "без_сут_др_прем_стажа в_день итого адрес_загр адрес_выгр транспорт прицеп №рейса\n\n"
            "Пример: 15.01.2026 г 50000 0 0 1000 20 0 0 0 0 0 0 0 0 0 0 0 0 0 0 150 0 5 0 0 0 0 0 0 0 51000.00 адрес_загр адрес_выгр А123BC прицеп 001",
            parse_mode="HTML",
        )
        return
    builder = InlineKeyboardBuilder()
    for u in users[:10]:
        if u.tg_id and str(u.tg_id) != "0":
            builder.row(types.InlineKeyboardButton(text=u.name, callback_data=f"salary_driver_select_{u.tg_id}"))
    await state.update_data(salary_driver_action="load_salary")
    await message.reply("Выберите водителя:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("salary_driver_select_"))
async def salary_driver_select_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    user_repository: UserRepository,
):
    """Выбор водителя по tg_id после поиска по ФИО (загрузка/поиск/выгрузка расчёта)."""
    try:
        tg_id = int(callback.data.replace("salary_driver_select_", ""))
    except ValueError:
        await callback.answer("Ошибка.")
        return
    user = user_repository.get_by_tg_id(tg_id)
    if not user:
        await callback.answer("Водитель не найден.")
        return
    data = await state.get_data()
    action = data.get("salary_driver_action") or data.get("action")
    await state.update_data(driver_tg_id=user.tg_id, driver_name=user.name)
    await callback.message.edit_text(
        f"✅ Водитель: {copy_link_fio(user.name)}\n📞 Телефон: {html.escape(user.phone or '')}",
        parse_mode="HTML",
    )
    if action == "load_salary":
        await state.set_state(SalaryState.salary)
        await callback.message.answer(
            "📝 Введите данные расчета (37 значений через пробел):\n"
            "дата г/мг/рд/пр оклад сутки загр2р шаттл загр/выгр дт возврат доп_шаттл доп_точка азс "
            "паллет_гипер паллет_метро паллет_ашан 3т 3.5т 5т 10т 12т 12.5т пробег комп_связи стаж 10% премия удержать возмещение др "
            "без_сут_др_прем_стажа в_день итого адрес_загр адрес_выгр транспорт прицеп №рейса",
            parse_mode="HTML",
        )
    elif action == "find_salary":
        await state.set_state(AdminSalaryDateState.date)
        await callback.message.answer("📅 Введите дату расчета (дд.мм.гггг):", reply_markup=get_admin_main_keyboard())
    elif action == "admin_export":
        await state.set_state(AdminExportPeriodState.period_type)
        await callback.message.answer(
            "📊 Выберите период для выгрузки расчетов:",
            reply_markup=get_admin_period_selection_keyboard(),
        )
    await callback.answer()


@router.message(SalaryState.salary)
async def admin_load_salary_process(
    message: types.Message,
    state: FSMContext,
    salary_repository: SalaryRepository,
    user_repository: UserRepository
):
    data = await state.get_data()
    
    if data.get("action") != "load_salary":
        return
    
    salary_data = message.text.strip()
    
    try:
        # Парсим данные - ожидается 37 параметров (ФИО водителя получено ранее, status_driver и comment_driver заполняются при подтверждении/комментарии)
        parts = salary_data.split()
        if len(parts) != 37:
            raise ValueError(f"Неверное количество параметров. Ожидается 37, получено {len(parts)}")
        
        # Парсим все поля (числа можно вводить с запятой или точкой)
        date_salary = parts[0].strip()
        type_route = parts[1].strip()
        sum_status = _parse_float(parts[2])
        sum_daily = _parse_float(parts[3])
        load_2_trips = _parse_float(parts[4])
        calc_shuttle = _parse_float(parts[5])
        sum_load_unload = _parse_float(parts[6])
        sum_curtain = _parse_float(parts[7])
        sum_return = _parse_float(parts[8])
        sum_add_shuttle = _parse_float(parts[9])
        sum_add_point = _parse_float(parts[10])
        sum_gas_station = _parse_float(parts[11])
        pallets_hyper = _parse_int(parts[12])
        pallets_metro = _parse_int(parts[13])
        pallets_ashan = _parse_int(parts[14])
        rate_3km = _parse_float(parts[15])
        rate_3_5km = _parse_float(parts[16])
        rate_5km = _parse_float(parts[17])
        rate_10km = _parse_float(parts[18])
        rate_12km = _parse_float(parts[19])
        rate_12_5km = _parse_float(parts[20])
        mileage = _parse_int(parts[21])
        sum_cell_compensation = _parse_float(parts[22])
        experience = _parse_int(parts[23])
        percent_10 = _parse_float(parts[24])
        sum_bonus = _parse_float(parts[25])
        withhold = _parse_float(parts[26])
        compensation = _parse_float(parts[27])
        dr = _parse_float(parts[28])
        sum_without_daily_dr_bonus_exp = _parse_float(parts[29])
        sum_without_daily_dr_bonus = _parse_float(parts[30])
        total = _parse_float(parts[31])
        load_address = parts[32].strip()
        unload_address = parts[33].strip()
        transport = parts[34].strip()
        trailer_number = parts[35].strip()
        route_number = parts[36].strip()
        
        driver_tg_id = data.get("driver_tg_id")
        driver_name = data.get("driver_name")
        
        # Создаем расчет и получаем его ID
        salary_id = salary_repository.create_salary(
            id_driver=driver_tg_id,
            date_salary=date_salary,
            type_route=type_route,
            sum_status=sum_status,
            sum_daily=sum_daily,
            load_2_trips=load_2_trips,
            calc_shuttle=calc_shuttle,
            sum_load_unload=sum_load_unload,
            sum_curtain=sum_curtain,
            sum_return=sum_return,
            sum_add_shuttle=sum_add_shuttle,
            sum_add_point=sum_add_point,
            sum_gas_station=sum_gas_station,
            pallets_hyper=pallets_hyper,
            pallets_metro=pallets_metro,
            pallets_ashan=pallets_ashan,
            rate_3km=rate_3km,
            rate_3_5km=rate_3_5km,
            rate_5km=rate_5km,
            rate_10km=rate_10km,
            rate_12km=rate_12km,
            rate_12_5km=rate_12_5km,
            mileage=mileage,
            sum_cell_compensation=sum_cell_compensation,
            experience=experience,
            percent_10=percent_10,
            sum_bonus=sum_bonus,
            withhold=withhold,
            compensation=compensation,
            dr=dr,
            sum_without_daily_dr_bonus_exp=sum_without_daily_dr_bonus_exp,
            sum_without_daily_dr_bonus=sum_without_daily_dr_bonus,
            total=total,
            load_address=load_address,
            unload_address=unload_address,
            transport=transport,
            trailer_number=trailer_number,
            route_number=route_number
        )
        
        if salary_id:
            # Получаем созданный расчет для отображения
            salary = salary_repository.get_by_id_int(salary_id)
            
            if salary:
                # Отправляем уведомление водителю
                from services.notification_service import MessageSalary
                message_salary = MessageSalary(salary_repository, user_repository)
                await message_salary.notify_driver_about_salary(driver_tg_id, date_salary)
                
                text = "✅ Расчет успешно загружен!\n\n"
                text += f"📊 ID расчета: {salary_id}\n"
                text += f"👤 Водитель: {copy_link_fio(driver_name)}\n"
                text += f"📅 Дата: {html.escape(date_salary)}\n"
                text += f"💰 Итого: {total:.2f}\n"
                text += f"🚚 Транспорт: {html.escape(transport)}\n"
                text += f"🛞 Пробег: {mileage} км\n\n"
                text += "📤 Уведомление отправлено водителю.\n\n"
                text += format_salary_message(driver_name, salary)
                await message.reply(text, reply_markup=get_admin_salary_keyboard(), parse_mode="HTML")
            else:
                await message.reply(
                    f"✅ Расчет для водителя {driver_name} за {date_salary} успешно загружен.",
                    reply_markup=get_admin_salary_keyboard()
                )
        else:
            await message.reply(
                f"❌ Не удалось загрузить расчет для водителя {driver_name}.",
                reply_markup=get_admin_salary_keyboard()
            )
            
    except ValueError as e:
        await message.reply(
            f"❌ Ошибка в формате данных: {str(e)}\n\n"
            "Пожалуйста, проверьте формат и попробуйте снова.\n\n"
            "Пример правильного формата (37 параметров через пробел):\n"
            "15.01.2026 г 50000 0 0 1000 20 0 0 0 0 0 0 0 0 0 0 0 0 0 0 150 0 5 0 0 0 0 0 0 0 51000.00 адрес_загр адрес_выгр А123BC прицеп 001",
            reply_markup=get_admin_salary_keyboard()
        )
    except Exception as e:
        await message.reply(
            f"❌ Произошла ошибка: {str(e)}",
            reply_markup=get_admin_salary_keyboard()
        )
    
    await state.clear()
    
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
    
    # Получаем ВСЕ расчеты за указанную дату
    salaries = salary_repository.get_by_id_date(driver_tg_id, date_salary)
    
    if not salaries:
        await message.reply(
            f"📭 Расчетов для водителя {driver_name} за {date_salary} не найдено.",
            reply_markup=get_admin_salary_keyboard()
        )
        await state.clear()
        return
    
    await message.reply(
        f"📊 Найдено расчетов для {copy_link_fio(driver_name)} за {html.escape(date_salary)}: {len(salaries)}",
        reply_markup=get_admin_salary_keyboard(),
        parse_mode="HTML",
    )
    for salary in salaries:
        text = format_salary_message(driver_name, salary)
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
    
    # Получаем все расчеты
    all_salaries = salary_repository.get_all()
    
    # Фильтруем расчеты по водителю
    driver_salaries = [s for s in all_salaries if s.id_driver == driver_tg_id]
    
    if not driver_salaries:
        await message.reply(
            f"📭 У водителя {driver_name} нет расчетов.",
            reply_markup=get_admin_salary_keyboard()
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
            f"📭 За период {period_info} расчетов не найдено для водителя {driver_name}.",
            reply_markup=get_admin_salary_keyboard()
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
async def delete_salary_start(message: types.Message, state: FSMContext):
    await state.set_state(DeleteSalaryState.driver)
    await state.update_data(action="delete")
    await message.reply("👤 Введите ФИО водителя для удаления расчета:", reply_markup=get_admin_salary_keyboard())

@router.message(DeleteSalaryState.driver)
async def delete_salary_driver(
    message: types.Message,
    state: FSMContext,
    user_repository: UserRepository
):
    data = await state.get_data()
    
    if data.get("action") != "delete":
        return
    
    driver_name = message.text.strip()
    await state.update_data(driver=driver_name)
    
    users = user_repository.search_drivers_by_name_part(driver_name, limit=15)
    if not users:
        await state.clear()
        await message.reply("❌ Пользователь не найден или не активирован", reply_markup=get_admin_salary_keyboard())
        return
    if len(users) == 1:
        user = users[0]
        if not user.tg_id or str(user.tg_id) == "0":
            await state.clear()
            await message.reply("❌ Пользователь не активирован в боте.", reply_markup=get_admin_salary_keyboard())
            return
        await state.update_data(driver_tg_id=user.tg_id, driver_name=user.name)
        await state.set_state(DeleteSalaryState.date)
        await message.reply(
            f"✅ Водитель найден: {copy_link_fio(user.name)}\n"
            f"📞 Телефон: {html.escape(user.phone or '')}\n\n"
            "📅 Введите дату расчета для удаления (дд.мм.гггг):",
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML",
        )
        return
    builder = InlineKeyboardBuilder()
    for u in users[:10]:
        if u.tg_id and str(u.tg_id) != "0":
            builder.row(
                types.InlineKeyboardButton(text=u.name, callback_data=f"delete_salary_driver_{u.tg_id}"),
            )
    await state.update_data(action="delete")
    await message.reply("Выберите водителя:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("delete_salary_driver_"))
async def delete_salary_driver_selected(
    callback: types.CallbackQuery,
    state: FSMContext,
    user_repository: UserRepository,
):
    """Выбор водителя при удалении расчёта (несколько совпадений по ФИО)."""
    data = await state.get_data()
    if data.get("action") != "delete":
        await callback.answer("Сессия истекла.")
        return
    try:
        tg_id = int(callback.data.replace("delete_salary_driver_", ""))
    except ValueError:
        await callback.answer("Ошибка.")
        return
    user = user_repository.get_by_tg_id(tg_id)
    if not user:
        await callback.answer("Водитель не найден.")
        return
    await state.update_data(driver_tg_id=tg_id, driver_name=user.name)
    await state.set_state(DeleteSalaryState.date)
    await callback.message.edit_text(
        f"✅ Водитель: {copy_link_fio(user.name)}\n\n📅 Введите дату расчета для удаления (дд.мм.гггг):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(DeleteSalaryState.date)
async def delete_salary_date(
    message: types.Message,
    state: FSMContext,
    user_repository: UserRepository,
    salary_repository: SalaryRepository
):
    data = await state.get_data()
    
    if data.get("action") != "delete":
        return
    
    date_input = message.text.strip()
    await state.update_data(date=date_input)
    
    driver_tg_id = data.get("driver_tg_id")
    driver_name = data.get("driver_name")

    if not driver_tg_id:
        await message.reply("❌ Ошибка: данные водителя не найдены", reply_markup=get_admin_salary_keyboard())
        await state.clear()
        return

    # Получаем ВСЕ расчеты за указанную дату
    salaries = salary_repository.get_by_id_date(driver_tg_id, date_input)

    if not salaries:
        await message.reply(f"📭 Расчетов для {driver_name} за {date_input} не найдено", reply_markup=get_admin_salary_keyboard())
        await state.clear()
        return
    
    if len(salaries) == 1:
        # Если только один расчет, показываем его сразу
        salary = salaries[0]
        text = format_salary_message(driver_name, salary)
        text = f"Найден расчет для удаления:\n\n{text}\n\n❓ Подтвердите удаление:"
        
        await state.update_data(salary_id=salary.id)
        await state.set_state(DeleteSalaryState.confirmation)
        await message.reply(text, reply_markup=get_delete_confirmation_keyboard(salary.id), parse_mode="HTML")
    else:
        text = f"Найдено {len(salaries)} расчетов для {copy_link_fio(driver_name)} за {html.escape(date_input)}:\n\n"
        
        for i, salary in enumerate(salaries, 1):
            status_icon = "✅" if salary.status_driver == "confirmed" else "⏳"
            text += f"{i}. {status_icon} ID: {salary.id} - ЗП: {salary.total:.2f}"
            if salary.comment_driver and salary.comment_driver != " ":
                text += " 💬"
            text += "\n"
        
        text += "\n📝 Введите ID расчета для удаления:"
        await state.set_state(DeleteSalaryState.salary_id)
        await message.reply(text, parse_mode="HTML")

@router.message(DeleteSalaryState.salary_id)
async def delete_salary_select_id(
    message: types.Message,
    state: FSMContext,
    user_repository: UserRepository,
    salary_repository: SalaryRepository
):
    try:
        salary_id = int(message.text.strip())
        data = await state.get_data()
        driver_name = data.get("driver_name")
        
        # Получаем расчет по ID
        salary = salary_repository.get_by_id_int(salary_id)
        
        if not salary:
            await message.reply("❌ Расчет с таким ID не найден", reply_markup=get_admin_salary_keyboard())
            await state.clear()
            return
        
        text = format_salary_message(driver_name, salary)
        text = f"Найден расчет для удаления:\n\n{text}\n\n❓ Подтвердите удаление:"
        
        await state.update_data(salary_id=salary_id)
        await state.set_state(DeleteSalaryState.confirmation)
        await message.reply(text, reply_markup=get_delete_confirmation_keyboard(salary_id), parse_mode="HTML")
    except ValueError:
        await message.reply("❌ Введите корректный ID расчета (число)", reply_markup=get_admin_salary_keyboard())
        await state.clear()

@router.callback_query(
    F.data.startswith("confirm_delete_") & ~F.data.startswith("confirm_delete_user_")
)
async def confirm_delete_callback(
    callback: types.CallbackQuery,
    state: FSMContext,
    salary_repository: SalaryRepository
):
    """Удаление расчёта по ID (callback: confirm_delete_<salary_id>). Не путать с confirm_delete_user_ в users.py."""
    try:
        salary_id = int(callback.data.replace("confirm_delete_", ""))
        data = await state.get_data()
        driver_name = data.get("driver_name")
        
        success = salary_repository.delete_by_id(salary_id)
        
        if success:
            await callback.message.edit_text(
                f"✅ Расчет ID: {salary_id} для водителя {driver_name} успешно удален."
            )
        else:
            await callback.message.edit_text(
                f"❌ Не удалось удалить расчет ID: {salary_id} для водителя {driver_name}."
            )
    except (ValueError, IndexError):
        await callback.message.edit_text("❌ Ошибка при удалении расчета")
    
    await state.clear()
    
    # ВОЗВРАЩАЕМСЯ В МЕНЮ ЗАРПЛАТЫ, А НЕ В ГЛАВНОЕ МЕНЮ
    from keyboards.admin_kb import get_admin_salary_keyboard
    await callback.message.answer("Меню зарплаты:", reply_markup=get_admin_salary_keyboard())
    
    await callback.answer()

@router.callback_query(F.data == "cancel_delete")
async def cancel_delete_callback(
    callback: types.CallbackQuery,
    state: FSMContext
):
    await callback.message.edit_text("❌ Удаление отменено")
    await state.clear()
    
    # ВОЗВРАЩАЕМСЯ В МЕНЮ ЗАРПЛАТЫ
    from keyboards.admin_kb import get_admin_salary_keyboard
    await callback.message.answer("Меню зарплаты:", reply_markup=get_admin_salary_keyboard())
    
    await callback.answer()