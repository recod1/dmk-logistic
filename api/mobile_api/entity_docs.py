"""Persistent documents for vehicles, trailers and drivers (from the shift check step)."""

from __future__ import annotations

import json
from typing import Any

from mobile_api.shift_inspection import dump_json, parse_json

EntityKind = str

DOC_SPECS: dict[str, list[dict[str, Any]]] = {
    "vehicle": [
        {"key": "sts", "name": "СТС тягача", "needs_exp": False, "kind": ""},
        {"key": "osago", "name": "Полис ОСАГО", "needs_exp": True, "kind": ""},
        {"key": "diagnostic", "name": "Диагностическая карта", "needs_exp": True, "kind": ""},
        {"key": "tacho_calib", "name": "Калибровка тахографа", "needs_exp": True, "kind": ""},
        {"key": "green_card", "name": "Зелёная карта", "needs_exp": True, "kind": ""},
        {"key": "dopog", "name": "Свидетельство ДОПОГ (ТС)", "needs_exp": True, "kind": ""},
    ],
    "trailer": [
        {"key": "sts", "name": "СТС прицепа", "needs_exp": False, "kind": ""},
        {"key": "atp", "name": "Свидетельство СПС (ATP) на реф", "needs_exp": True, "kind": ""},
        {"key": "san", "name": "Санпаспорт", "needs_exp": True, "kind": "san"},
        {"key": "diagnostic", "name": "Диагностическая карта прицепа", "needs_exp": True, "kind": ""},
    ],
    "driver": [
        {"key": "license", "name": "Водительское удостоверение", "needs_exp": True, "kind": ""},
        {"key": "tacho_card", "name": "Карта водителя (тахограф)", "needs_exp": True, "kind": ""},
        {"key": "med_cert", "name": "Медицинская справка", "needs_exp": True, "kind": ""},
        {"key": "medbook", "name": "Медкнижка", "needs_exp": True, "kind": "med"},
        {"key": "dopog", "name": "Свидетельство ДОПОГ", "needs_exp": True, "kind": ""},
    ],
}

# Shift check-step rows that belong to a lasting object. Waybill and condition checks stay per-shift.
SHIFT_DOC_BINDINGS: dict[str, tuple[str, str]] = {
    "Водительское удостоверение": ("driver", "license"),
    "Карта водителя (тахограф)": ("driver", "tacho_card"),
    "Медицинская справка": ("driver", "med_cert"),
    "Медкнижка": ("driver", "medbook"),
    "Свидетельство ДОПОГ": ("driver", "dopog"),
    "СТС тягача": ("vehicle", "sts"),
    "Полис ОСАГО": ("vehicle", "osago"),
    "Диагностическая карта": ("vehicle", "diagnostic"),
    "Калибровка тахографа": ("vehicle", "tacho_calib"),
    "Зелёная карта": ("vehicle", "green_card"),
    "СТС прицепа": ("trailer", "sts"),
    "Свидетельство СПС (ATP) на реф": ("trailer", "atp"),
    "Санпаспорт": ("trailer", "san"),
}


def _blank_item(spec: dict[str, Any]) -> dict[str, Any]:
    return {"has": None, "exp": "", "d1": "", "d2": "", "note": "", "kind": spec.get("kind") or ""}


def empty_profile(kind: str) -> dict[str, dict[str, Any]]:
    return {spec["key"]: _blank_item(spec) for spec in DOC_SPECS.get(kind, [])}


def parse_docs(raw: str | None, kind: str) -> dict[str, dict[str, Any]]:
    base = empty_profile(kind)
    data = parse_json(raw, {})
    if not isinstance(data, dict):
        return base
    for spec in DOC_SPECS.get(kind, []):
        key = spec["key"]
        src = data.get(key)
        if not isinstance(src, dict):
            continue
        has = src.get("has")
        if has not in {"y", "n", "x", None}:
            has = None
        base[key] = {
            "has": has,
            "exp": str(src.get("exp") or ""),
            "d1": str(src.get("d1") or ""),
            "d2": str(src.get("d2") or ""),
            "note": str(src.get("note") or "")[:255],
            "kind": spec.get("kind") or "",
        }
    return base


def dump_docs(docs: dict[str, Any] | None, kind: str) -> str:
    cleaned = parse_docs(dump_json(docs or {}), kind)
    return dump_json(cleaned)


def apply_profile_to_shift_docs(docs: list[dict[str, Any]], profile: dict[str, Any] | None, entity: str) -> list[dict[str, Any]]:
    saved = profile or {}
    for doc in docs:
        bind = SHIFT_DOC_BINDINGS.get(str(doc.get("name") or ""))
        if not bind or bind[0] != entity:
            continue
        item = saved.get(bind[1]) or {}
        if doc.get("has") is not None or not item.get("has"):
            continue
        doc["has"] = item.get("has")
        doc["exp"] = item.get("exp") or doc.get("exp") or ""
        doc["d1"] = item.get("d1") or doc.get("d1") or ""
        doc["d2"] = item.get("d2") or doc.get("d2") or ""
        if item.get("kind") and not doc.get("kind"):
            doc["kind"] = item["kind"]
    return docs


def collect_writeback(docs: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = {"driver": {}, "vehicle": {}, "trailer": {}}
    for doc in docs:
        bind = SHIFT_DOC_BINDINGS.get(str(doc.get("name") or ""))
        if not bind or doc.get("has") is None:
            continue
        entity, key = bind
        out[entity][key] = {
            "has": doc.get("has"),
            "exp": doc.get("exp") or "",
            "d1": doc.get("d1") or "",
            "d2": doc.get("d2") or "",
            "note": "",
            "kind": doc.get("kind") or "",
        }
    return out


def merge_writeback(current_raw: str | None, kind: str, incoming: dict[str, Any]) -> str:
    merged = parse_docs(current_raw, kind)
    for key, value in (incoming or {}).items():
        if key in merged and isinstance(value, dict):
            merged[key] = {
                **merged[key],
                "has": value.get("has", merged[key]["has"]),
                "exp": str(value.get("exp") or merged[key]["exp"]),
                "d1": str(value.get("d1") or merged[key]["d1"]),
                "d2": str(value.get("d2") or merged[key]["d2"]),
            }
    return dump_docs(merged, kind)
