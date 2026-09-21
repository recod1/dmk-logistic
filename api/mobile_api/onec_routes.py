from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OnecPoint:
    type_point: str
    date_point: str
    place_point: str


@dataclass(frozen=True)
class OnecParsedRoute:
    route_id: str
    driver_fio: str
    number_auto: str
    trailer_number: str
    temperature: str
    dispatcher_contacts: str
    registration_number: str
    points: list[OnecPoint]


def _clean_lines(raw: str) -> list[str]:
    return [line.strip() for line in (raw or "").splitlines() if line.strip()]


def parse_onec_message(raw: str) -> OnecParsedRoute:
    """
    Parse 1C text format used in Telegram bot handler.
    The goal is compatibility, not strict validation.
    """
    lines = _clean_lines(raw)
    route_id = ""
    driver_fio = ""
    number_auto = ""
    trailer_number = ""
    temperature = ""
    dispatcher_contacts = ""
    registration_number = ""

    points: list[OnecPoint] = []
    points_start_idx: int | None = None

    # Header scan
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
            elif "номер тс" in key_lower:
                number_auto = value
            elif "номер прицепа" in key_lower:
                trailer_number = (value or "").strip().upper()
            elif "температура" in key_lower:
                temperature = value
            elif "контакты" in key_lower or "диспетчер" in key_lower:
                dispatcher_contacts = value or line
        else:
            if not route_id and line:
                route_id = line

    # Points scan
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
                points.append(OnecPoint(type_point=type_point, date_point=date_time, place_point=place))

            i += 1

    return OnecParsedRoute(
        route_id=route_id.strip(),
        driver_fio=driver_fio.strip(),
        number_auto=number_auto.strip(),
        trailer_number=trailer_number.strip(),
        temperature=temperature.strip(),
        dispatcher_contacts=dispatcher_contacts.strip(),
        registration_number=registration_number.strip(),
        points=points,
    )

