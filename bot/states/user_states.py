# states/user_states.py
from aiogram.fsm.state import State, StatesGroup

class InviteState(StatesGroup):
    name = State()

class RegisterState(StatesGroup):
    name = State()
    phone = State()
    role = State()

class BlockedState(StatesGroup):
    tg_id = State()


class EditUserState(StatesGroup):
    """Состояния для изменения пользователя: ID → выбор параметра → новое значение"""
    tg_id = State()
    new_value = State()


class DeleteUserState(StatesGroup):
    """Удаление пользователя: способ (ID/ФИО) → ввод → подтверждение"""
    method = State()
    input_value = State()
    selected_tg_id = State()