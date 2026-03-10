# database/models/salary.py
from dataclasses import dataclass, field
from typing import Optional


def _to_float(value) -> float:
    """
    Безопасное преобразование значения из БД в float.
    Поддерживает числа с запятой в качестве десятичного разделителя.
    """
    if value is None or value == "":
        return 0.0
    try:
        return float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


@dataclass
class Salary:
    id: Optional[int] = field(default=None)
    id_driver: str = field(default="")
    date_salary: str = field(default="")
    type_route: str = field(default="")  # г/мг/рд/пр/смг/пд
    
    # Основные суммы
    sum_status: float = field(default=0.0)           # Сумма статус
    sum_daily: float = field(default=0.0)            # Сумма суточных
    load_2_trips: float = field(default=0.0)         # загр 2 рейса
    calc_shuttle: float = field(default=0.0)         # Расчет шаттл
    sum_load_unload: float = field(default=0.0)      # Сумма загрузка выгрузка
    sum_curtain: float = field(default=0.0)          # Сумма штора
    sum_return: float = field(default=0.0)           # Сумма возврат
    sum_add_shuttle: float = field(default=0.0)      # Сумма доп шаттл
    sum_add_point: float = field(default=0.0)        # Сумма доп точка
    sum_gas_station: float = field(default=0.0)      # Сумма АЗС
    
    # Поддоны
    pallets_hyper: int = field(default=0)            # Поддоны гипер ТС
    pallets_metro: int = field(default=0)            # Поддоны Метро
    pallets_ashan: int = field(default=0)            # Поддоны Ашан
    
    # Тарифы за км
    rate_3km: float = field(default=0.0)             # 3 р/км
    rate_3_5km: float = field(default=0.0)           # 3,5 р/км
    rate_5km: float = field(default=0.0)             # 5 р/км
    rate_10km: float = field(default=0.0)            # 10 р/км
    rate_12km: float = field(default=0.0)            # 12 р/км
    rate_12_5km: float = field(default=0.0)          # 12,5 р/км
    
    # Прочее
    mileage: float = field(default=0.0)              # Пробег (int или float)
    sum_cell_compensation: float = field(default=0.0) # Сумма компенсации сотовой связи
    experience: int = field(default=0)               # стаж
    percent_10: float = field(default=0.0)           # 10%
    sum_bonus: float = field(default=0.0)            # Сумма премии
    withhold: float = field(default=0.0)             # Удержать
    compensation: float = field(default=0.0)         # Возмещение
    dr: float = field(default=0.0)                   # ДР
    
    # Итоговые суммы
    sum_without_daily_dr_bonus_exp: float = field(default=0.0)  # Сумма без суточных, ДР, премии, стажа
    sum_without_daily_dr_bonus: float = field(default=0.0)      # Сумма без суточных, ДР, премии
    total: float = field(default=0.0)                # Итого
    
    # Дополнительная информация
    load_address: str = field(default="")            # Адрес загрузки
    unload_address: str = field(default="")          # Адрес выгрузки
    transport: str = field(default="")               # Транспорт
    trailer_number: str = field(default="")          # Номер прицепа
    route_number: str = field(default="")            # № рейса
    
    # Статус и комментарий
    status_driver: str = field(default=" ")
    comment_driver: str = field(default=" ")

    @classmethod
    def from_row(cls, row) -> 'Salary':
        return cls(
            id=row['id'] if 'id' in row.keys() else None,
            id_driver=str(row['id_driver']),
            date_salary=row['date_salary'],
            type_route=row['type_route'],
            sum_status=_to_float(row['sum_status']),
            sum_daily=_to_float(row['sum_daily']),
            load_2_trips=_to_float(row['load_2_trips']),
            calc_shuttle=_to_float(row['calc_shuttle']),
            sum_load_unload=_to_float(row['sum_load_unload']),
            sum_curtain=_to_float(row['sum_curtain']),
            sum_return=_to_float(row['sum_return']),
            sum_add_shuttle=_to_float(row['sum_add_shuttle']),
            sum_add_point=_to_float(row['sum_add_point']),
            sum_gas_station=_to_float(row['sum_gas_station']),
            pallets_hyper=int(row['pallets_hyper']) if row['pallets_hyper'] else 0,
            pallets_metro=int(row['pallets_metro']) if row['pallets_metro'] else 0,
            pallets_ashan=int(row['pallets_ashan']) if row['pallets_ashan'] else 0,
            rate_3km=_to_float(row['rate_3km']),
            rate_3_5km=_to_float(row['rate_3_5km']),
            rate_5km=_to_float(row['rate_5km']),
            rate_10km=_to_float(row['rate_10km']),
            rate_12km=_to_float(row['rate_12km']),
            rate_12_5km=_to_float(row['rate_12_5km']),
            mileage=_to_float(row['mileage']) if row['mileage'] is not None else 0.0,
            sum_cell_compensation=_to_float(row['sum_cell_compensation']),
            experience=int(row['experience']) if row['experience'] else 0,
            percent_10=_to_float(row['percent_10']),
            sum_bonus=_to_float(row['sum_bonus']),
            withhold=_to_float(row['withhold']),
            compensation=_to_float(row['compensation']),
            dr=_to_float(row['dr']),
            sum_without_daily_dr_bonus_exp=_to_float(row['sum_without_daily_dr_bonus_exp']),
            sum_without_daily_dr_bonus=_to_float(row['sum_without_daily_dr_bonus']),
            total=_to_float(row['total']),
            load_address=row['load_address'] if row['load_address'] else "",
            unload_address=row['unload_address'] if row['unload_address'] else "",
            transport=row['transport'] if row['transport'] else "",
            trailer_number=row['trailer_number'] if row['trailer_number'] else "",
            route_number=row['route_number'] if row['route_number'] else "",
            status_driver=row['status_driver'] if row['status_driver'] else " ",
            comment_driver=row['comment_driver'] if row['comment_driver'] else " "
        )