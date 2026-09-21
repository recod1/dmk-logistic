from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def get_admin_main_keyboard() -> ReplyKeyboardMarkup:
    """Основная клавиатура для администратора"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🚚 Рейсы"),
        KeyboardButton(text="🛠 Заявки на ремонт")
    )
    builder.row(
        KeyboardButton(text="💸 Зарплата"),
        KeyboardButton(text="🤵🏼‍♂️ Пользователи")
    )
    builder.row(KeyboardButton(text="📨 Сообщение"))
    return builder.as_markup(resize_keyboard=True)

def get_admin_salary_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура раздела Зарплата для администратора и бухгалтера"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="💰 Загрузить расчет за день"),
        KeyboardButton(text="📅 Найти расчет за день")
    )
    builder.row(
        KeyboardButton(text="⏳ Не подтвержденные расчеты"),
        KeyboardButton(text="💬 С комментариями")
    )
    builder.row(
        KeyboardButton(text="📊 Выгрузить расчет за период"),
        KeyboardButton(text="🗑️ Удалить расчет")
    )
    builder.row(KeyboardButton(text="↩️ Назад"))
    return builder.as_markup(resize_keyboard=True)

def get_users_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для раздела пользователей"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="👩‍👩‍👦‍👦 Все пользователи"),
        KeyboardButton(text="➕ Добавить пользователя")
    )
    builder.row(
        KeyboardButton(text="✏️ Изменить пользователя"),
        KeyboardButton(text="❌ Заблокировать пользователя")
    )
    builder.row(
        KeyboardButton(text="🚫 Заблокированные"),
        KeyboardButton(text="🗑 Удалить пользователя")
    )
    builder.row(KeyboardButton(text="↩️ Назад"))
    return builder.as_markup(resize_keyboard=True)


def get_edit_user_param_keyboard():
    """Инлайн-клавиатура выбора параметра для редактирования пользователя"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 ФИО", callback_data="edit_user_name"),
        InlineKeyboardButton(text="📞 Телефон", callback_data="edit_user_phone"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статус", callback_data="edit_user_status"),
        InlineKeyboardButton(text="🎯 Роль", callback_data="edit_user_role"),
    )
    return builder.as_markup()


def get_edit_user_role_keyboard():
    """Инлайн-клавиатура выбора новой роли"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Водитель", callback_data="edit_role_driver"),
        InlineKeyboardButton(text="Администратор", callback_data="edit_role_admin"),
    )
    builder.row(
        InlineKeyboardButton(text="Логист", callback_data="edit_role_logistic"),
        InlineKeyboardButton(text="Бухгалтер", callback_data="edit_role_accountant"),
    )
    builder.row(InlineKeyboardButton(text="Механик", callback_data="edit_role_mechanic"))
    return builder.as_markup()


def get_edit_user_status_keyboard():
    """Инлайн-клавиатура выбора нового статуса"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Активен", callback_data="edit_status_active"),
        InlineKeyboardButton(text="⏳ Не подтверждён", callback_data="edit_status_invite"),
    )
    builder.row(InlineKeyboardButton(text="❌ Заблокирован", callback_data="edit_status_blocked"))
    return builder.as_markup()

def get_repairs_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для раздела ремонтов (Администратор, Механик, Бухгалтер)"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🔧 Обработать заявку"),
        KeyboardButton(text="🔍 Найти заявки ТС")
    )
    builder.row(
        KeyboardButton(text="📋 Заявки по статусам"),
        KeyboardButton(text="🗑 Удалить заявку")
    )
    builder.row(
        KeyboardButton(text="🔄 Переназначить заявку"),
        KeyboardButton(text="🚫 Отменить ремонт")
    )
    builder.row(
        KeyboardButton(text="✏️ Изменить детали ремонта")
    )
    builder.row(KeyboardButton(text="↩️ Назад"))
    return builder.as_markup(resize_keyboard=True)


