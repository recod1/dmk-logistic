# database/repositories/salary_repository.py
from typing import List, Optional
from database.base import get_db_cursor
from database.models.salary import Salary
from .base import BaseRepository

class SalaryRepository(BaseRepository):

    def get_by_id(self, salary_id: int) -> Optional[Salary]:
        return self.get_by_id_int(salary_id)
    
    def get_all(self) -> List[Salary]:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Salary ORDER BY date_salary DESC')
            return [Salary.from_row(row) for row in cursor.fetchall()]
    
    # Создание расчета с новыми полями
    def create_salary(
        self, 
        id_driver: str,
        date_salary: str,
        type_route: str,
        sum_status: float,
        sum_daily: float,
        load_2_trips: float,
        calc_shuttle: float,
        sum_load_unload: float,
        sum_curtain: float,
        sum_return: float,
        sum_add_shuttle: float,
        sum_add_point: float,
        sum_gas_station: float,
        pallets_hyper: int,
        pallets_metro: int,
        pallets_ashan: int,
        rate_3km: float,
        rate_3_5km: float,
        rate_5km: float,
        rate_10km: float,
        rate_12km: float,
        rate_12_5km: float,
        mileage: float,
        sum_cell_compensation: float,
        experience: int,
        percent_10: float,
        sum_bonus: float,
        withhold: float,
        compensation: float,
        dr: float,
        sum_without_daily_dr_bonus_exp: float,
        sum_without_daily_dr_bonus: float,
        total: float,
        load_address: str,
        unload_address: str,
        transport: str,
        trailer_number: str,
        route_number: str
    ) -> int:
        """Создать новый расчет и вернуть его ID"""
        with get_db_cursor() as cursor:
            cursor.execute(
                '''INSERT INTO Salary 
                (id_driver, date_salary, type_route, sum_status, sum_daily, load_2_trips, 
                 calc_shuttle, sum_load_unload, sum_curtain, sum_return, sum_add_shuttle, 
                 sum_add_point, sum_gas_station, pallets_hyper, pallets_metro, pallets_ashan,
                 rate_3km, rate_3_5km, rate_5km, rate_10km, rate_12km, rate_12_5km,
                 mileage, sum_cell_compensation, experience, percent_10, sum_bonus,
                 withhold, compensation, dr, sum_without_daily_dr_bonus_exp, 
                 sum_without_daily_dr_bonus, total, load_address, unload_address,
                 transport, trailer_number, route_number, status_driver, comment_driver) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (id_driver, date_salary, type_route, sum_status, sum_daily, load_2_trips,
                 calc_shuttle, sum_load_unload, sum_curtain, sum_return, sum_add_shuttle,
                 sum_add_point, sum_gas_station, pallets_hyper, pallets_metro, pallets_ashan,
                 rate_3km, rate_3_5km, rate_5km, rate_10km, rate_12km, rate_12_5km,
                 mileage, sum_cell_compensation, experience, percent_10, sum_bonus,
                 withhold, compensation, dr, sum_without_daily_dr_bonus_exp,
                 sum_without_daily_dr_bonus, total, load_address, unload_address,
                 transport, trailer_number, route_number, " ", " ")
            )
            return cursor.lastrowid
    
    # Поиск по ID расчета
    def get_by_id_int(self, salary_id: int) -> Optional[Salary]:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Salary WHERE id = ?', (salary_id,))
            row = cursor.fetchone()
            return Salary.from_row(row) if row else None
    
    # Поиск по дате и тг_айди
    def get_by_id_date(self, id_driver: str, date_salary: str) -> List[Salary]:
        """Получить все расчеты водителя за конкретную дату"""
        with get_db_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM Salary WHERE id_driver = ? AND date_salary = ? ORDER BY id DESC',
                (id_driver, date_salary)
            )
            rows = cursor.fetchall()
            return [Salary.from_row(row) for row in rows]
    
    # Удаление расчета по ID
    def delete_by_id(self, salary_id: int) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute('DELETE FROM Salary WHERE id = ?', (salary_id,))
            return cursor.rowcount > 0
    
    # Удаление расчета по водителю и дате
    def delete_by_id_date(self, id_driver: str, date_salary: str) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                'DELETE FROM Salary WHERE id_driver = ? AND date_salary = ?',
                (id_driver, date_salary)
            )
            return cursor.rowcount > 0
    
    # Получение расчетов водителя
    def get_by_id_str(self, id_driver: str) -> List[Salary]:
        """Получить все расчеты водителя"""
        with get_db_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM Salary WHERE id_driver = ? ORDER BY date_salary DESC, id DESC',
                (id_driver,)
            )
            rows = cursor.fetchall()
            return [Salary.from_row(row) for row in rows]
    
    # Новый метод: получить неподтвержденные расчеты для конкретного водителя
    def get_unconfirmed_by_driver(self, id_driver: str) -> List[Salary]:
        """Получить все неподтвержденные расчеты для конкретного водителя"""
        with get_db_cursor() as cursor:
            cursor.execute(
                '''SELECT * FROM Salary 
                WHERE id_driver = ? AND (status_driver != 'confirmed' OR status_driver IS NULL OR status_driver = ' ' OR status_driver = '') 
                ORDER BY date_salary DESC, id DESC''',
                (id_driver,)
            )
            rows = cursor.fetchall()
            return [Salary.from_row(row) for row in rows]
    
    # Новый метод: получить все неподтвержденные расчеты для всех водителей
    def get_all_unconfirmed(self) -> List[Salary]:
        """Получить все неподтвержденные расчеты для всех водителей"""
        with get_db_cursor() as cursor:
            cursor.execute(
                '''SELECT * FROM Salary 
                WHERE status_driver != 'confirmed' OR status_driver IS NULL OR status_driver = ' ' OR status_driver = ''
                ORDER BY date_salary DESC, id DESC''',
            )
            rows = cursor.fetchall()
            return [Salary.from_row(row) for row in rows]

    def get_all_unconfirmed_commented(self) -> List[Salary]:
        """Получить все неподтвержденные расчеты с комментариями водителя (status_driver = 'commented')."""
        with get_db_cursor() as cursor:
            cursor.execute(
                '''SELECT * FROM Salary 
                WHERE status_driver = 'commented'
                ORDER BY date_salary DESC, id DESC''',
            )
            rows = cursor.fetchall()
            return [Salary.from_row(row) for row in rows]
    
    # Получить расчеты водителя за период
    def get_salaries_by_period(self, id_driver: str, start_date: str, end_date: str) -> List[Salary]:
        """Получить расчеты водителя за определенный период"""
        with get_db_cursor() as cursor:
            cursor.execute(
                '''SELECT * FROM Salary 
                WHERE id_driver = ? AND date_salary >= ? AND date_salary <= ? 
                ORDER BY date_salary, id''',
                (id_driver, start_date, end_date)
            )
            rows = cursor.fetchall()
            return [Salary.from_row(row) for row in rows]
    
    # Обновление статуса расчета
    def update_status(self, salary_id: int, status: str) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                'UPDATE Salary SET status_driver = ? WHERE id = ?',
                (status, salary_id)
            )
            return cursor.rowcount > 0
    
    # Обновление комментария
    def update_comment(self, salary_id: int, comment: str) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                'UPDATE Salary SET comment_driver = ?, status_driver = ? WHERE id = ?',
                (comment, "commented", salary_id)
            )
            return cursor.rowcount > 0
    
    # Получение последнего расчета водителя за дату
    def get_last_by_driver_date(self, id_driver: str, date_salary: str) -> Optional[Salary]:
        """Получить последний расчет водителя за конкретную дату"""
        with get_db_cursor() as cursor:
            cursor.execute(
                '''SELECT * FROM Salary 
                WHERE id_driver = ? AND date_salary = ? 
                ORDER BY id DESC LIMIT 1''',
                (id_driver, date_salary)
            )
            row = cursor.fetchone()
            return Salary.from_row(row) if row else None