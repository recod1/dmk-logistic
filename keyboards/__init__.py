# keyboards/__init__.py
from .base import get_start_keyboard
from .admin_kb import (
    get_admin_main_keyboard,
    get_users_keyboard,
    get_repairs_keyboard,
    get_routes_keyboard,
    get_ticket_repair_keyboard,
    get_user_role_keyboard,
    get_route_point_keyboard,
    get_point_type_keyboard
)
from .driver_kb import (
    get_driver_main_keyboard,
    get_driver_repairs_keyboard,
    get_ticket_confirm_driver_keyboard,
    get_ticket_proc_repair_driver_keyboard,
    get_ticket_conf_repair_driver_keyboard,
    get_ticket_success_repair_driver_keyboard
)

__all__ = [
    'get_start_keyboard',
    'get_admin_main_keyboard',
    'get_users_keyboard',
    'get_repairs_keyboard',
    'get_routes_keyboard',
    'get_driver_main_keyboard',
    'get_driver_repairs_keyboard',
    'get_ticket_confirm_driver_keyboard',
    'get_ticket_proc_repair_driver_keyboard',
    'get_ticket_conf_repair_driver_keyboard',
    'get_ticket_success_repair_driver_keyboard',
    'get_ticket_repair_keyboard',
    'get_user_role_keyboard',
    'get_route_point_keyboard',
    'get_point_type_keyboard',
]