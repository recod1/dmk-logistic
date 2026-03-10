# core/bot.py
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config.settings import settings

def create_bot() -> Bot:
    """Создание экземпляра бота"""
    return Bot(token=settings.TG_TOKEN)

def create_dispatcher() -> Dispatcher:
    """Создание диспетчера с хранилищем состояний"""
    storage = MemoryStorage()
    return Dispatcher(storage=storage)