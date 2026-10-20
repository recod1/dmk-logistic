"""Archive cancelled route ids so the original number can be reused."""

from __future__ import annotations

ARCHIVED_ROUTE_MARK = "~"
_ROUTE_ID_MAX_LEN = 64


def next_archived_route_id(original_id: str, existing_ids: set[str]) -> str:
    """Return `{original}~N` that is free and fits the routes.id column."""
    base = (original_id or "").strip()
    if not base:
        raise ValueError("original_id is required")
    taken = {item for item in existing_ids if item}
    n = 1
    while True:
        suffix = f"{ARCHIVED_ROUTE_MARK}{n}"
        archive_id = f"{base}{suffix}"
        if len(archive_id) > _ROUTE_ID_MAX_LEN:
            archive_id = f"{base[: _ROUTE_ID_MAX_LEN - len(suffix)]}{suffix}"
        if archive_id not in taken:
            return archive_id
        n += 1


def route_id_search_like(route_id: str) -> str:
    """LIKE pattern that matches archived copies of the same number."""
    return f"{route_id.strip()}{ARCHIVED_ROUTE_MARK}%"
