# database/repositories/repair_repository.py
from typing import List, Optional
from database.base import get_db_cursor
from database.models.repair import Repair
from config.settings import RepairStatus
from .base import BaseRepository

class RepairRepository(BaseRepository):
    
    def get_by_id(self, repair_id: int) -> Optional[Repair]:
        # В таблице Repair нет числового id, только id_ticket
        return self.get_by_ticket_id(repair_id)
    
    def get_all(self) -> List[Repair]:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Repair')
            return [Repair.from_row(row) for row in cursor.fetchall()]
    
    def get_by_ticket_id(self, ticket_id: int) -> Optional[Repair]:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Repair WHERE id_ticket = ?', (ticket_id,))
            row = cursor.fetchone()
            return Repair.from_row(row) if row else None
    
    def get_by_tg_id(self, tg_id: int) -> List[Repair]:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Repair WHERE tg_id = ?', (str(tg_id),))
            return [Repair.from_row(row) for row in cursor.fetchall()]
    
    def get_by_number_auto(self, number_auto: str) -> List[Repair]:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Repair WHERE number_auto = ?', (number_auto,))
            return [Repair.from_row(row) for row in cursor.fetchall()]
    
    def get_by_status(self, status: RepairStatus) -> List[Repair]:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT * FROM Repair WHERE status = ?', (status.value,))
            return [Repair.from_row(row) for row in cursor.fetchall()]
    
    def create(self, id_ticket: int, tg_id: int, number_auto: str, malfunction: str) -> Repair:
        with get_db_cursor() as cursor:
            cursor.execute(
                '''INSERT INTO Repair 
                (id_ticket, tg_id, number_auto, malfunction, status, date_repair, place_repair, comment_repair) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (id_ticket, str(tg_id), number_auto, malfunction, 
                 RepairStatus.NEW.value, "0", "0", "0")
            )
            return self.get_by_ticket_id(id_ticket)
    
    def update_status(self, ticket_id: int, status: RepairStatus) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                'UPDATE Repair SET status = ? WHERE id_ticket = ?',
                (status.value, ticket_id)
            )
            return cursor.rowcount > 0
    
    def process_ticket(self, ticket_id: int, date_repair: str, place_repair: str, comment_repair: str) -> bool:
        with get_db_cursor() as cursor:
            cursor.execute(
                '''UPDATE Repair SET 
                status = ?, date_repair = ?, place_repair = ?, comment_repair = ? 
                WHERE id_ticket = ?''',
                (RepairStatus.PROCESS.value, date_repair, place_repair, comment_repair, ticket_id)
            )
            return cursor.rowcount > 0
    
    def count_all(self) -> int:
        with get_db_cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM Repair')
            return cursor.fetchone()[0]
    
    def get_next_ticket_id(self) -> int:
        """
        Получить следующий ID заявки на ремонт.
        Использует MAX(id_ticket) + 1, чтобы номера не переиспользовались после удаления записей.
        """
        with get_db_cursor() as cursor:
            cursor.execute('SELECT MAX(id_ticket) FROM Repair')
            result = cursor.fetchone()
            last_id = result[0] if result and result[0] is not None else 0
            return last_id + 1
    
    # Методы для обновления статусов из оригинального кода
    def confirm_ticket_repair(self, ticket_id: int) -> bool:
        return self.update_status(ticket_id, RepairStatus.CONFIRM)
    
    def proc_repair_ticket_repair(self, ticket_id: int) -> bool:
        return self.update_status(ticket_id, RepairStatus.PROC_REPAIR)
    
    def conf_repair_ticket_repair(self, ticket_id: int) -> bool:
        return self.update_status(ticket_id, RepairStatus.CONF_REPAIR)
    
    def success_repair_ticket_repair(self, ticket_id: int) -> bool:
        return self.update_status(ticket_id, RepairStatus.SUCCESS)

    def delete(self, ticket_id: int) -> bool:
        """Удалить заявку на ремонт по id_ticket."""
        with get_db_cursor() as cursor:
            cursor.execute('DELETE FROM Repair WHERE id_ticket = ?', (ticket_id,))
            return cursor.rowcount > 0

    def reassign_driver(self, ticket_id: int, new_tg_id: str) -> bool:
        """Переназначить заявку на другого водителя."""
        with get_db_cursor() as cursor:
            cursor.execute(
                'UPDATE Repair SET tg_id = ? WHERE id_ticket = ?',
                (str(new_tg_id), ticket_id)
            )
            return cursor.rowcount > 0

    def update_details(
        self,
        ticket_id: int,
        number_auto: str = None,
        malfunction: str = None,
        date_repair: str = None,
        place_repair: str = None,
        comment_repair: str = None,
    ) -> bool:
        """Обновить детали ремонта (кроме водителя). Передавать только изменяемые поля."""
        updates = []
        params = []
        if number_auto is not None:
            updates.append('number_auto = ?')
            params.append(number_auto)
        if malfunction is not None:
            updates.append('malfunction = ?')
            params.append(malfunction)
        if date_repair is not None:
            updates.append('date_repair = ?')
            params.append(date_repair)
        if place_repair is not None:
            updates.append('place_repair = ?')
            params.append(place_repair)
        if comment_repair is not None:
            updates.append('comment_repair = ?')
            params.append(comment_repair)
        if not updates:
            return False
        params.append(ticket_id)
        with get_db_cursor() as cursor:
            cursor.execute(
                f'UPDATE Repair SET {", ".join(updates)} WHERE id_ticket = ?',
                params
            )
            return cursor.rowcount > 0