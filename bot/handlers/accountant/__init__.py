# handlers/accountant/__init__.py
from .salary import router as salary_router

__all__ = ['salary_router']