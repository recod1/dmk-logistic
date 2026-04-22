# config/settings.py
import os
from dataclasses import dataclass
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    DRIVER = "driver"
    LOGISTIC = "logistic"
    ACCOUNTANT = "accountant"  # Бухгалтер
    MECHANIC = "mechanic"      # Механик

class RepairStatus(str, Enum):
    NEW = "new"
    PROCESS = "process"
    CONFIRM = "confirm"
    PROC_REPAIR = "proc_repair"
    CONF_REPAIR = "conf_repair"
    SUCCESS = "success"
    CANCELLED = "cancelled"  # Отменена

class UserStatus(str, Enum):
    ACTIVE = "active"
    INVITE = "invite"
    BLOCKED = "blocked"

class RouteStatus(str, Enum):
    NEW = "new" # Создан , но не принят водителям
    PROCESS = "process" # Принят водителем но не завершен
    SUCCESS = "success" # Подтверждено завершение водителем

class PointStatus(str, Enum):
    NEW = "new" # Создана но водитель ещё не выехал на точку
    PROCESS = "process" # Водитель выехал на точку
    REGISTRATION = "registration" # Водитель зарегистрировался
    LOAD = "load" # Поставил на ворота, в процессе загрузки \ разгрузки
    DOCS = "docs" # Забрал документы
    SUCCESS = "success" # Выехал с точки

@dataclass
class Settings:
    TG_TOKEN: str = os.getenv("TG_TOKEN", "")
    DB_PATH: str = os.getenv("DB_PATH", "./db/olymp.db")
    WIALON_TOKEN: str = os.getenv("WIALON_TOKEN", "")
    # Часто совпадает с веб-мониторингом; для JSON Remote API может понадобиться другой хост — см. WIALON_API_BASE_URL.
    WIALON_BASE_URL: str = os.getenv("WIALON_BASE_URL", "http://w1.wialon.justgps.ru")
    # Если пусто — используется WIALON_BASE_URL. Задайте URL хоста API из панели Wialon Hosting (не страница «Мониторинг» в браузере).
    WIALON_API_BASE_URL: str = os.getenv("WIALON_API_BASE_URL", "").strip()
    # Путь к endpoint ajax (почти всегда /wialon/ajax.html).
    WIALON_AJAX_PATH: str = os.getenv("WIALON_AJAX_PATH", "/wialon/ajax.html").strip() or "/wialon/ajax.html"
    
    class Config:
        env_file = ".env"

settings = Settings()
