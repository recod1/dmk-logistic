"""Parse 1C planned point date/time as naive Moscow wall clocks (24-hour)."""

from __future__ import annotations

import re

_DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DATE_DMY = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})")
_TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*([AaPp][Mm]))?")


def _pad2(value: int) -> str:
    return f"{int(value):02d}"


def format_planned_date(year: int, month: int, day: int) -> str:
    return f"{_pad2(day)}.{_pad2(month)}.{int(year):04d}"


def format_planned_time(hour: int, minute: int) -> str:
    return f"{_pad2(hour)}:{_pad2(minute)}"


def _hour_from_token(hour: int, ampm: str | None) -> int:
    if not ampm:
        return hour
    suffix = ampm.upper()
    if suffix == "AM":
        if hour == 12:
            return 0
        return hour
    if suffix == "PM":
        if hour == 12:
            return 12
        return hour + 12
    return hour


def split_onec_wall_datetime(raw: str | None) -> tuple[str, str]:
    """
    Split a 1C date/time string into (dd.MM.yyyy, HH:mm).

    Treats naive values as 24-hour Moscow wall time. Does not use UTC,
    Date.parse, ISO timezone conversion, or 12-hour output.
    AM/PM is applied only when the token is present (4:30 PM → 16:30).
    """
    text = (raw or "").strip()
    if not text:
        return "", ""

    date_s = ""
    rest = text
    iso = _DATE_ISO.search(text)
    dmy = _DATE_DMY.search(text)
    if iso and (not dmy or iso.start() <= dmy.start()):
        year, month, day = (int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        if 1 <= month <= 12 and 1 <= day <= 31:
            date_s = format_planned_date(year, month, day)
        rest = (text[: iso.start()] + " " + text[iso.end() :]).strip()
    elif dmy:
        day, month, year = (int(dmy.group(1)), int(dmy.group(2)), int(dmy.group(3)))
        if year < 100:
            year += 2000
        if 1 <= month <= 12 and 1 <= day <= 31:
            date_s = format_planned_date(year, month, day)
        rest = (text[: dmy.start()] + " " + text[dmy.end() :]).strip()

    search_in = rest or text
    time_s = ""
    tm = _TIME.search(search_in)
    if tm:
        hour = _hour_from_token(int(tm.group(1)), tm.group(4))
        minute = int(tm.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            time_s = format_planned_time(hour, minute)
    return date_s, time_s


def normalize_planned_date(raw: str | None) -> str:
    date_s, _ = split_onec_wall_datetime(raw)
    return date_s


def normalize_planned_time(raw: str | None) -> str:
    _, time_s = split_onec_wall_datetime(raw)
    if time_s:
        return time_s
    text = (raw or "").strip()
    tm = _TIME.fullmatch(text) or _TIME.search(text)
    if not tm:
        return ""
    hour = _hour_from_token(int(tm.group(1)), tm.group(4))
    minute = int(tm.group(2))
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return format_planned_time(hour, minute)
    return ""


def planned_wall_fields(date_raw: str | None, time_raw: str | None = None) -> tuple[str, str]:
    """Return (dd.MM.yyyy, HH:mm) without TZ/12-hour conversion."""
    date_s, time_from_date = split_onec_wall_datetime(date_raw)
    time_s = normalize_planned_time(time_raw) or time_from_date
    return date_s or (date_raw or "").strip(), time_s
