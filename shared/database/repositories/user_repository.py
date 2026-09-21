from typing import List, Optional
from database.base import get_db_cursor
from database.models.user import User
from config.settings import UserRole, UserStatus
from .base import BaseRepository

class UserRepository(BaseRepository):
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        return None
    
    def get_all(self) -> List[User]:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Users')
            return [User.from_row(row) for row in cursor.fetchall()]
    
    def get_by_tg_id(self, tg_id: int) -> Optional[User]:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Users WHERE tg_id = ?', (str(tg_id),))
            row = cursor.fetchone()
            return User.from_row(row) if row else None
    
    def get_by_name(self, name: str) -> Optional[User]:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Users WHERE name = ?', (name,))
            row = cursor.fetchone()
            return User.from_row(row) if row else None

    def search_drivers_by_name_part(self, part: str, limit: int = 20) -> List[User]:
        """Поиск активных водителей по части ФИО (регистронезависимый).
        Поиск только по границам слов: в начале ФИО или после пробела.
        Например, «панов» находит «Панов», но не «Степанов».
        Фильтрация в Python: SQLite LOWER() не работает с кириллицей."""
        if not part or len(part.strip()) < 2:
            return []
        part_clean = part.strip().lower()
        raw = self.get_all_by_role_and_status(UserRole.DRIVER, UserStatus.ACTIVE)
        # Фильтр в Python: регистронезависимый поиск по границе слова
        result = []
        for u in raw:
            name_lower = (u.name or "").strip().lower()
            if not name_lower:
                continue
            if name_lower.startswith(part_clean) or f" {part_clean}" in f" {name_lower}":
                result.append(u)
                if len(result) >= limit:
                    break
        return sorted(result, key=lambda x: (x.name or ""))

    def search_users_by_name_part(self, part: str, limit: int = 20) -> List[User]:
        """Поиск активных пользователей любой роли по части ФИО (регистронезависимый, по границе слова)."""
        if not part or len(part.strip()) < 2:
            return []
        part_clean = part.strip().lower()
        raw = []
        for role in UserRole:
            raw.extend(self.get_all_by_role_and_status(role, UserStatus.ACTIVE))
        result = []
        seen_tg = set()
        for u in raw:
            if not u.tg_id or str(u.tg_id) == "0":
                continue
            if u.tg_id in seen_tg:
                continue
            seen_tg.add(u.tg_id)
            name_lower = (u.name or "").strip().lower()
            if not name_lower:
                continue
            if name_lower.startswith(part_clean) or f" {part_clean}" in f" {name_lower}":
                result.append(u)
                if len(result) >= limit:
                    break
        return sorted(result, key=lambda x: (x.name or ""))
    
    def get_all_by_role(self, role: UserRole) -> List[User]:
        with get_db_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM Users WHERE role = ? AND status = ?',
                (role.value, UserStatus.ACTIVE.value)
            )
            return [User.from_row(row) for row in cursor.fetchall()]
    
    def get_all_by_role_and_status(self, role: UserRole, status: UserStatus) -> List[User]:
        with get_db_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM Users WHERE role = ? AND status = ?',
                (role.value, status.value)
            )
            return [User.from_row(row) for row in cursor.fetchall()]
    
    # Получить всех активных администраторов
    def get_all_active_admins(self) -> List[User]:
        return self.get_all_by_role_and_status(UserRole.ADMIN, UserStatus.ACTIVE)
    
    # Получить всех активных водителей
    def get_all_active_drivers(self) -> List[User]:
        return self.get_all_by_role_and_status(UserRole.DRIVER, UserStatus.ACTIVE)
    
    # Получить всех активных логистов
    def get_all_active_logistics(self) -> List[User]:
        return self.get_all_by_role_and_status(UserRole.LOGISTIC, UserStatus.ACTIVE)
    
    # Получить всех активных бухгалтеров
    def get_all_active_accountants(self) -> List[User]:
        return self.get_all_by_role_and_status(UserRole.ACCOUNTANT, UserStatus.ACTIVE)
    
    # Получить всех активных механиков
    def get_all_active_mechanics(self) -> List[User]:
        return self.get_all_by_role_and_status(UserRole.MECHANIC, UserStatus.ACTIVE)
    
    # Получить всех неприглашенных пользователей (любой роли)
    def get_all_invite_users(self) -> List[User]:
        with get_db_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM Users WHERE status = ?',
                (UserStatus.INVITE.value,)
            )
            return [User.from_row(row) for row in cursor.fetchall()]

    # Получить всех заблокированных пользователей
    def get_all_blocked(self) -> List[User]:
        with get_db_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM Users WHERE status = ?',
                (UserStatus.BLOCKED.value,)
            )
            return [User.from_row(row) for row in cursor.fetchall()]

    def delete_user(self, tg_id: int) -> bool:
        """Удалить пользователя по Telegram ID. Рейсы не удаляются, в них ФИО водителя будет «Неизвестно»."""
        with get_db_cursor() as cursor:
            cursor.execute('DELETE FROM Users WHERE tg_id = ?', (str(tg_id),))
            return cursor.rowcount > 0
    
    def delete_user_by_fields(self, tg_id: str, name: str, phone: str = "") -> bool:
        """Удалить пользователя по комбинации tg_id + name + phone. Используется для точного удаления при tg_id=0."""
        with get_db_cursor() as cursor:
            cursor.execute(
                'DELETE FROM Users WHERE tg_id = ? AND name = ? AND phone = ?',
                (tg_id, name, phone or "")
            )
            return cursor.rowcount > 0
    
    def create(self, name: str, phone: str, role: UserRole) -> User:
        with get_db_cursor() as cursor:
            cursor.execute(
                'INSERT INTO Users (tg_id, name, phone, role, status) VALUES (?, ?, ?, ?, ?)',
                ("0", name, phone, role.value, UserStatus.INVITE.value)
            )
            return User(
                tg_id="0",
                name=name,
                phone=phone,
                role=role,
                status=UserStatus.INVITE
            )
    
    def update_status(self, tg_id: int, status: UserStatus) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                'UPDATE Users SET status = ? WHERE tg_id = ?',
                (status.value, str(tg_id))
            )
            return cursor.rowcount > 0

    def update_name(self, tg_id: int, name: str) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                'UPDATE Users SET name = ? WHERE tg_id = ?',
                (name.strip(), str(tg_id))
            )
            return cursor.rowcount > 0

    def update_phone(self, tg_id: int, phone: str) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                'UPDATE Users SET phone = ? WHERE tg_id = ?',
                (phone.strip(), str(tg_id))
            )
            return cursor.rowcount > 0

    def update_role(self, tg_id: int, role: UserRole) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                'UPDATE Users SET role = ? WHERE tg_id = ?',
                (role.value, str(tg_id))
            )
            return cursor.rowcount > 0
    
    def activate_user(self, tg_id: int, name: str) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                'UPDATE Users SET status = ?, tg_id = ? WHERE name = ?',
                (UserStatus.ACTIVE.value, str(tg_id), name)
            )
            return cursor.rowcount > 0
    
    def block_user(self, tg_id: int) -> bool:
        return self.update_status(tg_id, UserStatus.BLOCKED)
    
    def check_blocked_user(self, tg_id: int) -> bool:
        """Проверить, заблокирован ли пользователь"""
        with get_db_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM Users WHERE tg_id = ? AND status = ?',
                (str(tg_id), UserStatus.BLOCKED.value)
            )
            return cursor.fetchone() is not None
    
    # Методы для совместимости
    def get_all_active_admin(self) -> List[User]:
        return self.get_all_active_admins()
    
    def get_all_active_driver(self) -> List[User]:
        return self.get_all_active_drivers()
    
    def get_all_invite_driver(self) -> List[User]:
        """Для совместимости с оригинальным кодом"""
        with get_db_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM Users WHERE role = ? AND status = ?',
                (UserRole.DRIVER.value, UserStatus.INVITE.value)
            )
            return [User.from_row(row) for row in cursor.fetchall()]
    
    def check_name_user(self, name: str) -> List[User]:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Users WHERE name = ?', (name,))
            return [User.from_row(row) for row in cursor.fetchall()]
    
    def get_user_on_id(self, tg_id: int) -> List[User]:
        user = self.get_by_tg_id(tg_id)
        return [user] if user else []
    
    def get_status_driver(self, tg_id: str) -> List[User]:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Users WHERE tg_id = ?', (tg_id,))
            return [User.from_row(row) for row in cursor.fetchall()]