# database/base.py
import sqlite3
from contextlib import contextmanager
from typing import Generator
from config.settings import settings

@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Контекстный менеджер для работы с БД"""
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

@contextmanager
def get_db_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """Контекстный менеджер для работы с курсором"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()