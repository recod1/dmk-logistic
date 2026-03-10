# handlers/mechanic/__init__.py
from .repairs import router as repairs_router

__all__ = ['repairs_router']