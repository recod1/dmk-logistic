# database/models/repair.py
from dataclasses import dataclass, field
from typing import Optional
from config.settings import RepairStatus

@dataclass
class Repair:
    id_ticket: int
    tg_id: str
    number_auto: str
    malfunction: str
    status: RepairStatus = field(default=RepairStatus.NEW)
    date_repair: Optional[str] = field(default=None)
    place_repair: Optional[str] = field(default=None)
    comment_repair: Optional[str] = field(default=None)
    
    @classmethod
    def from_row(cls, row) -> 'Repair':
        return cls(
            id_ticket=row['id_ticket'],
            tg_id=str(row['tg_id']),
            number_auto=row['number_auto'],
            malfunction=row['malfunction'],
            status=RepairStatus(row['status']),
            date_repair=row['date_repair'],
            place_repair=row['place_repair'],
            comment_repair=row['comment_repair']
        )