def get_repairs_by_status_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора заявок по статусам"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🆕 Новые"),
        KeyboardButton(text="✉️ Ожидают подтверждения")
    )
    builder.row(
        KeyboardButton(text="📨 Ожидают ремонта"),
        KeyboardButton(text="🛻 Выехали на ремонт")
    )
    builder.row(
        KeyboardButton(text="🛠 Отремонтированы"),
        KeyboardButton(text="✅ Завершены")
    )
    builder.row(
        KeyboardButton(text="❌ Отмененные")
    )
    builder.row(KeyboardButton(text="↩️ Назад"))
    return builder.as_markup(resize_keyboard=True)

def get_routes_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для раздела рейсов (админ, логист, бухгалтер)"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="➕ Создать рейс"),
        KeyboardButton(text="🗑️ Удалить рейс")
    )
    builder.row(
        KeyboardButton(text="🚫 Отменить рейс"),
        KeyboardButton(text="🔍 Поиск по номеру рейса")
    )
    builder.row(
        KeyboardButton(text="🔄 Переназначить рейс"),
        KeyboardButton(text="✏️ Изменить рейс")
    )
    builder.row(
        KeyboardButton(text="🔍 Рейсы по водителю"),
        KeyboardButton(text="🔍 Рейсы по ТС")
    )
    builder.row(
        KeyboardButton(text="📋 Не принятые"),
        KeyboardButton(text="🚚 В процессе")
    )
    builder.row(
        KeyboardButton(text="✅ Завершенные"),
        KeyboardButton(text="❌ Отменённые рейсы")
    )
    builder.row(KeyboardButton(text="↩️ Назад"))
    return builder.as_markup(resize_keyboard=True)

def get_admin_completed_routes_period_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора периода для завершённых рейсов (как в ЗП + за день)."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📅 За день"))
    builder.row(
        KeyboardButton(text="📊 С начала месяца"),
        KeyboardButton(text="📋 Выбрать месяц")
    )
    builder.row(KeyboardButton(text="📑 Произвольный период"))
    builder.row(KeyboardButton(text="↩️ Назад"))
    return builder.as_markup(resize_keyboard=True)


# Новые клавиатуры для выбора периода
def get_admin_period_selection_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора типа периода для администратора"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📊 С начала месяца"),
        KeyboardButton(text="📋 Выбрать месяц")
    )
    builder.row(KeyboardButton(text="📑 Произвольный период"))
    builder.row(KeyboardButton(text="↩️ Назад"))
    return builder.as_markup(resize_keyboard=True)

def get_admin_months_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора месяца для администратора"""
    builder = ReplyKeyboardBuilder()
    months = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    
    for i in range(0, len(months), 3):
        row = months[i:i+3]
        builder.row(*[KeyboardButton(text=month) for month in row])
    
    builder.row(KeyboardButton(text="↩️ Назад"))
    return builder.as_markup(resize_keyboard=True)

# Inline клавиатуры
def get_ticket_repair_keyboard():
    """Клавиатура для обработки заявки"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Обработать", 
        callback_data="ticket_repair"
    ))
    return builder.as_markup()

def get_user_role_keyboard():
    """Клавиатура для выбора роли пользователя"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Водитель", callback_data="change_driver"),
        InlineKeyboardButton(text="Администратор", callback_data="change_admin")
    )
    builder.row(
        InlineKeyboardButton(text="Логист", callback_data="change_logistic"),
        InlineKeyboardButton(text="Бухгалтер", callback_data="change_accountant")
    )
    builder.row(
        InlineKeyboardButton(text="Механик", callback_data="change_mechanic")
    )
    return builder.as_markup()

def get_route_point_keyboard():
    """Клавиатура для работы с точками маршрута"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Добавить точку", callback_data="point_add"),
        InlineKeyboardButton(text="Сохранить рейс", callback_data="save_route")
    )
    return builder.as_markup()

def get_point_type_keyboard():
    """Клавиатура для выбора типа точки"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Загрузка", callback_data="loading"),
        InlineKeyboardButton(text="Разгрузка", callback_data="unloading")
    )
    return builder.as_markup()