# handlers/dispatcher.py - УПРОЩЕННАЯ ВЕРСИЯ
from aiogram import Router
from handlers.common.start_handlers import router as start_router
from handlers.common.back_handler import router as back_router
from handlers.driver.repairs import router as driver_repairs_router
from handlers.driver.routes import router as driver_routes_router
from handlers.driver.salary import router as driver_salary_router

# Импортируем все роутеры администратора
from handlers.admin.users import router as admin_users_router
from handlers.admin.messages import router as admin_messages_router
from handlers.admin.repairs import router as admin_repairs_router
from handlers.admin.routes import router as admin_routes_router
from handlers.admin.salary import router as admin_salary_router

from core.middlewares.role_middleware import RoleMiddleware
from config.settings import UserRole

def setup_routers(dp) -> None:
    """Настройка всех роутеров с проверкой ролей"""
    
    # Общие роутеры (доступны всем)
    dp.include_router(start_router)
    
    # Роутеры для водителей
    driver_router = Router()
    driver_router.include_router(driver_repairs_router)
    driver_router.include_router(driver_routes_router)
    driver_router.include_router(driver_salary_router)
    driver_router.message.middleware(RoleMiddleware([UserRole.DRIVER]))
    driver_router.callback_query.middleware(RoleMiddleware([UserRole.DRIVER]))
    dp.include_router(driver_router)
    
    # ЕДИНЫЙ роутер для всех не-водителей (админ, логист, бухгалтер, механик)
    non_driver_router = Router()
    
    # Подключаем ВСЕ административные роутеры
    non_driver_router.include_router(admin_repairs_router)
    non_driver_router.include_router(admin_routes_router)
    non_driver_router.include_router(admin_salary_router)
    
    # Общий обработчик "Назад" для не-водителей
    non_driver_router.include_router(back_router)
    
    # Middleware для всех не-водителей
    non_driver_middleware = RoleMiddleware([
        UserRole.ADMIN, 
        UserRole.LOGISTIC, 
        UserRole.ACCOUNTANT, 
        UserRole.MECHANIC
    ])
    non_driver_router.message.middleware(non_driver_middleware)
    non_driver_router.callback_query.middleware(non_driver_middleware)
    dp.include_router(non_driver_router)
    
    # ОТДЕЛЬНЫЙ роутер для админ-функций (только админ)
    admin_only_router = Router()
    admin_only_router.include_router(admin_users_router)
    admin_only_router.include_router(admin_messages_router)
    admin_only_router.message.middleware(RoleMiddleware([UserRole.ADMIN]))
    admin_only_router.callback_query.middleware(RoleMiddleware([UserRole.ADMIN]))
    dp.include_router(admin_only_router)