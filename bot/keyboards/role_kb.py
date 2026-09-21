# keyboards/role_kb.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from config.settings import UserRole

def get_main_keyboard_by_role(role: UserRole) -> ReplyKeyboardMarkup:
    """Возвращает основную клавиатуру в зависимости от роли"""
    builder = ReplyKeyboardBuilder()
    
    if role == UserRole.ADMIN:
        builder.row(
            KeyboardButton(text="🚚 Рейсы"),
            KeyboardButton(text="🛠 Заявки на ремонт")
        )
        builder.row(
            KeyboardButton(text="💸 Зарплата"),
            KeyboardButton(text="🤵🏼‍♂️ Пользователи")
        )
        builder.row(KeyboardButton(text="📨 Сообщение"))
    
    elif role == UserRole.DRIVER:
        builder.row(KeyboardButton(text="💵 Зарплата"))
        builder.row(KeyboardButton(text="🛠 Ремонт"))
        builder.row(KeyboardButton(text="🚚 Рейс"))  # Теперь здесь будет меню рейсов
        # Убираем "📋 Прошедшие рейсы" из главного меню
    
    elif role == UserRole.LOGISTIC:
        builder.row(KeyboardButton(text="🚚 Рейсы"))
    
    elif role == UserRole.ACCOUNTANT:
        builder.row(
            KeyboardButton(text="💸 Зарплата"),
            KeyboardButton(text="🚚 Рейсы")
        )
        builder.row(KeyboardButton(text="🛠 Заявки на ремонт"))
    
    elif role == UserRole.MECHANIC:
        builder.row(KeyboardButton(text="🛠 Заявки на ремонт"))
    
    return builder.as_markup(resize_keyboard=True)

