"""Хелперы для форматирования сообщений Telegram (копируемые по клику поля)."""
import html
from urllib.parse import quote

# Короткие названия часовых поясов для отображения вместо (Виалон)
TZ_SHORT_NAMES = {
    "Europe/Moscow": "Мск",
    "Europe/Kaliningrad": "Кал",
    "Europe/Samara": "Сам",
    "Asia/Yekaterinburg": "Екб",
    "Asia/Omsk": "Омск",
    "Asia/Novosibirsk": "Нск",
    "Asia/Krasnoyarsk": "Крс",
    "Asia/Irkutsk": "Ирк",
    "Asia/Yakutsk": "Якт",
    "Asia/Vladivostok": "Влд",
    "Asia/Kamchatka": "Кам",
}


def timezone_to_short(tz_str: str) -> str:
    """Преобразует timezone (например Europe/Moscow) в короткое название (Мск)."""
    if not tz_str or not str(tz_str).strip():
        return "Мск"
    tz = str(tz_str).strip()
    return TZ_SHORT_NAMES.get(tz, tz.split("/")[-1][:3] if "/" in tz else tz[:3])


def copy_link_fio(name: str) -> str:
    """Возвращает HTML-фрагмент для копируемого по клику ФИО (использовать с parse_mode='HTML')."""
    safe = (name or "").strip() or "—"
    return f'<a href="tg://copy?text={quote(safe)}"><code>{html.escape(safe)}</code></a>'


def copy_link_text(text: str) -> str:
    """Возвращает HTML-фрагмент для копируемого по клику текста (номер ТС, прицепа и т.д.)."""
    safe = (text or "").strip() or "—"
    return f'<a href="tg://copy?text={quote(safe)}"><code>{html.escape(safe)}</code></a>'


def format_point_time_display(time_str: str) -> str:
    """Для отображения времени точки. Суффиксы:
    (Мск) — московское, (ВВ) — вручную, (🛰️ Екб) — из Wialon с часовым поясом.
    Старый формат (Виалон) заменяется на (🛰️ Мск) для совместимости."""
    if not time_str or not str(time_str).strip():
        return ""
    s = str(time_str).strip()
    if " (Виалон)" in s:
        s = s.replace(" (Виалон)", " (🛰️ Мск)")
    if " (ВВ)" in s or " (Введено вручную)" in s or " (Мск)" in s or " (🛰️ " in s:
        return s
    return s + " (Мск)"
