# app.py
import asyncio
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
for _path in (_HERE, _REPO_ROOT / "shared"):
    if _path.is_dir():
        _s = str(_path)
        if _s not in sys.path:
            sys.path.insert(0, _s)

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config.settings import settings
from handlers.dispatcher import setup_routers
from database.repositories.user_repository import UserRepository
from database.repositories.repair_repository import RepairRepository
from database.repositories.route_repository import RouteRepository
from database.repositories.salary_repository import SalaryRepository

async def main():
    if not settings.TG_TOKEN:
        print("ОШИБКА: TG_TOKEN не найден в .env файле")
        print("Создайте .env файл с содержанием:")
        print("TG_TOKEN=ваш_токен_бота")
        return
    
    print("Запуск бота...")
    
    bot = Bot(token=settings.TG_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрируем репозитории в диспетчере
    dp["user_repository"] = UserRepository()
    dp["repair_repository"] = RepairRepository()
    dp["route_repository"] = RouteRepository()
    dp["salary_repository"] = SalaryRepository()
    
    # Настраиваем роутеры
    setup_routers(dp)
    
    print("Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен")