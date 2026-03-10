# database/repositories/route_repository.py
import json
from typing import List, Optional, Dict, Any
from database.base import get_db_cursor
from database.models.route import Route, Point
from .base import BaseRepository

# Формат хранения одометра и координат по статусам в поле odometer (JSON, без изменения структуры БД)
# {"process": {"o": "12345", "lat": 55.1, "lng": 37.2}, "registration": {...}, ...}


def _parse_odometer_json(raw: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """Парсит JSON из поля odometer. Возвращает dict статус -> {o, lat, lng}."""
    if not raw or not str(raw).strip():
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def _merge_odometer_status(
    current: Dict[str, Dict[str, Any]],
    status: str,
    odometer: Optional[str],
    lat: Optional[float],
    lng: Optional[float],
) -> str:
    """Добавляет/обновляет данные для статуса и возвращает JSON-строку."""
    entry = dict(current.get(status) or {})
    if odometer is not None:
        entry["o"] = str(odometer).strip()
    if lat is not None:
        entry["lat"] = lat
    if lng is not None:
        entry["lng"] = lng
    if entry:
        current[status] = entry
    return json.dumps(current, ensure_ascii=False)


def get_point_status_data(raw_odometer: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """Возвращает данные по статусам из поля odometer (для отображения)."""
    return _parse_odometer_json(raw_odometer)


# Метки статусов для отображения (используется в admin routes)
STATUS_LABELS_RU = {
    "process": "Выехал",
    "registration": "Регистрация",
    "load": "На ворота",
    "docs": "Документы",
    "success": "Выехал с точки",
}

class RouteRepository(BaseRepository):

    def get_point_status_data(self, raw_odometer: Optional[str]) -> Dict[str, Dict[str, Any]]:
        """Возвращает данные по статусам из поля odometer (для отображения)."""
        return _parse_odometer_json(raw_odometer)

    def get_by_id(self, route_id: int) -> Optional[Route]:
        # В Route id - это TEXT, поэтому используем строковый метод
        return self.get_by_id_str(str(route_id))
    
    def get_all(self) -> List[Route]:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Route')
            return [Route.from_row(row) for row in cursor.fetchall()]

    def route_id_exists(self, target_id):
        """Проверяет, существует ли указанный ID в таблице Route"""
        with get_db_cursor() as cursor:
            cursor.execute(
                'SELECT EXISTS(SELECT 1 FROM Route WHERE id = ? LIMIT 1)',
                (target_id,)
            )
            # EXISTS вернет 1 (True) если запись найдена, 0 (False) если нет
            return cursor.fetchone()[0] == 1
    
    def get_by_id_str(self, route_id: str) -> Optional[Route]:
        """Получить маршрут по строковому ID"""
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Route WHERE id = ?', (route_id,))
            row = cursor.fetchone()
            return Route.from_row(row) if row else None
    
    def get_last_route(self) -> Optional[Route]:
        with get_db_cursor() as cursor:
            # Используем автоинкрементный id или rowid
            cursor.execute('SELECT * FROM Route ORDER BY rowid DESC LIMIT 1')
            row = cursor.fetchone()
            return Route.from_row(row) if row else None
    
    def create(
        self,
        route_id: str,
        tg_id: int,
        number_auto: str = "",
        temperature: str = "",
        dispatcher_contacts: str = "",
        registration_number: str = "",
        trailer_number: str = "",
    ) -> Optional[Route]:
        """Создать новый маршрут и вернуть его объект"""
        import sqlite3
        with get_db_cursor() as cursor:
            try:
                cursor.execute(
                    'INSERT INTO Route (id, tg_id, points, status, number_auto, temperature, dispatcher_contacts, registration_number, trailer_number) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (route_id, tg_id, "0", "new", number_auto, temperature, dispatcher_contacts, registration_number or "", trailer_number or ""),
                )
            except sqlite3.OperationalError:
                cursor.execute(
                    'INSERT INTO Route (id, tg_id, points, status, number_auto, temperature, dispatcher_contacts) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (route_id, tg_id, "0", "new", number_auto, temperature, dispatcher_contacts),
                )
            cursor.execute('SELECT * FROM Route WHERE id = ?', (route_id,))
            row = cursor.fetchone()
            return Route.from_row(row) if row else None
    
    def add_point_to_route(self, route_id: str, point_ids: str) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                'UPDATE Route SET points = ? WHERE id = ?',
                (point_ids, route_id)
            )
            return cursor.rowcount > 0

    def update_status_route(self, route_id: str, status: str) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                'UPDATE Route SET status = ? WHERE id = ?',
                (status, route_id)
            )
            return cursor.rowcount > 0

    def reassign_driver(self, route_id: str, new_tg_id: int) -> bool:
        """Переназначить рейс на другого водителя."""
        with get_db_cursor() as cursor:
            cursor.execute('UPDATE Route SET tg_id = ? WHERE id = ?', (new_tg_id, route_id))
            return cursor.rowcount > 0

    def update_route_field(self, route_id: str, field: str, value: str) -> bool:
        """Обновить одно поле рейса (number_auto, trailer_number, temperature, dispatcher_contacts, registration_number)."""
        allowed = {"number_auto", "trailer_number", "temperature", "dispatcher_contacts", "registration_number"}
        if field not in allowed:
            return False
        with get_db_cursor() as cursor:
            cursor.execute('PRAGMA table_info(Route)')
            columns = [row[1] for row in cursor.fetchall()]
            if field not in columns:
                return False
            cursor.execute(f'UPDATE Route SET {field} = ? WHERE id = ?', (value, route_id))
            return cursor.rowcount > 0

    def delete_points_by_route(self, route_id: str) -> bool:
        """Удалить все точки рейса (без удаления самого рейса)."""
        with get_db_cursor() as cursor:
            cursor.execute('DELETE FROM Point WHERE id_route = ?', (route_id,))
            return True

    def delete_route_with_points(self, route_id: str) -> bool:
        """
        Удалить рейс и все связанные с ним точки.
        Возвращает True, если рейс был удален.
        """
        with get_db_cursor() as cursor:
            # Сначала удаляем точки
            cursor.execute('DELETE FROM Point WHERE id_route = ?', (route_id,))
            # Затем сам рейс
            cursor.execute('DELETE FROM Route WHERE id = ?', (route_id,))
            return cursor.rowcount > 0

    def get_route_by_tgid(self, tg_id, status):
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM Route WHERE tg_id = ? AND status= ? ", (tg_id, status))
            row = cursor.fetchone()
            return Route.from_row(row) if row else None
    
    # Методы для работы с точками
    def create_point(self, point_id: int, route_id: str, type_point: str, 
                     date_point: str, place_point: str) -> Optional[Point]:
        """Создать точку и вернуть её объект"""
        with get_db_cursor() as cursor:
            cursor.execute(
                '''INSERT INTO Point 
                (id, id_route, type_point, place_point, date_point, time_accepted, 
                 time_departure, time_registration, time_put_on_gate, time_docs, photo_docs, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (point_id, route_id, type_point, place_point, date_point, 
                 "0", "0", "0", "0", "0", "0", "new")
            )
            # Получаем созданную точку
            cursor.execute('SELECT * FROM Point WHERE id = ?', (point_id,))
            row = cursor.fetchone()
            if row:
                return Point.from_row(row)
            else:
                # Если не нашли по id, пробуем найти последнюю созданную точку
                cursor.execute('SELECT * FROM Point ORDER BY id DESC LIMIT 1')
                row = cursor.fetchone()
                return Point.from_row(row) if row else None
    
    def get_point_by_id(self, point_id: int) -> Optional[Point]:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Point WHERE id = ?', (point_id,))
            row = cursor.fetchone()
            return Point.from_row(row) if row else None
    
    def get_all_points(self) -> List[Point]:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Point')
            return [Point.from_row(row) for row in cursor.fetchall()]
    
    def count_points(self) -> int:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM Point')
            return cursor.fetchone()[0]
    
    def get_last_point_id(self) -> int:
        """Получить ID последней созданной точки"""
        with get_db_cursor() as cursor:
            cursor.execute('SELECT MAX(id) FROM Point')
            result = cursor.fetchone()
            return result[0] if result[0] else 0

    def update_point_field(self, point_id: int, field: str, value: str) -> bool:
        """Обновить одно поле точки (type_point, place_point, date_point, time_accepted, time_registration, time_put_on_gate, time_docs, time_departure, status)."""
        allowed = {
            "type_point", "place_point", "date_point",
            "time_accepted", "time_registration", "time_put_on_gate", "time_docs", "time_departure",
            "status",
        }
        if field not in allowed:
            return False
        with get_db_cursor() as cursor:
            cursor.execute('PRAGMA table_info(Point)')
            columns = [row[1] for row in cursor.fetchall()]
            if field not in columns:
                return False
            cursor.execute(f'UPDATE Point SET {field} = ? WHERE id = ?', (value, point_id))
            return cursor.rowcount > 0

    def update_point_status(
        self,
        point_id: int,
        point_status: str,
        point_time: Optional[str] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        odometer: Optional[str] = None,
        expected_prev_status: Optional[str] = None,
    ) -> bool:
        """Обновить статус точки, время и опционально координаты/одометр.
        Одометр и координаты сохраняются по каждому статусу в JSON (поле odometer).
        lat/lng обновляются последними значениями для совместимости."""
        prev_status_map = {
            "process": "new",
            "registration": "process",
            "load": "registration",
            "docs": "load",
            "success": "docs",
        }
        exp = expected_prev_status or prev_status_map.get(point_status)
        with get_db_cursor() as cursor:
            cursor.execute('PRAGMA table_info(Point)')
            columns = [row[1] for row in cursor.fetchall()]
            time_column = {
                "process": "time_accepted",
                "registration": "time_registration",
                "load": "time_put_on_gate",
                "docs": "time_docs",
                "success": "time_departure",
            }.get(point_status)
            updates = ["status = ?"]
            params = [point_status]
            if point_time and time_column and time_column in columns:
                updates.append(f"{time_column} = ?")
                params.append(point_time)
            if lat is not None and "lat" in columns:
                updates.append("lat = ?")
                params.append(lat)
            if lng is not None and "lng" in columns:
                updates.append("lng = ?")
                params.append(lng)
            if "odometer" in columns and (odometer is not None or lat is not None or lng is not None):
                cursor.execute('SELECT odometer FROM Point WHERE id = ?', (point_id,))
                row = cursor.fetchone()
                current_raw = row[0] if row and row[0] else None
                current = _parse_odometer_json(current_raw)
                merged = _merge_odometer_status(current, point_status, odometer, lat, lng)
                updates.append("odometer = ?")
                params.append(merged)
            params.append(point_id)
            if exp:
                cursor.execute(
                    f'UPDATE Point SET {", ".join(updates)} WHERE id = ? AND status = ?',
                    params + [exp],
                )
            else:
                cursor.execute(f'UPDATE Point SET {", ".join(updates)} WHERE id = ?', params)
            return cursor.rowcount > 0

    def revert_point_status(self, point_id: int, from_status: str, to_status: str) -> bool:
        """Откатить статус точки на предыдущий и очистить время, соответствующее from_status."""
        time_columns = {
            "process": "time_accepted",
            "registration": "time_registration",
            "load": "time_put_on_gate",
            "docs": "time_docs",
            "success": "time_departure",
        }
        time_col = time_columns.get(from_status)
        with get_db_cursor() as cursor:
            cursor.execute('PRAGMA table_info(Point)')
            columns = [row[1] for row in cursor.fetchall()]
            if time_col and time_col in columns:
                cursor.execute(
                    f'UPDATE Point SET status = ?, {time_col} = NULL WHERE id = ?',
                    (to_status, point_id)
                )
            else:
                cursor.execute('UPDATE Point SET status = ? WHERE id = ?', (to_status, point_id))
            return cursor.rowcount > 0

    def get_new_point_by_route(self, id_route: str) -> Optional[Point]:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM Point WHERE id_route = ? AND status = 'new'", (id_route,))
            row = cursor.fetchone()
            return Point.from_row(row) if row else None


    
    # Методы из оригинального кода
    def get_id_last_route(self) -> Optional[str]:
        """Получить ID последнего маршрута"""
        route = self.get_last_route()
        return route.id if route else None
    
    def get_points_route(self, route_id: str) -> Optional[str]:
        """Получить точки маршрута как строку"""
        route = self.get_by_id_str(route_id)
        return route.points if route else None
    
    def get_route_info(self, route_id: str) -> Optional[Route]:
        return self.get_by_id_str(route_id)
    
    def get_point_info(self, point_id: int) -> Optional[Point]:
        return self.get_point_by_id(point_id)

    def get_routes_by_driver(self, tg_id: int, status: str = None) -> List[Route]:
        """Получить все рейсы водителя с опциональной фильтрацией по статусу"""
        with get_db_cursor() as cursor:
            if status:
                cursor.execute('SELECT * FROM Route WHERE tg_id = ? AND status = ?', (tg_id, status))
            else:
                cursor.execute('SELECT * FROM Route WHERE tg_id = ?', (tg_id,))
            return [Route.from_row(row) for row in cursor.fetchall()]
    
    def get_routes_by_status(self, status: str) -> List[Route]:
        """Получить все рейсы по статусу (new/process/success)"""
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Route WHERE status = ?', (status,))
            return [Route.from_row(row) for row in cursor.fetchall()]

    def _parse_date_dmy(self, s: str):
        """Парсит дату дд.мм.гггг или дд.мм.гггг HH:MM в (y, m, d) или None."""
        if not s or not isinstance(s, str):
            return None
        s = s.strip()
        if " " in s:
            s = s.split()[0]
        parts = s.split(".")
        if len(parts) != 3:
            return None
        try:
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            if 1 <= m <= 12 and 1 <= d <= 31 and 2000 <= y <= 2100:
                return (y, m, d)
        except ValueError:
            pass
        return None

    def _get_route_completion_date(self, route: Route) -> Optional[tuple]:
        """Дата завершения рейса = дата последней точки (date_point), проставленная при создании точки. (y, m, d) или None."""
        points_ids = [x for x in (route.points or "").split(",") if x.strip() and x.strip() != "0"]
        if not points_ids:
            return None
        last_point_id = points_ids[-1]
        try:
            point = self.get_point_by_id(int(last_point_id))
        except ValueError:
            return None
        if not point:
            return None
        return self._parse_date_dmy(point.date_point or "")

    def get_routes_success_in_period(self, date_from: str, date_to: str) -> List[Route]:
        """Завершённые рейсы, у которых дата завершения (по последней точке) попадает в указанный период (дд.мм.гггг)."""
        from_parsed = self._parse_date_dmy(date_from)
        to_parsed = self._parse_date_dmy(date_to)
        if not from_parsed or not to_parsed:
            return []
        routes = self.get_routes_by_status("success")
        result = []
        for route in routes:
            comp = self._get_route_completion_date(route)
            if comp and from_parsed <= comp <= to_parsed:
                result.append(route)
        return result

    def get_last_route_by_driver(self, tg_id: int) -> Optional[Route]:
        """Получить последний созданный рейс для конкретного водителя"""
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Route WHERE tg_id = ? ORDER BY rowid DESC LIMIT 1', (tg_id,))
            row = cursor.fetchone()
            return Route.from_row(row) if row else None

    def get_routes_by_number_auto(self, number_auto: str, status: str = None) -> List[Route]:
        """Получить рейсы по номеру ТС с опциональной фильтрацией по статусу"""
        with get_db_cursor() as cursor:
            if status:
                cursor.execute('SELECT * FROM Route WHERE number_auto = ? AND status = ?', (number_auto.strip(), status))
            else:
                cursor.execute('SELECT * FROM Route WHERE number_auto = ?', (number_auto.strip(),))
            return [Route.from_row(row) for row in cursor.fetchall()]

    def update_route_extra(self, route_id: str, registration_number: str = None, trailer_number: str = None) -> bool:
        """Обновить дополнительные поля рейса (номер для регистрации, прицеп)"""
        with get_db_cursor() as cursor:
            cursor.execute('PRAGMA table_info(Route)')
            columns = [row[1] for row in cursor.fetchall()]
            if 'registration_number' not in columns or 'trailer_number' not in columns:
                return False
            updates = []
            params = []
            if registration_number is not None:
                updates.append('registration_number = ?')
                params.append(registration_number)
            if trailer_number is not None:
                updates.append('trailer_number = ?')
                params.append(trailer_number)
            if not updates:
                return True
            params.append(route_id)
            cursor.execute(f'UPDATE Route SET {", ".join(updates)} WHERE id = ?', params)
            return cursor.rowcount > 0