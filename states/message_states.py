# states/message_states.py
from aiogram.fsm.state import State, StatesGroup


class AdminMessageState(StatesGroup):
    """Состояния для отправки сообщения администратором"""
    target = State()       # Выбор группы или переход к поиску пользователя
    user_search = State() # Ввод ФИО для поиска (при выборе «Пользователю»)
    text = State()        # Ввод текста сообщения
    confirm = State()     # Подтверждение отправки
