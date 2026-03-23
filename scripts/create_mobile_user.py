#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pathlib
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# Ensure repository root is importable regardless of cwd.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from mobile_api.auth import hash_password
from mobile_api.models import User
from mobile_api.roles import normalize_role_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update mobile API user.")
    parser.add_argument("--pg-dsn", required=True, help="Postgres SQLAlchemy DSN")
    parser.add_argument("--login", required=True, help="User login")
    parser.add_argument("--password", required=True, help="User password")
    parser.add_argument("--role", default="driver", help="User role (driver/admin/logistic/...)")
    parser.add_argument("--full-name", default="", help="Optional full name")
    parser.add_argument("--phone", default="", help="Optional phone")
    parser.add_argument("--legacy-tg-id", default="", help="Optional legacy tg_id")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    role_code = normalize_role_code(args.role).value
    engine = create_engine(args.pg_dsn, future=True)
    session = Session(engine)
    try:
        user = session.scalar(select(User).where(User.login == args.login))
        if user is None:
            user = User(
                login=args.login,
                password_hash=hash_password(args.password),
                role_code=role_code,
                full_name=args.full_name or None,
                phone=args.phone or None,
                legacy_tg_id=args.legacy_tg_id or None,
                is_active=True,
            )
            session.add(user)
            action = "created"
        else:
            user.password_hash = hash_password(args.password)
            user.role_code = role_code
            user.full_name = args.full_name or user.full_name
            user.phone = args.phone or user.phone
            user.legacy_tg_id = args.legacy_tg_id or user.legacy_tg_id
            user.is_active = True
            action = "updated"
        session.commit()
        print(f"User {action}: login={args.login}, role_code={user.role_code}, id={user.id}")
    finally:
        session.close()


if __name__ == "__main__":
    main()

