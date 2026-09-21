# services/wialon_service.py — получение координат, одометра и локального времени по номеру ТС через Wialon API

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

# Стандартный endpoint Remote API Wialon (как в handlers / старой интеграции).
_WIALON_AJAX_SUFFIX = "/wialon/ajax.html"

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


def _wialon_hostname(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _wialon_get(ajax_entry: str, params: dict, step: str) -> requests.Response | None:
    """
    GET с ручной обработкой редиректов (allow_redirects=False).

    Типичный кейс JustGPS/Sputnik: 302 с w1.* на корень https://monitor.* — при автоследовании
    requests теряет query (svc, params) и приходит HTML. Один раз пересобираем URL как
    {scheme}://{хост из Location}{/wialon/ajax.html} и повторяем с теми же params (как при «рабочем» боте).
    Дальше разрешены только редиректы внутри того же hostname (http→https и т.п.).
    """
    current = ajax_entry
    cross_host_ajax_rebuilt = False
    for hop in range(10):
        cur_host = _wialon_hostname(current)
        r = requests.get(
            current,
            params=params,
            timeout=15,
            headers=_WIALON_HTTP_HEADERS,
            allow_redirects=False,
        )
        if r.status_code in (301, 302, 303, 307, 308):
            loc = (r.headers.get("Location") or "").strip()
            if not loc:
                logger.warning("Wialon %s: HTTP %s без Location (%s)", step, r.status_code, _safe_url_for_log(r))
                return None
            nxt = urljoin(r.url, loc)
            h_next = _wialon_hostname(nxt)
            if h_next == cur_host:
                current = nxt
                continue
            # Редирект на другой хост
            if not cross_host_ajax_rebuilt:
                pu = urlparse(nxt)
                current = f"{pu.scheme}://{pu.netloc}{_WIALON_AJAX_SUFFIX}"
                cross_host_ajax_rebuilt = True
                logger.info(
                    "Wialon %s: редирект %s → %s; повтор с теми же svc/params на %s",
                    step,
                    cur_host or current,
                    h_next or nxt,
                    current,
                )
                continue
            logger.warning(
                "Wialon %s: ещё один редирект на другой хост (%s → %s), прекращаем.",
                step,
                cur_host,
                h_next,
            )
            return None
        return r
    logger.warning("Wialon %s: слишком длинная цепочка редиректов с %s", step, ajax_entry)
    return None


def _wialon_ajax_url() -> str | None:
    """Полный URL для Wialon Remote API: только WIALON_BASE_URL + /wialon/ajax.html (как в Telegram-боте)."""
    api_base = (settings.WIALON_BASE_URL or "").strip().rstrip("/")
    if not api_base:
        return None
    return f"{api_base}{_WIALON_AJAX_SUFFIX}"


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
                " Ответ — HTML: часто это следствие редиректа w1.* → monitor.* (см. лог «редирект на другой хост»). "
                "Нужен прямой хост JSON API без такого редиректа."
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

_first_vehicle_lookup_logged = False


def wialon_runtime_diagnostics() -> dict:
    """
    Снимок того, как процесс реально видит Wialon (без токена в ответе).
    Сравните с Portainer: если resolved_wialon_base_url = monitor, а в UI указали justgps — контейнер не получил новый env или не пересобран образ.
    """
    raw_env = os.environ.get("WIALON_BASE_URL")
    return {
        "wialon_enabled": WIALON_ENABLED,
        "token_configured": bool((settings.WIALON_TOKEN or "").strip()),
        "resolved_wialon_base_url": settings.WIALON_BASE_URL,
        "computed_ajax_url": _wialon_ajax_url(),
        "process_env_has_WIALON_BASE_URL": "WIALON_BASE_URL" in os.environ,
        "process_env_WIALON_BASE_URL_raw": raw_env,
        "hint": "При редиректе w1→monitor приложение один раз повторяет token/login на https://{хост из Location}/wialon/ajax.html с теми же svc/params. Если всё равно HTML — второй чужой редирект или сеть/прокси; см. логи Wialon.",
    }


def wialon_probe_token_login() -> dict:
    """Один запрос token/login: хост ответа и тип тела (диагностика HTML vs JSON)."""
    ajax = _wialon_ajax_url()
    if not ajax:
        return {"skipped": True, "reason": "no ajax url"}
    if not WIALON_ENABLED:
        return {"skipped": True, "reason": "no token"}
    try:
        login_params = {
            "svc": "token/login",
            "params": json.dumps({"token": settings.WIALON_TOKEN}),
        }
        r = _wialon_get(ajax, login_params, "probe/token/login")
        if r is None:
            return {
                "error": "wialon_get_failed",
                "message": "Нет ответа после редиректов (второй редирект на другой хост или обрыв цепочки); см. логи Wialon.",
            }
        text = (r.text or "").strip()
        prefix = text[:240].replace("\n", " ")
        return {
            "http_status": r.status_code,
            "response_url_host": urlparse(r.url).netloc,
            "response_url_path": urlparse(r.url).path,
            "content_type": r.headers.get("Content-Type", ""),
            "body_starts_with_brace": text.startswith("{"),
            "body_prefix": prefix,
        }
    except requests.RequestException as e:
        return {"error": str(e)}


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

    global _first_vehicle_lookup_logged
    if not _first_vehicle_lookup_logged:
        _first_vehicle_lookup_logged = True
        logger.info(
            "Wialon: первый запрос get_vehicle_location_data, ajax_url=%s (см. также GET /v1/mobile/debug/wialon)",
            _wialon_ajax_url(),
        )

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
        login_resp = _wialon_get(ajax_url, login_params, "token/login")
        if login_resp is None:
            return None
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
        search_resp = _wialon_get(ajax_url, search_params, "core/search_items")
        if search_resp is None:
            return None
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
            search_resp_nm = _wialon_get(ajax_url, search_params_nm, "core/search_items(nm)")
            if search_resp_nm is None:
                return None
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
