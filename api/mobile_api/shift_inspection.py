"""Vehicle intake / handover catalogs and validation for driver shifts."""

from __future__ import annotations

import json
import uuid
from typing import Any

WORKFLOW_DRAFT = "draft"
WORKFLOW_ACTIVE = "active"
WORKFLOW_CLOSING = "closing"
WORKFLOW_CLOSED = "closed"
OPEN_WORKFLOWS = (WORKFLOW_DRAFT, WORKFLOW_ACTIVE, WORKFLOW_CLOSING)

PHOTO_SLOTS = [
    {"k": "fl", "n": "Спереди слева", "req": False},
    {"k": "front", "n": "Спереди", "req": True},
    {"k": "fr", "n": "Спереди справа", "req": False},
    {"k": "left", "n": "Левый борт", "req": True},
    {"k": "right", "n": "Правый борт", "req": True},
    {"k": "rl", "n": "Сзади слева", "req": False},
    {"k": "rear", "n": "Сзади", "req": True},
    {"k": "rr", "n": "Сзади справа", "req": False},
    {"k": "cab", "n": "Место водителя", "req": True},
    {"k": "sleeper", "n": "Спальник и салон", "req": True},
    {"k": "odo", "n": "Одометр", "req": True},
    {"k": "fuel", "n": "Уровень топлива", "req": True},
    {"k": "reefer", "n": "Моточасы рефа", "req": True},
]
REQUIRED_PHOTO_SLOTS = tuple(item["k"] for item in PHOTO_SLOTS if item["req"])
CHECKS = [
    "Шины и колёса",
    "Световые приборы и сигналы",
    "Течи масла, топлива, ОЖ",
    "Тормоза и пневмосистема",
    "Седельно-сцепное устройство",
    "Тахограф исправен",
    "Рефрижератор работает",
    "Огнетушитель",
    "Аптечка",
    "Знак аварийной остановки",
    "Противооткатные упоры",
    "Светоотражающий жилет",
    "Пломба и запоры прицепа",
]
DOCS = [
    ("Водительское удостоверение", True, ""),
    ("Карта водителя (тахограф)", True, ""),
    ("Медицинская справка", True, ""),
    ("СТС тягача", False, ""),
    ("СТС прицепа", False, ""),
    ("Полис ОСАГО", True, ""),
    ("Диагностическая карта", True, ""),
    ("Калибровка тахографа", True, ""),
    ("Путевой лист", False, ""),
    ("Свидетельство СПС (ATP) на реф", True, ""),
    ("Свидетельство ДОПОГ", True, ""),
    ("Зелёная карта", True, ""),
    ("Медкнижка", True, "med"),
    ("Санпаспорт", True, "san"),
]
KIND_PERIODS = {"med": 12, "att": 24, "san": 12, "sanit": 1}
PHOTO_KIND_START = "start_photo"
PHOTO_KIND_END = "end_photo"
LEGACY_START_KINDS = ("start_photo", "start_vehicle", "start_waybill")
LEGACY_END_KINDS = ("end_photo", "end_vehicle")


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def empty_checks() -> list[dict]:
    return [{"id": _uid(), "name": name, "st": None, "note": ""} for name in CHECKS]


def empty_docs() -> list[dict]:
    items = []
    for name, needs_exp, kind in DOCS:
        items.append(
            {
                "id": _uid(),
                "name": name,
                "needs_exp": needs_exp,
                "has": None,
                "exp": "",
                "kind": kind,
                "d1": "",
                "d2": "",
                "custom": False,
            }
        )
    return items


def empty_phase() -> dict:
    return {
        "time": "",
        "place": "",
        "odo": "",
        "fuel": "",
        "reefer": "",
        "temp": "",
        "signed_at": None,
        "damages": [],
        "checks": empty_checks(),
        "docs": empty_docs(),
        "photos_meta": {},
    }


def handover_from_intake(intake: dict | None) -> dict:
    src = intake or {}
    docs = []
    for item in src.get("docs") or empty_docs():
        docs.append(
            {
                "id": _uid(),
                "name": item.get("name") or "",
                "needs_exp": bool(item.get("needs_exp")),
                "has": None,
                "exp": item.get("exp") or "",
                "kind": item.get("kind") or "",
                "d1": item.get("d1") or "",
                "d2": item.get("d2") or "",
                "custom": bool(item.get("custom")),
            }
        )
    names = [item.get("name") for item in (src.get("checks") or []) if item.get("name")]
    checks = [{"id": _uid(), "name": name, "st": None, "note": ""} for name in names] or empty_checks()
    return {
        "time": "",
        "place": "",
        "odo": "",
        "fuel": "",
        "reefer": "",
        "temp": "",
        "signed_at": None,
        "damages": [],
        "checks": checks,
        "docs": docs or empty_docs(),
        "photos_meta": {},
    }


