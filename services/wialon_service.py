# services/wialon_service.py — получение координат, одометра и локального времени по номеру ТС через Wialon API

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

_WIALON_HTTP_HEADERS = {
    "User-Agent": "dmk-logistic/1.0 (Wialon Remote API)",
    "Accept": "application/json, text/javascript, */*;q=0.1",
}


def vehicle_number_for_wialon(*candidates: str | None) -> str:
    """
    Строка поиска юнита в Wialon: сначала number_auto, затем запасные поля (как в PWA / mobile_api).
    Telegram-бот должен вызывать ту же функцию, чтобы логика совпадала.
    """
    for cand in candidates:
        s = (cand or "").strip()
        if s:
            return s
    return ""


def _safe_url_for_log(response: requests.Response) -> str:
    try:
        p = urlparse(response.url)
        return f"{p.scheme}://{p.netloc}{p.path}"
    except Exception:
        return "(url)"


def _wialon_ajax_url() -> str | None:
    """
    Полный URL для Wialon Remote API (JSON).
    Веб-домен вида https://monitor.* часто отдаёт HTML-приложение на /wialon/ajax.html — тогда нужен WIALON_API_BASE_URL
    с хоста вида https://bXXXX.hosting.wialon.com из админки хостинга.
    """
    api_base = ((settings.WIALON_API_BASE_URL or settings.WIALON_BASE_URL) or "").strip().rstrip("/")
    if not api_base:
        return None
    path = (settings.WIALON_AJAX_PATH or "/wialon/ajax.html").strip()
    if not path.startswith("/"):
        path = "/" + path
    return f"{api_base}{path}"


def _parse_wialon_ajax_json(response: requests.Response, step: str) -> dict | None:
    """Wialon отвечает JSON; пустое тело/HTML даёт JSONDecodeError — логируем фактические данные."""
    safe = _safe_url_for_log(response)
    if response.status_code != 200:
        logger.warning("Wialon %s: HTTP %s %s", step, response.status_code, safe)
    raw = (response.text or "").strip()
    if not raw:
        logger.warning(
            "Wialon %s: пустой ответ (status=%s, %s). Проверьте WIALON_BASE_URL и доступность хоста.",
            step,
            response.status_code,
            safe,
        )
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        snippet = raw[:400].replace("\n", " ").replace("\r", "")
        low = snippet.strip().lower()
        html_hint = ""
        if low.startswith("<!doctype") or low.startswith("<html") or "<html" in low[:80]:
            html_hint = (
                " Ответ — HTML (веб-мониторинг), не Remote API: задайте WIALON_API_BASE_URL на хост API из "
                "кабинета Wialon Hosting (например https://…hosting.wialon.com), не адрес браузерного «Монитор»."
            )
        logger.warning(
            "Wialon %s: не JSON (status=%s, %s): %s; начало ответа: %r%s",
            step,
            response.status_code,
            safe,
            e,
            snippet,
            html_hint,
        )
        return None

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

    ajax_url = _wialon_ajax_url()
    if not ajax_url:
        return None

    try:
        login_params = {
            "svc": "token/login",
            "params": json.dumps({"token": settings.WIALON_TOKEN}),
        }
        login_resp = requests.get(
            ajax_url,
            params=login_params,
            timeout=15,
            headers=_WIALON_HTTP_HEADERS,
        )
        login_data = _parse_wialon_ajax_json(login_resp, "token/login")
        if not login_data:
            return None
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
        search_resp = requests.get(
            ajax_url,
            params=search_params,
            timeout=15,
            headers=_WIALON_HTTP_HEADERS,
        )
        search_data = _parse_wialon_ajax_json(search_resp, "core/search_items")
        if not search_data:
            return None
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
            search_resp_nm = requests.get(
                ajax_url,
                params=search_params_nm,
                timeout=15,
                headers=_WIALON_HTTP_HEADERS,
            )
            search_data = _parse_wialon_ajax_json(search_resp_nm, "core/search_items(nm)")
            if not search_data:
                return None
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
