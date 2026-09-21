from aiogram import Router, types, F
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from keyboards.base import get_start_keyboard
from keyboards.role_kb import get_main_keyboard_by_role  # Импортируем новую клавиатуру
from states.user_states import InviteState
from database.repositories.user_repository import UserRepository
from config.settings import UserStatus, UserRole

router = Router()

@router.message(Command('start'))
async def process_start_command(message: types.Message):
    await message.reply("Бот запущен", reply_markup=get_start_keyboard())

@router.message(F.text == "Начать")
async def process_begin_command(
    message: types.Message, 
    state: FSMContext,
    user_repository: UserRepository
):
    user = user_repository.get_by_tg_id(message.from_user.id)
    
    if user:
        if user.status == UserStatus.BLOCKED:
            await message.reply("Ваша учетная запись заблокирована")
            return
        
        # Получаем клавиатуру в зависимости от роли
        keyboard = get_main_keyboard_by_role(user.role)
        welcome_text = {
            UserRole.ADMIN: "Добро пожаловать, Администратор 👑",
            UserRole.DRIVER: "Добро пожаловать, Водитель 🚚",
            UserRole.LOGISTIC: "Добро пожаловать, Логист 📋",
            UserRole.ACCOUNTANT: "Добро пожаловать, Бухгалтер 💰",
            UserRole.MECHANIC: "Добро пожаловать, Механик 🔧"
        }.get(user.role, "Добро пожаловать")
        
        await message.reply(welcome_text, reply_markup=keyboard)
    else:
        await state.set_state(InviteState.name)
        await message.reply("Введите ваше ФИО:")

@router.message(InviteState.name)
async def invite_name(
    message: types.Message, 
    state: FSMContext,
    user_repository: UserRepository
):
    await state.update_data(name=message.text)
    data = await state.get_data()
    await state.clear()
    
    user = user_repository.get_by_name(data["name"])
    
    if user:
        # Проверяем, не заблокирован ли пользователь
        if user.status == UserStatus.BLOCKED:
            await message.answer("❌ Ваша учетная запись заблокирована. Обратитесь к администратору.")
            return
        
        success = user_repository.activate_user(message.from_user.id, data['name'])
        
        if success:
            updated_user = user_repository.get_by_tg_id(message.from_user.id)
            
            # Получаем клавиатуру в зависимости от роли
            keyboard = get_main_keyboard_by_role(updated_user.role)
            welcome_text = {
                UserRole.ADMIN: "✅ Учетная запись активирована\nДолжность: Администратор 👑",
                UserRole.DRIVER: "✅ Учетная запись активирована\nДолжность: Водитель 🚚",
                UserRole.LOGISTIC: "✅ Учетная запись активирована\nДолжность: Логист 📋",
                UserRole.ACCOUNTANT: "✅ Учетная запись активирована\nДолжность: Бухгалтер 💰",
                UserRole.MECHANIC: "✅ Учетная запись активирована\nДолжность: Механик 🔧"
            }.get(updated_user.role, "✅ Учетная запись активирована")
            
            await message.answer(welcome_text, reply_markup=keyboard)
        else:
            await message.answer("Ошибка активации учетной записи")
    else:
        await message.answer("Пользователь не найден")