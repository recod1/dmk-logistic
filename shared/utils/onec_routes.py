from __future__ import annotations

from dataclasses import dataclass

from utils.onec_datetime import split_onec_wall_datetime

_PLACEHOLDER_PHONE_TAILS = frozenset({"9991234567"})


@dataclass(frozen=True)
class OnecPoint:
    type_point: str
    date_point: str
    point_time: str
    place_point: str


@dataclass(frozen=True)
class OnecParsedRoute:
    route_id: str
    driver_fio: str
    logistic_name: str
    number_auto: str
    trailer_number: str
    temperature: str
    dispatcher_contacts: str
    registration_number: str
    points: list[OnecPoint]


def _clean_lines(raw: str) -> list[str]:
    return [line.strip() for line in (raw or "").splitlines() if line.strip()]


def _phone_digits(text: str) -> str:
    return "".join(ch for ch in (text or "") if ch.isdigit())


def is_placeholder_dispatcher_phone(text: str) -> bool:
    digits = _phone_digits(text)
    if len(digits) < 10:
        return False
    return digits[-10:] in _PLACEHOLDER_PHONE_TAILS


def _contact_priority(key_lower: str) -> int | None:
    """Lower is better. None = not a dispatcher-contact field."""
    if "логист" in key_lower and "диспетчер" not in key_lower:
        return None
    if "контакт" in key_lower and ("ооо" in key_lower or "дмк" in key_lower):
        return 1
    if "телефон" in key_lower and "диспетчер" in key_lower:
        return 2
    if key_lower.startswith("диспетчер"):
        return 2
    if key_lower == "контакты" or key_lower.startswith("контакты"):
        return 3
    if "диспетчер" in key_lower:
        return 4
    return None


def _is_logistic_key(key_lower: str) -> bool:
    if "контакт" in key_lower or "диспетчер" in key_lower:
        return False
    return "логист" in key_lower


def _pick_dispatcher_contacts(hits: list[tuple[int, str]]) -> str:
    if not hits:
        return ""
    ranked = sorted(
        hits,
        key=lambda item: (item[0], 1 if is_placeholder_dispatcher_phone(item[1]) else 0),
    )
    return ranked[0][1].strip()


def parse_onec_message(raw: str) -> OnecParsedRoute:
    """
    Parse 1C text format used in Telegram and PWA import.
    The goal is compatibility, not strict validation.
    """
    lines = _clean_lines(raw)
    route_id = ""
    driver_fio = ""
    logistic_name = ""
    number_auto = ""
    trailer_number = ""
    temperature = ""
    registration_number = ""
    contact_hits: list[tuple[int, str]] = []

    points: list[OnecPoint] = []
    points_start_idx: int | None = None

    for idx, line in enumerate(lines):
        lower = line.lower()
        if lower.startswith("загр:") or lower.startswith("выгр:"):
            points_start_idx = idx
            break

        if ":" in line:
            key, value = line.split(":", 1)
            key_lower = key.strip().lower()
            value = value.strip()
            if "номер для регистрации" in key_lower or "номер регистрации" in key_lower:
                registration_number = value
            elif "фио водителя" in key_lower:
                driver_fio = value
            elif _is_logistic_key(key_lower):
                logistic_name = value
            elif "номер тс" in key_lower:
                number_auto = value
            elif "номер прицепа" in key_lower:
                trailer_number = (value or "").strip().upper()
            elif "температура" in key_lower:
                temperature = value
            else:
                priority = _contact_priority(key_lower)
                if priority is not None and value:
                    contact_hits.append((priority, value))
        elif not route_id and line:
            route_id = line

    if points_start_idx is not None:
        i = points_start_idx
        while i < len(lines):
            line = lines[i]
            lower = line.lower()
            if not (lower.startswith("загр:") or lower.startswith("выгр:")):
                i += 1
                continue

            type_point = "loading" if lower.startswith("загр:") else "unloading"
            after_type = line.split(":", 1)[1].strip()
            after_lower = after_type.lower()

            pos_org = after_lower.find("организация:")
            if pos_org < 0:
                pos_org = after_lower.find("организация ")
            if pos_org < 0:
                pos_org = after_lower.find("организация")

            date_time = ""
            place = ""
            if pos_org >= 0:
                date_time = after_type[:pos_org].strip()
                org_part = after_type[pos_org:].strip()
                if org_part.lower().startswith("организация:"):
                    place = org_part.split(":", 1)[1].strip()
                else:
                    place = org_part[len("Организация") :].lstrip(" :").strip()
            else:
                date_time = after_type
                i += 1
                if i >= len(lines):
                    break
                org_line = lines[i]
                org_lower = org_line.lower()
                if org_lower.startswith("организация"):
                    if org_lower.startswith("организация:"):
                        place = org_line.split(":", 1)[1].strip()
                    else:
                        place = org_line[len("Организация") :].lstrip(" :").strip()
                else:
                    place = org_line

            contact_pos = place.lower().find("контакт")
            if contact_pos >= 0:
                place = place[:contact_pos].strip()
            place = " ".join(place.split())

            if date_time and place:
                date_point, point_time = split_onec_wall_datetime(date_time)
                points.append(
                    OnecPoint(
                        type_point=type_point,
                        date_point=date_point or date_time,
                        point_time=point_time,
                        place_point=place,
                    )
                )

            i += 1

    return OnecParsedRoute(
        route_id=route_id.strip(),
        driver_fio=driver_fio.strip(),
        logistic_name=logistic_name.strip(),
        number_auto=number_auto.strip(),
        trailer_number=trailer_number.strip(),
        temperature=temperature.strip(),
        dispatcher_contacts=_pick_dispatcher_contacts(contact_hits),
        registration_number=registration_number.strip(),
        points=points,
    )
