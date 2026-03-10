# core/middlewares/role_middleware.py
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database.repositories.user_repository import UserRepository
from config.settings import UserRole, UserStatus

class RoleMiddleware(BaseMiddleware):
    """Middleware для проверки ролей пользователя и статуса (блокировка неавторизованных и заблокированных)"""
    
    def __init__(self, allowed_roles: list[UserRole]):
        self.allowed_roles = allowed_roles
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_repo: UserRepository = data.get("user_repository")
        
        if not user_repo:
            return await handler(event, data)
        
        # Определяем ID пользователя
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        else:
            return await handler(event, data)
        
        # Получаем пользователя
        user = user_repo.get_by_tg_id(user_id)
        
        # Блокируем неавторизованных пользователей
        if not user:
            error_msg = "❌ Вы не авторизованы. Нажмите /start для авторизации."
            if isinstance(event, Message):
                await event.answer(error_msg)
            elif isinstance(event, CallbackQuery):
                await event.answer(error_msg, show_alert=True)
                if event.message:
                    await event.message.answer(error_msg)
            return
        
        # Блокируем заблокированных пользователей
        if user.status == UserStatus.BLOCKED:
            error_msg = "❌ Ваша учетная запись заблокирована. Обратитесь к администратору."
            if isinstance(event, Message):
                await event.answer(error_msg)
            elif isinstance(event, CallbackQuery):
                await event.answer(error_msg, show_alert=True)
                if event.message:
                    await event.message.answer(error_msg)
            return
        
        # Добавляем пользователя в данные для использования в хэндлерах
        data["user"] = user
        
        # Проверяем, находится ли пользователь в состоянии FSM
        # В FSM состоянии пропускаем проверку роли (для процесса авторизации и других процессов)
        state: FSMContext = data.get("state")
        if state:
            current_state = await state.get_state()
            if current_state:
                return await handler(event, data)
        
        # Проверяем роль только если не в состоянии FSM
        if user.role not in self.allowed_roles:
            role_names = {
                UserRole.ADMIN: "Администратор",
                UserRole.DRIVER: "Водитель",
                UserRole.LOGISTIC: "Логист",
                UserRole.ACCOUNTANT: "Бухгалтер",
                UserRole.MECHANIC: "Механик"
            }
            
            user_role_name = role_names.get(user.role, "Неизвестно")
            error_msg = f"❌ Доступ запрещен\n\nВаша роль: {user_role_name}"
            
            if isinstance(event, Message):
                await event.answer(error_msg)
            elif isinstance(event, CallbackQuery):
                await event.answer(error_msg, show_alert=True)
                if event.message:
                    await event.message.answer(error_msg)
            return
        
        return await handler(event, data)