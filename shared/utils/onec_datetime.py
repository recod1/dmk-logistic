"""Parse 1C planned point date/time as naive Moscow wall clocks (24-hour)."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

_DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DATE_DMY = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})")
_TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*([AaPp][Mm])(?![A-Za-z]))?")
_TIME_FLEX = re.compile(r"(?<!\d)(\d{1,2})[.\-](\d{2})(?:[.\-](\d{2}))?(?!\d)")
_MOSCOW = ZoneInfo("Europe/Moscow")


def _pad2(value: int) -> str:
    return f"{int(value):02d}"


def format_planned_date(year: int, month: int, day: int) -> str:
    return f"{_pad2(day)}.{_pad2(month)}.{int(year):04d}"


def format_planned_time(hour: int, minute: int) -> str:
    return f"{_pad2(hour)}:{_pad2(minute)}"


def _hour_from_token(hour: int, ampm: str | None) -> int:
    if not ampm or hour > 12:
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

    search_in = rest if date_s else text
    time_s = ""
    tm = _TIME.search(search_in)
    hour = minute = None
    if tm:
        hour = _hour_from_token(int(tm.group(1)), tm.group(4))
        minute = int(tm.group(2))
    else:
        flex = _TIME_FLEX.search(search_in)
        if flex:
            hour = int(flex.group(1))
            minute = int(flex.group(2))
    if hour is not None and minute is not None and 0 <= hour <= 23 and 0 <= minute <= 59:
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


def _clock_hm(value: str) -> tuple[int, int] | None:
    text = (value or "").strip()
    if len(text) < 4 or ":" not in text:
        return None
    hour_s, minute_s = text.split(":", 1)
    try:
        hour = int(hour_s)
        minute = int(minute_s[:2])
    except ValueError:
        return None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def prefer_24h_wall_time(time_from_date: str, time_from_time: str) -> str:
    """If 1C sends 14:00 on the date and 02:00 in a 12-hour time field, keep 14:00."""
    if time_from_date and time_from_time:
        left = _clock_hm(time_from_date)
        right = _clock_hm(time_from_time)
        if left and right and left[1] == right[1] and abs(left[0] - right[0]) == 12:
            return format_planned_time(max(left[0], right[0]), left[1])
        if left and right and left[0] >= 13 and right[0] <= 12:
            return time_from_date
        return time_from_time
    return time_from_time or time_from_date


def planned_wall_fields(date_raw: str | None, time_raw: str | None = None) -> tuple[str, str]:
    """Return (dd.MM.yyyy, HH:mm) without TZ/12-hour conversion."""
    date_s, time_from_date = split_onec_wall_datetime(date_raw)
    time_from_time = normalize_planned_time(time_raw)
    time_s = prefer_24h_wall_time(time_from_date, time_from_time)
    return date_s or (date_raw or "").strip(), time_s


def planned_wall_datetime(date_raw: str | None, time_raw: str | None = None) -> datetime | None:
    """Moscow-aware datetime for a planned wall clock, or None if incomplete."""
    date_s, time_s = planned_wall_fields(date_raw, time_raw)
    if not date_s or not time_s:
        return None
    try:
        naive = datetime.strptime(f"{date_s} {time_s}", "%d.%m.%Y %H:%M")
    except ValueError:
        return None
    return naive.replace(tzinfo=_MOSCOW)
