"""Parse 1C planned point date/time as naive Moscow wall clocks (24-hour)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DATE_DMY = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})")
_TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*([AaPp][Mm])(?![A-Za-z]))?")
_TIME_FLEX = re.compile(r"(?<!\d)(\d{1,2})[.\-](\d{2})(?:[.\-](\d{2}))?(?!\d)")
_MS_DATE = re.compile(r"/Date\((-?\d+)(?:[+-]\d{4})?\)/")
_FOLLOWED_BY_YEAR = re.compile(r"[./-]\d{2,4}(?!\d)")
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


def _from_moscow(dt: datetime) -> tuple[str, str]:
    local = dt.astimezone(_MOSCOW) if dt.tzinfo else dt.replace(tzinfo=_MOSCOW)
    return format_planned_date(local.year, local.month, local.day), format_planned_time(local.hour, local.minute)


def _from_ms_epoch(ms: int) -> tuple[str, str]:
    utc = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return _from_moscow(utc)


def _from_numeric_clock(value: float) -> str:
    if value > 1e11:
        date_s, time_s = _from_ms_epoch(int(value))
        return f"{date_s} {time_s}".strip()
    if value > 1e9:
        utc = datetime.fromtimestamp(value, tz=timezone.utc)
        date_s, time_s = _from_moscow(utc)
        return f"{date_s} {time_s}".strip()
    if value >= 60:
        # Excel serial date (days since 1899-12-30) or minutes from midnight.
        if value >= 20000:
            whole = int(value)
            fraction = float(value) - whole
            total_seconds = int(round(fraction * 86400))
            base = datetime(1899, 12, 30) + timedelta(days=whole)
            hour = total_seconds // 3600
            minute = (total_seconds % 3600) // 60
            return f"{format_planned_date(base.year, base.month, base.day)} {format_planned_time(hour, minute)}".strip()
        minutes = int(round(value))
        return format_planned_time(minutes // 60, minutes % 60)
    if value >= 1:
        hour = int(value)
        minute = int(round((float(value) - hour) * 60))
        if minute == 60:
            hour += 1
            minute = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return format_planned_time(hour, minute)
        return ""
    if value > 0:
        total_minutes = int(round(float(value) * 24 * 60))
        return format_planned_time(total_minutes // 60, total_minutes % 60)
    return ""


def coerce_onec_datetime_input(raw: object | None) -> str:
    """Flatten 1C/JSON values to a string the wall-clock parser can read."""
    if raw is None:
        return ""
    if isinstance(raw, datetime):
        if raw.tzinfo is not None:
            date_s, time_s = _from_moscow(raw)
        else:
            date_s = format_planned_date(raw.year, raw.month, raw.day)
            time_s = format_planned_time(raw.hour, raw.minute)
        if raw.year <= 1:
            return time_s
        return f"{date_s} {time_s}".strip()
    if isinstance(raw, date):
        if raw.year <= 1:
            return ""
        return format_planned_date(raw.year, raw.month, raw.day)
    if isinstance(raw, bool):
        return ""
    if isinstance(raw, (int, float)):
        return _from_numeric_clock(float(raw))
    if isinstance(raw, dict):
        for key in ("#value", "value", "Date", "date", "Time", "time", "Дата", "Время"):
            if key in raw and raw[key] is not None:
                return coerce_onec_datetime_input(raw[key])
        return ""
    return str(raw).strip()


def split_onec_wall_datetime(raw: object | None) -> tuple[str, str]:
    """
    Split a 1C date/time value into (dd.MM.yyyy, HH:mm).

    Naive ISO/text is 24-hour wall clock (18:30 stays 18:30).
    `/Date(ms)/` and timezone-aware datetimes are converted to Europe/Moscow.
    AM/PM is applied only when the token is present (4:30 PM → 16:30).
    """
    text = coerce_onec_datetime_input(raw)
    if not text:
        return "", ""

    ms = _MS_DATE.search(text)
    if ms and not _DATE_ISO.search(text) and not _DATE_DMY.search(text) and ":" not in text:
        return _from_ms_epoch(int(ms.group(1)))

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
    time_s = _pick_wall_clock_time(search_in)
    return date_s, time_s


def _is_date_fragment(text: str, start: int, end: int) -> bool:
    if _FOLLOWED_BY_YEAR.match(text[end:]):
        return True
    prefix = text[:start]
    return bool(re.search(r"\d{4}[./-]$", prefix))


def _pick_wall_clock_time(search_in: str) -> str:
    candidates: list[tuple[int, int]] = []
    for tm in _TIME.finditer(search_in):
        hour = _hour_from_token(int(tm.group(1)), tm.group(4))
        minute = int(tm.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            candidates.append((hour, minute))
    if not candidates:
        for flex in _TIME_FLEX.finditer(search_in):
            if flex.group(3) is not None and re.match(r"\d", search_in[flex.end() :]):
                continue
            if _is_date_fragment(search_in, flex.start(), flex.end()):
                continue
            hour = int(flex.group(1))
            minute = int(flex.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                candidates.append((hour, minute))
    if not candidates:
        return ""
    afternoon = next((item for item in candidates if item[0] >= 13), None)
    hour, minute = afternoon or candidates[0]
    return format_planned_time(hour, minute)


def normalize_planned_date(raw: object | None) -> str:
    date_s, _ = split_onec_wall_datetime(raw)
    return date_s


def normalize_planned_time(raw: object | None) -> str:
    _, time_s = split_onec_wall_datetime(raw)
    if time_s:
        return time_s
    text = coerce_onec_datetime_input(raw)
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


def planned_wall_fields(date_raw: object | None, time_raw: object | None = None) -> tuple[str, str]:
    """Return (dd.MM.yyyy, HH:mm) without 12-hour output."""
    date_text = coerce_onec_datetime_input(date_raw)
    time_text = coerce_onec_datetime_input(time_raw)
    date_s, time_from_date = split_onec_wall_datetime(date_text)
    time_from_time = normalize_planned_time(time_text)
    time_s = prefer_24h_wall_time(time_from_date, time_from_time)
    return date_s or date_text, time_s


def planned_wall_datetime(date_raw: object | None, time_raw: object | None = None) -> datetime | None:
    """Moscow-aware datetime for a planned wall clock, or None if incomplete."""
    date_s, time_s = planned_wall_fields(date_raw, time_raw)
    if not date_s or not time_s:
        return None
    try:
        naive = datetime.strptime(f"{date_s} {time_s}", "%d.%m.%Y %H:%M")
    except ValueError:
        return None
    return naive.replace(tzinfo=_MOSCOW)
