# states/route_states.py
from aiogram.fsm.state import State, StatesGroup


class RouteState(StatesGroup):
    """Состояния для создания рейса администратором"""
    route_id = State()
    driver = State()
    number_auto = State()
    temperature = State()
    dispatcher_contacts = State()
    registration_number = State()
    trailer_number = State()
    onec_text = State()


class PointState(StatesGroup):
    """Состояния для добавления точек к рейсу"""
    type_point = State()
    place_point = State()
    date_point = State()


class AdminRouteDeleteState(StatesGroup):
    """Состояния для удаления рейса"""
    route_id = State()


class AdminRouteSearchState(StatesGroup):
    """Состояния для поиска рейсов по водителю"""
    driver = State()


class AdminRouteSearchByAutoState(StatesGroup):
    """Состояния для поиска рейсов по номеру ТС"""
    number_auto = State()


class AdminRouteCancelState(StatesGroup):
    """Состояния для отмены рейса"""
    route_id = State()


class AdminRouteSearchByIdState(StatesGroup):
    """Состояния для поиска рейса по номеру"""
    route_id = State()


class AdminRouteFilterByState(StatesGroup):
    """После выбора статуса рейсов: выбор способа фильтра (Все / По водителю / По номеру рейса / По ТС)"""
    filter_status = State()
    driver_fio = State()
    route_id = State()
    number_auto = State()


class AdminRouteReassignState(StatesGroup):
    """Состояния для переназначения рейса"""
    route_id = State()
    driver_fio = State()
    number_auto = State()
    trailer_number = State()


class AdminRouteEditState(StatesGroup):
    """Состояния для изменения рейса"""
    route_id = State()
    choosing_field = State()
    value = State()


class AdminRouteCompletedPeriodState(StatesGroup):
    """Состояния для выбора периода завершённых рейсов"""
    period_type = State()
    date_day = State()
    month_year = State()
    custom_start = State()
    custom_end = State()


class OnecMissingParamState(StatesGroup):
    """Запрос недостающих параметров после парсинга 1С"""
    value = State()


class DriverPointTimeState(StatesGroup):
    """Выбор времени смены статуса точки: сохранить авто или ввести вручную"""
    manual_time = State()
    odometer_manual = State()  # Ввод одометра вручную (для process и docs)