#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from mobile_api.auth import hash_password
from mobile_api.models import Point, Repair, Route, RouteEvent, RoutePoint, Salary, User


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate legacy SQLite data to Postgres.")
    parser.add_argument("--sqlite-path", required=True, help="Path to sqlite DB file (e.g. ./db/olymp.db)")
    parser.add_argument("--pg-dsn", required=True, help="Postgres SQLAlchemy DSN")
    parser.add_argument(
        "--default-password",
        default="ChangeMe123!",
        help="Default password for imported login users (will be bcrypt-hashed).",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing Postgres data before import.",
    )
    return parser.parse_args()


def _to_decimal(value, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    text = str(value).strip()
    if not text:
        return Decimal(default)
    text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal(default)


def _to_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "0":
        return None
    formats = [
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _login_from_legacy(name: str | None, tg_id: str | None, suffix: int) -> str:
    tg_text = (tg_id or "").strip()
    if tg_text and tg_text != "0":
        return f"tg_{tg_text}"

    base_name = (name or "").strip().lower()
    base_name = re.sub(r"[^a-z0-9]+", "_", base_name).strip("_")
    if not base_name:
        base_name = "user"
    return f"{base_name}_{suffix}"


def _truncate_target(session: Session) -> None:
    session.execute(delete(RouteEvent))
    session.execute(delete(RoutePoint))
    session.execute(delete(Point))
    session.execute(delete(Route))
    session.execute(delete(Salary))
    session.execute(delete(Repair))
    session.execute(delete(User))
    session.commit()


def migrate(sqlite_path: str, pg_dsn: str, default_password: str, truncate: bool) -> None:
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    engine = create_engine(pg_dsn, future=True)
    session = Session(engine)

    try:
        if truncate:
            _truncate_target(session)

        sqlite_cur.execute("SELECT * FROM Users")
        users_rows = sqlite_cur.fetchall()

        login_seq = 1
        tg_to_user_id: dict[str, int] = {}
        existing_logins: set[str] = set(session.scalars(select(User.login)).all())
        password_hash = hash_password(default_password)

        for row in users_rows:
            tg_id = str(row["tg_id"]) if row["tg_id"] is not None else ""
            full_name = row["name"] if "name" in row.keys() else None
            login = _login_from_legacy(full_name, tg_id, login_seq)
            while login in existing_logins:
                login_seq += 1
                login = _login_from_legacy(full_name, tg_id, login_seq)
            login_seq += 1
            existing_logins.add(login)

            user = User(
                login=login,
                password_hash=password_hash,
                role=(row["role"] or "driver") if "role" in row.keys() else "driver",
                full_name=full_name,
                legacy_tg_id=tg_id or None,
                is_active=(row["status"] != "blocked") if "status" in row.keys() else True,
            )
            session.add(user)
            session.flush()
            if tg_id:
                tg_to_user_id[tg_id] = user.id

        sqlite_cur.execute("SELECT * FROM Route")
        route_rows = sqlite_cur.fetchall()
        for row in route_rows:
            tg_id = str(row["tg_id"]) if row["tg_id"] is not None else ""
            route = Route(
                id=str(row["id"]),
                legacy_driver_tg_id=int(row["tg_id"]) if str(row["tg_id"]).isdigit() else None,
                assigned_user_id=tg_to_user_id.get(tg_id),
                status=row["status"] or "new",
                number_auto=(row["number_auto"] or "") if "number_auto" in row.keys() else "",
                temperature=(row["temperature"] or "") if "temperature" in row.keys() else "",
                dispatcher_contacts=(row["dispatcher_contacts"] or "") if "dispatcher_contacts" in row.keys() else "",
                registration_number=(row["registration_number"] or "") if "registration_number" in row.keys() else "",
                trailer_number=(row["trailer_number"] or "") if "trailer_number" in row.keys() else "",
            )
            session.add(route)

        sqlite_cur.execute("SELECT * FROM Point")
        point_rows = sqlite_cur.fetchall()
        for row in point_rows:
            point = Point(
                id=int(row["id"]),
                route_id=str(row["id_route"]),
                type_point=row["type_point"] or "",
                place_point=row["place_point"] or "",
                date_point=row["date_point"] or "",
                time_accepted=_to_datetime(row["time_accepted"]) if "time_accepted" in row.keys() else None,
                time_departure=_to_datetime(row["time_departure"]) if "time_departure" in row.keys() else None,
                time_registration=_to_datetime(row["time_registration"]) if "time_registration" in row.keys() else None,
                time_put_on_gate=_to_datetime(row["time_put_on_gate"]) if "time_put_on_gate" in row.keys() else None,
                time_docs=_to_datetime(row["time_docs"]) if "time_docs" in row.keys() else None,
                photo_docs=(row["photo_docs"] if "photo_docs" in row.keys() and row["photo_docs"] != "0" else None),
                status=row["status"] or "new",
                lat=float(row["lat"]) if "lat" in row.keys() and row["lat"] not in (None, "") else None,
                lng=float(row["lng"]) if "lng" in row.keys() and row["lng"] not in (None, "") else None,
                odometer=(row["odometer"] if "odometer" in row.keys() and row["odometer"] not in ("", "0") else None),
            )
            session.add(point)

        session.flush()

        # Нормализация Route.points (CSV) -> route_points(order_index)
        for row in route_rows:
            route_id = str(row["id"])
            points_csv = (row["points"] or "").strip()
            if not points_csv or points_csv == "0":
                continue
            point_ids = [p.strip() for p in points_csv.split(",") if p.strip() and p.strip() != "0"]
            for idx, point_id in enumerate(point_ids):
                if not point_id.isdigit():
                    continue
                exists = session.scalar(
                    select(func.count()).select_from(Point).where(Point.id == int(point_id), Point.route_id == route_id)
                )
                if not exists:
                    continue
                session.add(
                    RoutePoint(
                        route_id=route_id,
                        point_id=int(point_id),
                        order_index=idx,
                    )
                )

        sqlite_cur.execute("SELECT * FROM Salary")
        salary_rows = sqlite_cur.fetchall()
        for row in salary_rows:
            session.add(
                Salary(
                    id_driver=str(row["id_driver"]) if row["id_driver"] is not None else "",
                    date_salary=row["date_salary"] or "",
                    type_route=row["type_route"] or "",
                    sum_status=_to_decimal(row["sum_status"]),
                    sum_daily=_to_decimal(row["sum_daily"]),
                    load_2_trips=_to_decimal(row["load_2_trips"]),
                    calc_shuttle=_to_decimal(row["calc_shuttle"]),
                    sum_load_unload=_to_decimal(row["sum_load_unload"]),
                    sum_curtain=_to_decimal(row["sum_curtain"]),
                    sum_return=_to_decimal(row["sum_return"]),
                    sum_add_shuttle=_to_decimal(row["sum_add_shuttle"]),
                    sum_add_point=_to_decimal(row["sum_add_point"]),
                    sum_gas_station=_to_decimal(row["sum_gas_station"]),
                    pallets_hyper=int(row["pallets_hyper"] or 0),
                    pallets_metro=int(row["pallets_metro"] or 0),
                    pallets_ashan=int(row["pallets_ashan"] or 0),
                    rate_3km=_to_decimal(row["rate_3km"]),
                    rate_3_5km=_to_decimal(row["rate_3_5km"]),
                    rate_5km=_to_decimal(row["rate_5km"]),
                    rate_10km=_to_decimal(row["rate_10km"]),
                    rate_12km=_to_decimal(row["rate_12km"]),
                    rate_12_5km=_to_decimal(row["rate_12_5km"]),
                    mileage=_to_decimal(row["mileage"]),
                    sum_cell_compensation=_to_decimal(row["sum_cell_compensation"]),
                    experience=int(row["experience"] or 0),
                    percent_10=_to_decimal(row["percent_10"]),
                    sum_bonus=_to_decimal(row["sum_bonus"]),
                    withhold=_to_decimal(row["withhold"]),
                    compensation=_to_decimal(row["compensation"]),
                    dr=_to_decimal(row["dr"]),
                    sum_without_daily_dr_bonus_exp=_to_decimal(row["sum_without_daily_dr_bonus_exp"]),
                    sum_without_daily_dr_bonus=_to_decimal(row["sum_without_daily_dr_bonus"]),
                    total=_to_decimal(row["total"]),
                    load_address=row["load_address"] or "",
                    unload_address=row["unload_address"] or "",
                    transport=row["transport"] or "",
                    trailer_number=row["trailer_number"] or "",
                    route_number=row["route_number"] or "",
                    status_driver=row["status_driver"] or " ",
                    comment_driver=row["comment_driver"] or " ",
                )
            )

        sqlite_cur.execute("SELECT * FROM Repair")
        repair_rows = sqlite_cur.fetchall()
        for row in repair_rows:
            session.add(
                Repair(
                    id_ticket=int(row["id_ticket"]),
                    tg_id=str(row["tg_id"]) if row["tg_id"] is not None else "",
                    number_auto=row["number_auto"] or "",
                    malfunction=row["malfunction"] or "",
                    status=row["status"] or "new",
                    date_repair=row["date_repair"] or "0",
                    place_repair=row["place_repair"] or "0",
                    comment_repair=row["comment_repair"] or "0",
                )
            )

        session.commit()

        print("Migration completed successfully.")
        print(
            {
                "users": session.scalar(select(func.count()).select_from(User)),
                "routes": session.scalar(select(func.count()).select_from(Route)),
                "points": session.scalar(select(func.count()).select_from(Point)),
                "route_points": session.scalar(select(func.count()).select_from(RoutePoint)),
                "salary": session.scalar(select(func.count()).select_from(Salary)),
                "repair": session.scalar(select(func.count()).select_from(Repair)),
            }
        )
    finally:
        session.close()
        sqlite_conn.close()


def main() -> None:
    args = parse_args()
    migrate(
        sqlite_path=args.sqlite_path,
        pg_dsn=args.pg_dsn,
        default_password=args.default_password,
        truncate=args.truncate,
    )


if __name__ == "__main__":
    main()