def parse_json(raw: str | None, fallback):
    if not raw:
        return fallback
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return fallback
    return data if data is not None else fallback


def dump_json(data) -> str:
    return json.dumps(data if data is not None else {}, ensure_ascii=False)


def photo_slots(images: list, *, phase: str) -> set[str]:
    kinds = LEGACY_START_KINDS if phase == "start" else LEGACY_END_KINDS
    found: set[str] = set()
    for row in images:
        kind = getattr(row, "kind", "") if not isinstance(row, dict) else row.get("kind") or ""
        slot = getattr(row, "slot", "") if not isinstance(row, dict) else row.get("slot") or ""
        if kind in kinds and slot:
            found.add(slot)
        if phase == "start" and kind == "start_waybill":
            found.add("waybill")
    return found


def _num(value) -> float | None:
    text = str(value if value is not None else "").strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _diff(a, b) -> float | None:
    left, right = _num(a), _num(b)
    if left is None or right is None:
        return None
    return round(right - left, 1)


def analyse(shift: dict, phase: str, photo_keys: set[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    payload = shift.get("intake") if phase == "start" else shift.get("handover")
    payload = payload or {}
    if phase == "start":
        if not (shift.get("driver_name") or "").strip():
            out.append(("bad", "Не указан водитель"))
        if not (shift.get("truck") or "").strip():
            out.append(("bad", "Не указан госномер тягача"))
    elif not (payload.get("time") or "").strip():
        out.append(("bad", "Не указано время окончания вахты"))
    miss = [item["n"] for item in PHOTO_SLOTS if item["req"] and item["k"] not in photo_keys]
    if miss:
        out.append(("bad", f"Нет фото: {', '.join(n.lower() for n in miss)}"))
    if str(payload.get("odo") or "").strip() == "":
        out.append(("bad", "Не внесены показания одометра"))
    if str(payload.get("fuel") if payload.get("fuel") is not None else "").strip() == "":
        out.append(("bad", "Не внесён остаток топлива"))
    if str(payload.get("reefer") or "").strip() == "":
        out.append(("bad", "Не внесены моточасы рефрижератора"))
    damages = payload.get("damages") or []
    if phase == "start" and damages:
        out.append(("warn", f"Зафиксировано повреждений при приёмке: {len(damages)}"))
    if phase == "end" and damages:
        start_n = len((shift.get("intake") or {}).get("damages") or [])
        out.append(("warn", f"Повреждений при сдаче: {len(damages)} (при приёмке было {start_n})"))
    if not payload.get("signed_at"):
        out.append(("warn", "Нет подписи водителя"))
    nd = len([item for item in damages if not str(item.get("note") or "").strip()])
    if nd:
        out.append(("warn", f"Нет описания у повреждений: {nd}"))
    if phase == "end":
        intake = shift.get("intake") or {}
        dk = _diff(intake.get("odo"), payload.get("odo"))
        dh = _diff(intake.get("reefer"), payload.get("reefer"))
        if dk is not None and dk < 0:
            out.append(("bad", f"Пробег на сдаче меньше, чем на приёмке ({intake.get('odo') or '—'} км)"))
        if dh is not None and dh < 0:
            out.append(("bad", f"Моточасы на сдаче меньше, чем на приёмке ({intake.get('reefer') or '—'})"))
    checks = payload.get("checks") or []
    unset = len([item for item in checks if item.get("st") is None])
    if unset:
        out.append(("warn", f"Не проверено пунктов состояния: {unset}"))
    for item in checks:
        if item.get("st") == "bad":
            note = (item.get("note") or "").strip()
            extra = f" — {note}" if note else ""
            out.append(("bad", f"Неисправно: {item.get('name') or ''}{extra}"))
    docs = payload.get("docs") or []
    unk = len([item for item in docs if item.get("has") is None])
    if unk:
        out.append(("warn", f"Не отмечено документов: {unk}"))
    start_docs = (shift.get("intake") or {}).get("docs") or []
    for item in docs:
        if item.get("has") == "n":
            was = phase == "end" and any(x.get("name") == item.get("name") and x.get("has") == "y" for x in start_docs)
            extra = " (был на приёмке)" if was else ""
            out.append(("bad", f"Нет документа: {item.get('name') or ''}{extra}"))
    return out


def blocking_issues(shift: dict, phase: str, photo_keys: set[str]) -> list[str]:
    return [text for level, text in analyse(shift, phase, photo_keys) if level == "bad"]


def as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list:
    return value if isinstance(value, list) else []
