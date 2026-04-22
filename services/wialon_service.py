# services/wialon_service.py — получение координат, одометра и локального времени по номеру ТС через Wialon API

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

# Флаг доступности Wialon (если токен не задан — не пытаемся подключаться)
WIALON_ENABLED = bool(settings.WIALON_TOKEN and settings.WIALON_TOKEN.strip())

# Флаги для Wialon: 1 (базовые) + 256 (доп.свойства) + 1024 (позиция) + 2048 (водитель) + 4096 (датчики) + 8192 (счетчики) + 16384 (свойства датчиков)
WIALON_FLAGS_FULL = 1 | 256 | 1024 | 2048 | 4096 | 8192 | 16384


def _format_odometer(unit: dict) -> Optional[str]:
    """Извлекает значение одометра из unit (cnm или prp)."""
    try:
        if "cnm" in unit:
            mileage = unit["cnm"]
            if isinstance(mileage, (int, float)):
                return f"{int(round(mileage))} км"
            return str(mileage)
        prp = unit.get("prp") or {}
        if isinstance(prp, dict):
            for key in ("odometer", "mileage"):
                if key in prp:
                    val = prp[key]
                    if isinstance(val, (int, float)):
                        return f"{int(round(val))} км"
                    return f"{val} км"
    except Exception as e:
        logger.warning("odometer extract: %s", e)
    return None


def _get_timezone_from_coords(lat: float, lng: float) -> Optional[str]:
    """Определяет часовой пояс по координатам."""
    if lat == 0 and lng == 0:
        return None
    try:
        from timezonefinder import TimezoneFinder
        tf = TimezoneFinder()
        tz_str = tf.timezone_at(lng=lng, lat=lat)
        return tz_str
    except Exception as e:
        logger.warning("timezonefinder: %s", e)
        return None


def _get_local_time_str(timezone_str: str) -> str:
    """Возвращает текущее локальное время в указанном часовом поясе (формат дд.мм.гггг чч:мм)."""
    try:
        import pytz
        tz = pytz.timezone(timezone_str)
        return datetime.now(tz).strftime("%d.%m.%Y %H:%M")
    except Exception as e:
        logger.warning("pytz timezone %s: %s", timezone_str, e)
        return None


def get_vehicle_location_data(vehicle_number: str):
    """
    Получает полные данные ТС по номеру через Wialon.
    :param vehicle_number: номер ТС (number_auto из рейса)
    :return: dict с ключами time_str, timezone_str, lat, lng, odometer или None при ошибке
    """
    if not WIALON_ENABLED:
        return None

    number = (vehicle_number or "").strip()
    if not number:
        return None

    base_url = (settings.WIALON_BASE_URL or "").rstrip("/")
    if not base_url:
        return None

    try:
        login_params = {
            "svc": "token/login",
            "params": json.dumps({"token": settings.WIALON_TOKEN}),
        }
        login_resp = requests.get(f"{base_url}/wialon/ajax.html", params=login_params, timeout=10)
        login_data = login_resp.json()
        sid = login_data.get("eid")
        if not sid:
            logger.warning("Wialon login failed: %s", login_data)
            return None

        search_params = {
            "svc": "core/search_items",
            "params": json.dumps({
                "spec": {
                    "itemsType": "avl_unit",
                    "propName": "sys_name",
                    "propValueMask": f"*{number}*",
                    "sortType": "sys_name",
                },
                "force": 1,
                "flags": WIALON_FLAGS_FULL,
                "from": 0,
                "to": 10,
            }),
            "sid": sid,
        }
        search_resp = requests.get(f"{base_url}/wialon/ajax.html", params=search_params, timeout=10)
        search_data = search_resp.json()
        if "error" in search_data:
            logger.warning("Wialon search error: %s", search_data["error"])
            return None

        items = search_data.get("items") or []
        if not items:
            # Доп. попытка по отображаемому имени объекта (как в части аккаунтов Wialon).
            search_params_nm = {
                **search_params,
                "params": json.dumps({
                    "spec": {
                        "itemsType": "avl_unit",
                        "propName": "nm",
                        "propValueMask": f"*{number}*",
                        "sortType": "nm",
                    },
                    "force": 1,
                    "flags": WIALON_FLAGS_FULL,
                    "from": 0,
                    "to": 10,
                }),
            }
            search_resp_nm = requests.get(f"{base_url}/wialon/ajax.html", params=search_params_nm, timeout=10)
            search_data = search_resp_nm.json()
            if "error" in search_data:
                logger.warning("Wialon search (nm) error: %s", search_data["error"])
                return None
            items = search_data.get("items") or []
        if not items:
            logger.info("Wialon: vehicle not found for number=%s", number)
            return None

        unit = items[0]
        pos = unit.get("pos")
        if not pos or not isinstance(pos, dict):
            logger.info("Wialon: no position for vehicle %s", unit.get("nm", number))
            return None

        lat = pos.get("y", 0)
        lng = pos.get("x", 0)
        if lat == 0 and lng == 0:
            logger.info("Wialon: zero coords for vehicle %s", unit.get("nm", number))
            return None

        odometer = _format_odometer(unit)
        # Координаты и одометр нужны даже если timezonefinder не смог определить пояс (океан и т.п.).
        tz_str = _get_timezone_from_coords(lat, lng) or "UTC"
        time_str = _get_local_time_str(tz_str)
        if not time_str:
            time_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")

        return {
            "time_str": time_str,
            "timezone_str": tz_str,
            "lat": lat,
            "lng": lng,
            "odometer": odometer,
        }
    except requests.RequestException as e:
        logger.warning("Wialon request error: %s", e)
        return None
    except Exception as e:
        logger.exception("Wialon: %s", e)
        return None


def get_location_and_local_time(vehicle_number: str) -> Optional[Tuple[str, str]]:
    """
    Получает координаты ТС по номеру через Wialon и возвращает локальное время в месте нахождения машины.
    :param vehicle_number: номер ТС (number_auto из рейса)
    :return: (time_str, timezone_str) или None при ошибке
    """
    data = get_vehicle_location_data(vehicle_number)
    if not data:
        return None
    return (data["time_str"], data["timezone_str"])
