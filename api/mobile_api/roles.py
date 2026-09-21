from __future__ import annotations

from enum import StrEnum


class RoleCode(StrEnum):
    DRIVER = "driver"
    LOGISTIC = "logistic"
    ACCOUNTANT = "accountant"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


ROLE_LABELS_RU: dict[RoleCode, str] = {
    RoleCode.DRIVER: "Водитель",
    RoleCode.LOGISTIC: "Логист",
    RoleCode.ACCOUNTANT: "Бухгалтер",
    RoleCode.ADMIN: "Администратор",
    RoleCode.SUPERADMIN: "Супер-админ",
}

ADMIN_ACCESS_ROLES: set[RoleCode] = {RoleCode.ADMIN, RoleCode.SUPERADMIN}
ROUTE_MANAGER_ROLES: set[RoleCode] = {
    RoleCode.ADMIN,
    RoleCode.SUPERADMIN,
    RoleCode.LOGISTIC,
    RoleCode.ACCOUNTANT,
}


def normalize_role_code(value: str) -> RoleCode:
    text = (value or "").strip().lower()
    aliases = {
        "водитель": RoleCode.DRIVER,
        "логист": RoleCode.LOGISTIC,
        "бухгалтер": RoleCode.ACCOUNTANT,
        "администратор": RoleCode.ADMIN,
        "супер-админ": RoleCode.SUPERADMIN,
        "super-admin": RoleCode.SUPERADMIN,
    }
    if text in aliases:
        return aliases[text]
    try:
        return RoleCode(text)
    except ValueError as exc:
        allowed = ", ".join([role.value for role in RoleCode])
        raise ValueError(f"Invalid role '{value}'. Allowed: {allowed}") from exc


def role_label_ru(role_code: str) -> str:
    try:
        return ROLE_LABELS_RU[normalize_role_code(role_code)]
    except Exception:
        return role_code

