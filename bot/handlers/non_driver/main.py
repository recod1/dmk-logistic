# handlers/non_driver/main.py
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from config.settings import UserRole

router = Router()

# Импортируем хэндлеры из других модулей
from handlers.admin.users import (
    menu_users,
    all_users,
    add_user,
    block_user,
    block_user_tg_id,
    register_name,
    register_phone,
    change_driver,
    change_admin,
    change_logistic,
    change_accountant,
    change_mechanic
)

from handlers.admin.repairs import (
    menu_repairs,
    work_repair_ticket,
    process_ticket_id_from_menu,
    search_repairs_by_auto,
    show_new_repairs,
    show_process_repairs,
    show_confirm_repairs,
    show_proc_repair_repairs,
    show_conf_repair_repairs,
    show_success_repairs,
    process_ticket_repair,
    ticket_repair_date,
    ticket_repair_place,
    ticket_repair_finish,
    ticket_repair_success_admin,
    process_ticket_repair_old,
    ticket_repair_success_old,
    ticket_repair_success_conf,
    search_repairs_by_auto_result
)

from handlers.admin.routes import (
    menu_routes,
    create_route,
    create_route_id,
    create_route_driver,
    add_point,
    add_loading_point,
    add_unloading_point,
    get_point_date,
    get_point_place,
    save_route,
    show_all_routes
)

from handlers.admin.salary import (
    admin_salary_menu,
    admin_load_salary_start,
    admin_load_salary_get_driver,
    admin_load_salary_process,
    admin_find_salary_start,
    admin_find_salary_get_driver,
    admin_find_salary_process,
    show_all_unconfirmed_salaries,
    admin_export_salaries_start,
    admin_export_get_driver,
    admin_handle_period_type,
    admin_handle_month_selection,
    admin_handle_custom_start_date,
    admin_handle_custom_end_date,
    delete_salary_start,
    delete_salary_driver,
    delete_salary_date,
    delete_salary_select_id,
    confirm_delete_callback,
    cancel_delete_callback
)

# Главные хэндлеры меню с проверкой ролей
@router.message(F.text == "🤵🏼‍♂️ Пользователи")
async def handle_users_menu(message: types.Message, user):
    if user.role != UserRole.ADMIN:
        await message.answer("❌ Доступ запрещен. Только администраторы могут управлять пользователями.")
        return
    await menu_users(message)

@router.message(F.text == "🛠 Заявки на ремонт")
async def handle_repairs_menu(message: types.Message, user):
    if user.role not in [UserRole.ADMIN, UserRole.MECHANIC]:
        await message.answer("❌ Доступ запрещен. Ваша роль не позволяет просматривать заявки на ремонт.")
        return
    await menu_repairs(message)

@router.message(F.text == "🚚 Рейсы")
async def handle_routes_menu(message: types.Message, user):
    if user.role not in [UserRole.ADMIN, UserRole.LOGISTIC]:
        await message.answer("❌ Доступ запрещен. Ваша роль не позволяет просматривать рейсы.")
        return
    await menu_routes(message)

@router.message(F.text == "💸 Зарплата")
async def handle_salary_menu(message: types.Message, user):
    if user.role not in [UserRole.ADMIN, UserRole.ACCOUNTANT]:
        await message.answer("❌ Доступ запрещен. Ваша роль не позволяет просматривать зарплату.")
        return
    await admin_salary_menu(message)

# Переопределяем хэндлеры с проверкой ролей для административных функций
@router.message(F.text == "➕ Создать рейс")
async def handle_create_route(message: types.Message, user: dict, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await message.answer("❌ Создание рейсов доступно только администраторам.")
        return
    await create_route(message, state)

@router.message(F.text == "🔧 Обработать заявку")
async def handle_work_repair(message: types.Message, user: dict, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await message.answer("❌ Обработка заявок доступна только администраторам.")
        return
    await work_repair_ticket(message, state)

@router.message(F.text == "💰 Загрузить расчет за день")
async def handle_load_salary(message: types.Message, user: dict, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await message.answer("❌ Загрузка расчетов доступна только администраторам.")
        return
    await admin_load_salary_start(message, state)

@router.message(F.text == "🗑️ Удалить расчет")
async def handle_delete_salary(message: types.Message, user: dict, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await message.answer("❌ Удаление расчетов доступно только администраторам.")
        return
    await delete_salary_start(message, state)

# Регистрируем остальные хэндлеры (они уже имеют свою логику проверки или доступны всем ролям)
router.message.register(show_all_routes, F.text == "🚚 Все рейсы")
router.message.register(show_new_repairs, F.text == "🆕 Новые")
router.message.register(show_process_repairs, F.text == "✉️ Ожидают подтверждения")
router.message.register(show_confirm_repairs, F.text == "📨 Ожидают ремонта")
router.message.register(show_proc_repair_repairs, F.text == "🛻 Выехали на ремонт")
router.message.register(show_conf_repair_repairs, F.text == "🛠 Отремонтированы")
router.message.register(show_success_repairs, F.text == "✅ Завершены")
router.message.register(search_repairs_by_auto, F.text == "🔍 Найти заявки ТС")
router.message.register(admin_find_salary_start, F.text == "📅 Найти расчет за день")
router.message.register(show_all_unconfirmed_salaries, F.text == "⏳ Не подтвержденные расчеты")
router.message.register(admin_export_salaries_start, F.text == "📊 Выгрузить расчет за период")