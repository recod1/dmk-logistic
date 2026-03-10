# core/middlewares/auth.py
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from database.repositories.user_repository import UserRepository
from config.settings import UserRole, UserStatus

class AuthMiddleware(BaseMiddleware):
    """Middleware для проверки авторизации пользователя"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_repo: UserRepository = data.get("user_repository")
        
        if not user_repo:
            # Репозиторий не инициализирован, пропускаем
            return await handler(event, data)
        
        # Определяем ID пользователя
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        else:
            return await handler(event, data)
        
        # Получаем пользователя из БД (без await)
        user = user_repo.get_by_tg_id(user_id)
        
        if user:
            # Проверяем статус пользователя
            if user.status == UserStatus.BLOCKED:
                if isinstance(event, Message):
                    await event.answer("Ваша учетная запись заблокирована")
                elif isinstance(event, CallbackQuery):
                    await event.message.answer("Ваша учетная запись заблокирована")
                return
            
            # Добавляем пользователя в данные
            data["user"] = user
            
            # Проверяем, есть ли фильтр по роли в хендлере
            filters = data.get("filter")
            if filters:
                # Проверяем, требуется ли определенная роль
                if hasattr(filters, 'F'):
                    # Здесь можно добавить логику проверки ролей
                    pass
        
        return await handler(event, data)