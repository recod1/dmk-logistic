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
    # TG_TOKEN: str = os.getenv("TG_TOKEN", "7789436327:AAE7f-g-8HY-5UYayA8y5Y7lnh6NwzDgaOA")
    DB_PATH: str = os.getenv("DB_PATH", "./db/olymp.db")
    WIALON_TOKEN: str = os.getenv("WIALON_TOKEN", "")
    # WIALON_TOKEN: str = os.getenv("WIALON_TOKEN", "1b78c9f1f54d396c5712d7620b06ad61C3C50B6594F0117363B7EA3F9B64F53A1722A315")
    WIALON_BASE_URL: str = os.getenv("WIALON_BASE_URL", "http://w1.wialon.justgps.ru")
    
    class Config:
        env_file = ".env"

settings = Settings()