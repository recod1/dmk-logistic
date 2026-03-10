# handlers/__init__.py
from .common.start_handlers import router as start_router
from .driver.repairs import router as driver_repairs_router
from .driver.routes import router as driver_routes_router
from .driver.salary import router as driver_salary_router
from .admin.users import router as admin_users_router
from .admin.repairs import router as admin_repairs_router
from .admin.routes import router as admin_routes_router
from .admin.salary import router as admin_salary_router
from .logistic.routes import router as logistic_routes_router
from .accountant.salary import router as accountant_salary_router
from .mechanic.repairs import router as mechanic_repairs_router

__all__ = [
    'start_router',
    'driver_repairs_router',
    'driver_routes_router',
    'driver_salary_router',
    'admin_users_router',
    'admin_repairs_router',
    'admin_routes_router',
    'admin_salary_router',
    'logistic_routes_router',
    'accountant_salary_router',
    'mechanic_repairs_router'
]