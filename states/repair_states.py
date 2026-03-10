# states/repair_states.py
from aiogram.fsm.state import State, StatesGroup

class DriverRepairState(StatesGroup):
    number_auto = State()
    malfunction = State()

class AdminRepairState(StatesGroup):
    ticket_id = State()
    date = State()
    place = State()
    comment = State()
    ticket_id_conf = State()

class AutoSearchState(StatesGroup):
    number_auto = State()

class RepairSuccState(StatesGroup):
    ticket_id = State()


class RepairDeleteState(StatesGroup):
    ticket_id = State()


class RepairReassignState(StatesGroup):
    ticket_id = State()
    driver_fio = State()


class RepairCancelState(StatesGroup):
    ticket_id = State()


class RepairEditState(StatesGroup):
    ticket_id = State()
    param = State()
    value = State()


class RepairStatusMenuState(StatesGroup):
    """Состояние просмотра заявок по статусам"""
    viewing = State()