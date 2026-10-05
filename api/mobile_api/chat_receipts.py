from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def bump_int_field(row: object, field: str, value: int) -> int:
    current = int(getattr(row, field) or 0)
    nxt = max(current, int(value or 0))
    setattr(row, field, nxt)
    if hasattr(row, "updated_at"):
        setattr(row, "updated_at", datetime.now(timezone.utc))
    return nxt


def others_watermark(db: Session, id_attr: object, *where: object) -> int:
    return int(db.scalar(select(func.max(id_attr)).where(*where)) or 0)


def upsert_watermark(
    db: Session,
    *,
    model: type,
    match: dict[str, object],
    field: str,
    value: int,
    factory: Callable[[], object],
) -> int:
    row = db.scalar(select(model).where(*[getattr(model, key) == val for key, val in match.items()]))
    if row is None:
        row = factory()
        for key, val in match.items():
            setattr(row, key, val)
        setattr(row, field, int(value or 0))
        db.add(row)
        return int(value or 0)
    return bump_int_field(row, field, value)
