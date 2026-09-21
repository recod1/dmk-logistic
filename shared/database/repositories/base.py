# database/repositories/base.py
from abc import ABC, abstractmethod
from typing import TypeVar, List, Optional

T = TypeVar('T')

class BaseRepository(ABC):
    """Базовый абстрактный класс для всех репозиториев"""
    
    @abstractmethod
    def get_by_id(self, id: int) -> Optional[T]:
        """Получить объект по ID"""
        pass
    
    @abstractmethod
    def get_all(self) -> List[T]:
        """Получить все объекты"""
        pass