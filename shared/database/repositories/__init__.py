# database/repositories/__init__.py
from .base import BaseRepository
from .user_repository import UserRepository
from .repair_repository import RepairRepository
from .route_repository import RouteRepository
from .salary_repository import SalaryRepository

__all__ = [
    'BaseRepository',
    'UserRepository',
    'RepairRepository',
    'RouteRepository',
    'SalaryRepository'
]