from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from mobile_api.auth import hash_password
from mobile_api.models import User
from mobile_api.settings import mobile_settings


def ensure_demo_user(db: Session) -> None:
    if not mobile_settings.bootstrap_demo_user:
        return

    existing = db.scalar(select(User).where(User.login == mobile_settings.demo_login))
    if existing:
        return

    demo = User(
        login=mobile_settings.demo_login,
        password_hash=hash_password(mobile_settings.demo_password),
        role=mobile_settings.demo_role,
        full_name="Demo User",
        is_active=True,
    )
    db.add(demo)
    db.commit()

