"""Парсинг строки расчёта (37 полей), как в Telegram-боте; CSV; ключ id_driver для PWA."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.models import Salary, User


def parse_float_token(s: str) -> float:
    if not s or not str(s).strip():
        return 0.0
    return float(str(s).strip().replace(",", "."))


def parse_int_token(s: str) -> int:
    return int(round(parse_float_token(s)))


def parse_salary_line_37(line: str) -> dict[str, Any]:
    """37 токенов через пробел — порядок как в handlers/admin/salary.py."""
    parts = line.strip().split()
    if len(parts) != 37:
        raise ValueError(f"Ожидается 37 значений через пробел, получено {len(parts)}")
    return {
        "date_salary": parts[0].strip(),
        "type_route": parts[1].strip(),
        "sum_status": parse_float_token(parts[2]),
        "sum_daily": parse_float_token(parts[3]),
        "load_2_trips": parse_float_token(parts[4]),
        "calc_shuttle": parse_float_token(parts[5]),
        "sum_load_unload": parse_float_token(parts[6]),
        "sum_curtain": parse_float_token(parts[7]),
        "sum_return": parse_float_token(parts[8]),
        "sum_add_shuttle": parse_float_token(parts[9]),
        "sum_add_point": parse_float_token(parts[10]),
        "sum_gas_station": parse_float_token(parts[11]),
        "pallets_hyper": parse_int_token(parts[12]),
        "pallets_metro": parse_int_token(parts[13]),
        "pallets_ashan": parse_int_token(parts[14]),
        "rate_3km": parse_float_token(parts[15]),
        "rate_3_5km": parse_float_token(parts[16]),
        "rate_5km": parse_float_token(parts[17]),
        "rate_10km": parse_float_token(parts[18]),
        "rate_12km": parse_float_token(parts[19]),
        "rate_12_5km": parse_float_token(parts[20]),
        "mileage": float(parse_int_token(parts[21])),
        "sum_cell_compensation": parse_float_token(parts[22]),
        "experience": parse_int_token(parts[23]),
        "percent_10": parse_float_token(parts[24]),
        "sum_bonus": parse_float_token(parts[25]),
        "withhold": parse_float_token(parts[26]),
        "compensation": parse_float_token(parts[27]),
        "dr": parse_float_token(parts[28]),
        "sum_without_daily_dr_bonus_exp": parse_float_token(parts[29]),
        "sum_without_daily_dr_bonus": parse_float_token(parts[30]),
        "total": parse_float_token(parts[31]),
        "load_address": parts[32].strip(),
        "unload_address": parts[33].strip(),
        "transport": parts[34].strip(),
        "trailer_number": parts[35].strip(),
        "route_number": parts[36].strip(),
    }


def driver_salary_key(user: User) -> str:
    """Значение id_driver в БД: legacy Telegram id, иначе строковый users.id (как в боте — строка)."""
    if user.legacy_tg_id and str(user.legacy_tg_id).strip():
        return str(user.legacy_tg_id).strip()
    return str(int(user.id))


def driver_identity_keys(user: User) -> list[str]:
    keys = [driver_salary_key(user)]
    alt = str(int(user.id))
    if alt not in keys:
        keys.append(alt)
    if user.legacy_tg_id and str(user.legacy_tg_id).strip():
        t = str(user.legacy_tg_id).strip()
        if t not in keys:
            keys.append(t)
    return keys


def salary_belongs_to_driver(salary: Salary, user: User) -> bool:
    sid = (salary.id_driver or "").strip()
    return sid in {k.strip() for k in driver_identity_keys(user)}


def parse_dd_mm_yyyy(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%d.%m.%Y")


def salary_date_in_range(salary: Salary, start: datetime, end: datetime) -> bool:
    try:
        d = parse_dd_mm_yyyy(salary.date_salary)
    except ValueError:
        return False
    return start.date() <= d.date() <= end.date()


def _num(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def salary_row_csv_values(salary: Salary) -> list[Any]:
    status_text = ""
    if (salary.status_driver or "").strip() == "confirmed":
        status_text = "Подтверждено"
    elif (salary.status_driver or "").strip() == "commented":
        status_text = "С комментарием"
    else:
        status_text = "Не подтверждено"
    comment = (salary.comment_driver or "").strip()
    if comment in ("", " "):
        comment = ""

    def nz_num(x: Any) -> str:
        f = _num(x)
        return str(f) if f > 0 else ""

    total_s = f"{_num(salary.total):.2f}"
    return [
        salary.id,
        salary.date_salary,
        salary.type_route if salary.type_route and salary.type_route.strip() != "" else "",
        nz_num(salary.sum_status),
        nz_num(salary.sum_daily),
        nz_num(salary.load_2_trips),
        nz_num(salary.calc_shuttle),
        nz_num(salary.sum_load_unload),
        nz_num(salary.sum_curtain),
        nz_num(salary.sum_return),
        nz_num(salary.sum_add_shuttle),
        nz_num(salary.sum_add_point),
        nz_num(salary.sum_gas_station),
        str(salary.pallets_hyper) if salary.pallets_hyper > 0 else "",
        str(salary.pallets_metro) if salary.pallets_metro > 0 else "",
        str(salary.pallets_ashan) if salary.pallets_ashan > 0 else "",
        nz_num(salary.rate_3km),
        nz_num(salary.rate_3_5km),
        nz_num(salary.rate_5km),
        nz_num(salary.rate_10km),
        nz_num(salary.rate_12km),
        nz_num(salary.rate_12_5km),
        nz_num(salary.mileage),
        nz_num(salary.sum_cell_compensation),
        str(salary.experience) if salary.experience > 0 else "",
        nz_num(salary.percent_10),
        nz_num(salary.sum_bonus),
        nz_num(salary.withhold),
        nz_num(salary.compensation),
        nz_num(salary.dr),
        nz_num(salary.sum_without_daily_dr_bonus_exp),
        nz_num(salary.sum_without_daily_dr_bonus),
        total_s,
        (salary.load_address or "").strip(),
        (salary.unload_address or "").strip(),
        (salary.transport or "").strip(),
        (salary.trailer_number or "").strip(),
        (salary.route_number or "").strip(),
        status_text,
        comment,
    ]


def build_salaries_csv_bytes(salaries: list[Salary], driver_name: str, period_info: str) -> bytes:
    """Формат как create_csv_file / create_admin_csv_file в боте (UTF-8 BOM)."""
    salaries_sorted = sorted(salaries, key=lambda x: parse_dd_mm_yyyy(x.date_salary))
    fieldnames = [
        "ID",
        "Дата",
        "г/мг/рд/пр",
        "Окл",
        "Сут",
        "Загр 2р",
        "Шаттл",
        "Загр/выгр",
        "Штора",
        "Возврат",
        "Доп шаттл",
        "Доп точка",
        "АЗС",
        "Паллет гипер",
        "Паллет метро",
        "Паллет ашан",
        "3",
        "3.5",
        "5",
        "10",
        "12",
        "12.5",
        "Пробег",
        "Комп. связи",
        "Стаж",
        "10%",
        "Премия",
        "Удержать",
        "Возмещение",
        "ДР",
        "Без сут/ДР/прем/стажа",
        "В день",
        "ЗП",
        "Адрес загрузки",
        "Адрес выгрузки",
        "Транспорт",
        "Прицеп",
        "№ рейса",
        "Статус",
        "Комментарий",
    ]
    buf = io.StringIO()
    buf.write(f"Период: {period_info}\n")
    buf.write(f"Водитель: {driver_name}\n\n")
    w = csv.writer(buf, delimiter=",")
    w.writerow(fieldnames)
    total_zp = 0.0
    confirmed_count = 0
    unconfirmed_count = 0
    commented_count = 0
    for salary in salaries_sorted:
        row = salary_row_csv_values(salary)
        w.writerow(row)
        try:
            total_zp += _num(salary.total)
        except (ValueError, TypeError):
            pass
        st = (salary.status_driver or "").strip()
        if st == "confirmed":
            confirmed_count += 1
        elif st == "commented":
            commented_count += 1
            unconfirmed_count += 1
        else:
            unconfirmed_count += 1
    buf.write("\n")
    buf.write(f"ИТОГО ЗП: {total_zp:.2f}\n")
    buf.write(f"Всего записей: {len(salaries)}\n")
    buf.write(f"Подтверждено: {confirmed_count}\n")
    buf.write(f"С комментариями: {commented_count}\n")
    buf.write(f"Ожидают подтверждения: {unconfirmed_count}\n")
    raw = buf.getvalue().encode("utf-8-sig")
    return raw


def resolve_user_for_salary_driver_id(db: Session, id_driver: str) -> User | None:
    """Найти пользователя по id_driver из строки salary."""
    text = (id_driver or "").strip()
    if not text:
        return None
    u = db.scalar(select(User).where(User.legacy_tg_id == text, User.is_active.is_(True)))  # noqa: E712
    if u:
        return u
    if text.isdigit():
        return db.get(User, int(text))
    return None

