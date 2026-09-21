# keyboards/base.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def get_start_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для команды start"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Начать"))
    return builder.as_markup(resize_keyboard=True)