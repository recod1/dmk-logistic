from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def get_driver_main_keyboard() -> ReplyKeyboardMarkup:
    """Основная клавиатура для водителя"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="💵 Зарплата"))
    builder.row(KeyboardButton(text="🛠 Ремонт"))
    builder.row(KeyboardButton(text="🚚 Рейс"))
    return builder.as_markup(resize_keyboard=True)

def get_driver_repairs_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для раздела ремонтов водителя"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🛠 Заявка на ремонт"))
    builder.row(KeyboardButton(text="🙎‍♂️ Мои ремонты"))
    builder.row(KeyboardButton(text="🔙 Назад"))
    return builder.as_markup(resize_keyboard=True)

# keyboards/driver_kb.py - добавьте новую функцию
def get_driver_routes_menu_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для меню рейсов водителя"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🚚 Активный рейс"))
    builder.row(KeyboardButton(text="📋 Все назначенные рейсы"))
    builder.row(KeyboardButton(text="📋 Прошедшие рейсы"))
    builder.row(KeyboardButton(text="🔙 Назад"))
    return builder.as_markup(resize_keyboard=True)
    
def get_driver_salary_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для раздела зарплаты водителя"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📅 Показать расчет за день"))
    builder.row(KeyboardButton(text="🔄 Не подтвержденные расчеты"))
    builder.row(KeyboardButton(text="🗂 Выгрузить расчет за период"))
    builder.row(KeyboardButton(text="🔙 Назад"))
    return builder.as_markup(resize_keyboard=True)

# Новые клавиатуры для выбора периода
def get_driver_period_selection_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора типа периода для водителя"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📅 С начала месяца"))
    builder.row(KeyboardButton(text="🗓️ Выбрать месяц"))
    builder.row(KeyboardButton(text="📝 Произвольный период"))
    builder.row(KeyboardButton(text="🔙 Назад"))
    return builder.as_markup(resize_keyboard=True)

def get_driver_months_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для выбора месяца для водителя"""
    builder = ReplyKeyboardBuilder()
    months = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    
    for i in range(0, len(months), 3):
        row = months[i:i+3]
        builder.row(*[KeyboardButton(text=month) for month in row])
    
    builder.row(KeyboardButton(text="🔙 Назад"))
    return builder.as_markup(resize_keyboard=True)

# Inline клавиатуры для ремонтов
# Добавляем новые функции для работы с конкретными заявками
def get_ticket_confirm_driver_keyboard(ticket_id: int):
    """Клавиатура для подтверждения ремонта водителем (привязана к конкретной заявке)"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="✅ Подтвердить ремонт", 
        callback_data=f"ticket_confirm_{ticket_id}"
    ))
    return builder.as_markup()

def get_ticket_proc_repair_driver_keyboard(ticket_id: int):
    """Клавиатура для отметки выезда на ремонт (привязана к конкретной заявке)"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="🚗 Выехал на ремонт", 
        callback_data=f"ticket_proc_repair_{ticket_id}"
    ))
    return builder.as_markup()

def get_ticket_conf_repair_driver_keyboard(ticket_id: int):
    """Клавиатура для отметки окончания ремонта (привязана к конкретной заявке)"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="🛠 Отремонтирована", 
        callback_data=f"ticket_conf_repair_{ticket_id}"
    ))
    return builder.as_markup()

def get_ticket_success_repair_driver_keyboard(ticket_id: int):
    """Клавиатура для подтверждения окончания ремонта (привязана к конкретной заявке)"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="✅ Подтвердить окончание", 
        callback_data=f"ticket_success_repair_{ticket_id}"
    ))
    return builder.as_markup()


# Inline клавиатуры для рейсов
def get_route_confirm_keyboard():
    """Клавиатура для принятия рейса"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Принять рейс", 
        callback_data="get_route_confirm_keyboard"
    ))
    return builder.as_markup()

def get_start_point_keyboard():
    """Клавиатура для выезда на точку"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Выехал на точку", 
        callback_data="get_start_point_keyboard"
    ))
    return builder.as_markup()

def get_registration_point_keyboard():
    """Клавиатура для регистрации на точке"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Зарегистрировался", 
        callback_data="get_registration_point_keyboard"
    ))
    return builder.as_markup()

def get_proc_loading_keyboard():
    """Клавиатура для постановки на ворота"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Поставил на ворота", 
        callback_data="get_proc_loading_keyboard"
    ))
    return builder.as_markup()

def get_docs_point_keyboard():
    """Клавиатура забрал документы"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Забрал документы", 
        callback_data="get_docs_point_keyboard"
    ))
    return builder.as_markup()

def get_end_point_keyboard():
    """Клавиатура выехал с точки"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Выехал с точки", 
        callback_data="get_end_point_keyboard"
    ))
    return builder.as_markup()

def get_start_new_point_keyboard():
    """Клавиатура к следующей точке"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="К следующей точке", 
        callback_data="get_route_confirm_keyboard"
    ))
    return builder.as_markup()

def get_route_end_keyboard():
    """Клавиатура для окончания рейса"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Подтвердить окончание рейса", 
        callback_data="get_route_end_keyboard"
    ))
    return builder.as_markup()