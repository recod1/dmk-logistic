# handlers/common/back_handler.py
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from keyboards.role_kb import get_main_keyboard_by_role
from config.settings import UserRole

router = Router()

@router.message(F.text == "↩️ Назад")
async def handle_back(message: types.Message, user=None, state: FSMContext = None):
    """Обработчик кнопки Назад (↩️) для всех ролей"""
    await _process_back(message, user, state)

@router.message(F.text == "🔙 Назад")
async def handle_back_alternative(message: types.Message, user=None, state: FSMContext = None):
    """Обработчик альтернативной кнопки Назад (🔙) для всех ролей"""
    await _process_back(message, user, state)

async def _process_back(message: types.Message, user=None, state: FSMContext = None):
    """Общая логика обработки кнопки Назад"""
    if state:
        current_state = await state.get_state()
        if current_state:
            await state.clear()
    
    if not user:
        # Если user не передан, получаем из репозитория
        from database.repositories.user_repository import UserRepository
        user_repo = UserRepository()
        user = user_repo.get_by_tg_id(message.from_user.id)
        if not user:
            await message.answer("❌ Вы не авторизованы. Нажмите /start")
            return
    
    # Получаем клавиатуру в зависимости от роли
    keyboard = get_main_keyboard_by_role(user.role)
    
    # Для всех ролей просто возвращаем на главное меню
    role_names = {
        UserRole.ADMIN: "Администратор",
        UserRole.DRIVER: "Водитель",
        UserRole.LOGISTIC: "Логист",
        UserRole.ACCOUNTANT: "Бухгалтер",
        UserRole.MECHANIC: "Механик"
    }
    
    role_name = role_names.get(user.role, "Пользователь")
    await message.reply(f"Возврат в главное меню ({role_name})", reply_markup=keyboard)