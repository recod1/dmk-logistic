# database/models/user.py
from dataclasses import dataclass, field
from typing import Optional
from config.settings import UserRole, UserStatus

@dataclass
class User:
    tg_id: Optional[str] = field(default=None)
    name: Optional[str] = field(default=None)
    phone: Optional[str] = field(default=None)
    role: UserRole = field(default=UserRole.DRIVER)
    status: UserStatus = field(default=UserStatus.INVITE)
    
    @classmethod
    def from_row(cls, row) -> 'User':
        return cls(
            tg_id=str(row['tg_id']) if row['tg_id'] else None,
            name=row['name'],
            phone=row['phone'],
            role=UserRole(row['role']),
            status=UserStatus(row['status'])
        )