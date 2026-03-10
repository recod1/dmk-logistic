# api/admin_routes_web.py — веб-интерфейс администрирования рейсов

import os
import re
import calendar
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from database.repositories.route_repository import RouteRepository
from database.repositories.user_repository import UserRepository
from config.settings import UserRole
from services.notification_service import NotificationService

from .web_route_helpers import (
    build_route_detail_data,
    get_driver_name,
    STATUS_TEXTS,
)

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

API_KEY = os.getenv("API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")


def _check_admin(request: Request) -> bool:
    """Проверка доступа: API_KEY в заголовке/query или пароль в сессии."""
    if not API_KEY and not ADMIN_PASSWORD:
        return True
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if api_key and api_key == API_KEY:
        return True
    session = request.cookies.get("admin_session")
    if session and session == (ADMIN_PASSWORD or API_KEY):
        return True
    return False


async def require_admin(request: Request):
    if request.url.path == "/admin/login":
        return True
    if not _check_admin(request):
        if ADMIN_PASSWORD or API_KEY:
            return RedirectResponse(url="/admin/login", status_code=302)
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True


# --- Репозитории (инициализация при первом запросе)
def _get_repos():
    return UserRepository(), RouteRepository()


# --- Парсинг точек из текста
def _parse_points_text(text: str) -> list:
    """Парсит точки из текста. Формат: type|date|place. type: loading/unloading."""
    result = []
    for line in (text or "").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|", 2)]
        if len(parts) < 3:
            continue
        t, d, p = parts[0].lower(), parts[1], parts[2]
        if t not in ("loading", "unloading"):
            t = "loading"
        result.append({"type_point": t, "date_point": d, "place_point": p})
    return result


def _validate_number_auto(text: str) -> bool:
    t = (text or "").strip().upper()
    if not t:
        return True
    return bool(
        re.match(r"^[А-ЯA-Z]\d{3}[А-ЯA-Z]{2}\d{2,3}$", t)
        or re.match(r"^[А-ЯA-Z]{2}\d{6}$", t)
    )


# --- Страницы
@router.get("", response_class=RedirectResponse)
async def admin_root():
    """Редирект с /admin на /admin/routes."""
    return RedirectResponse(url="/admin/routes", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if not ADMIN_PASSWORD and not API_KEY:
        return RedirectResponse(url="/admin/routes", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login_post(request: Request):
    form = await request.form()
    password = (form.get("password") or "").strip()
    expected = ADMIN_PASSWORD or API_KEY
    if not expected or password != expected:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Неверный пароль"},
        )
    response = RedirectResponse(url="/admin/routes", status_code=302)
    response.set_cookie("admin_session", expected, max_age=86400 * 7)  # 7 дней
    return response


@router.get("/routes", response_class=HTMLResponse)
async def routes_index(request: Request, _=Depends(require_admin)):
    return templates.TemplateResponse("routes_index.html", {"request": request})


@router.get("/routes/search", response_class=HTMLResponse)
async def route_search(request: Request, _=Depends(require_admin)):
    user_repo, route_repo = _get_repos()
    route_id = request.query_params.get("route_id", "").strip()
    driver = request.query_params.get("driver", "").strip()
    number_auto = request.query_params.get("number_auto", "").strip().upper()
    status = request.query_params.get("status", "").strip()

    routes = []
    req_ctx = {"route_id": route_id, "driver": driver, "number_auto": number_auto, "status": status}
    ctx = {
        "request": request,
        "driver_names": {},
        "status_texts": STATUS_TEXTS,
    }

    if route_id:
        r = route_repo.get_by_id_str(route_id)
        if r:
            routes = [r]
    elif driver and len(driver) >= 2:
        users = user_repo.search_drivers_by_name_part(driver, limit=15)
        for u in users:
            if status:
                rs = route_repo.get_routes_by_driver(int(u.tg_id), status)
            else:
                rs = route_repo.get_routes_by_driver(int(u.tg_id))
            routes.extend(rs)
        routes = list({r.id: r for r in routes}.values())
    elif number_auto:
        if status:
            routes = route_repo.get_routes_by_number_auto(number_auto, status)
        else:
            routes = route_repo.get_routes_by_number_auto(number_auto)
    elif not route_id and not driver and not number_auto:
        pass
    else:
        routes = route_repo.get_all()
        if status:
            routes = [r for r in routes if r.status == status]

    for r in routes:
        ctx["driver_names"][r.tg_id] = get_driver_name(user_repo, r.tg_id)

    ctx["routes"] = routes
    ctx["req_ctx"] = req_ctx
    return templates.TemplateResponse("route_search.html", ctx)


@router.get("/routes/filter", response_class=HTMLResponse)
async def route_filter(request: Request, _=Depends(require_admin)):
    user_repo, route_repo = _get_repos()
    status = request.query_params.get("status", "").strip()
    driver = request.query_params.get("driver", "").strip()
    route_id = request.query_params.get("route_id", "").strip()
    number_auto = request.query_params.get("number_auto", "").strip().upper()

    status_text = STATUS_TEXTS.get(status, status)
    routes = []

    if status:
        routes = route_repo.get_routes_by_status(status)
        if driver and len(driver) >= 2:
            users = user_repo.search_drivers_by_name_part(driver, limit=15)
            tg_ids = {u.tg_id for u in users}
            routes = [r for r in routes if r.tg_id in tg_ids]
        if route_id:
            routes = [r for r in routes if r.id == route_id]
        if number_auto:
            routes = [r for r in routes if (r.number_auto or "").strip().upper() == number_auto]

    driver_names = {r.tg_id: get_driver_name(user_repo, r.tg_id) for r in routes}

    req_ctx = {"driver": driver, "route_id": route_id, "number_auto": number_auto}
    return templates.TemplateResponse(
        "route_filter.html",
        {
            "request": request,
            "status": status,
            "status_text": status_text,
            "routes": routes,
            "driver_names": driver_names,
            "status_texts": STATUS_TEXTS,
            "req_ctx": req_ctx,
        },
    )


@router.get("/routes/completed", response_class=HTMLResponse)
async def route_completed(request: Request, _=Depends(require_admin)):
    user_repo, route_repo = _get_repos()
    today = datetime.now()
    date_from = request.query_params.get("date_from", "").strip()
    date_to = request.query_params.get("date_to", "").strip()
    today_param = request.query_params.get("today")
    month_param = request.query_params.get("month")

    if today_param:
        d = today.strftime("%d.%m.%Y")
        date_from = date_to = d
        period_info = d
    elif month_param:
        start = today.replace(day=1)
        date_from = start.strftime("%d.%m.%Y")
        date_to = today.strftime("%d.%m.%Y")
        period_info = f"с {date_from} по {date_to}"
    elif date_from and date_to:
        period_info = f"с {date_from} по {date_to}"
    else:
        period_info = "—"
        date_from = date_to = today.strftime("%d.%m.%Y")

    routes = route_repo.get_routes_success_in_period(date_from, date_to) if date_from and date_to else []
    driver_names = {r.tg_id: get_driver_name(user_repo, r.tg_id) for r in routes}

    req_ctx = {"date_from": date_from, "date_to": date_to}
    return templates.TemplateResponse(
        "route_completed.html",
        {
            "request": request,
            "routes": routes,
            "driver_names": driver_names,
            "period_info": period_info,
            "req_ctx": req_ctx,
        },
    )


@router.get("/routes/{route_id}", response_class=HTMLResponse)
async def route_detail(request: Request, route_id: str, _=Depends(require_admin)):
    user_repo, route_repo = _get_repos()
    route = route_repo.get_by_id_str(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Рейс не найден")
    detail_data = build_route_detail_data(route, route_repo, user_repo)
    return templates.TemplateResponse(
        "route_detail.html",
        {
            "request": request,
            "route": route,
            "detail": detail_data,
        },
    )


@router.get("/routes/{route_id}/delete", response_class=HTMLResponse)
async def route_delete_form(request: Request, route_id: str, _=Depends(require_admin)):
    _, route_repo = _get_repos()
    route = route_repo.get_by_id_str(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Рейс не найден")
    return templates.TemplateResponse(
        "route_delete.html",
        {"request": request, "route": route, "deleted": False},
    )


@router.post("/routes/{route_id}/delete", response_class=HTMLResponse)
async def route_delete_post(request: Request, route_id: str, _=Depends(require_admin)):
    _, route_repo = _get_repos()
    route = route_repo.get_by_id_str(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Рейс не найден")
    ok = route_repo.delete_route_with_points(route_id)
    return templates.TemplateResponse(
        "route_delete.html",
        {
            "request": request,
            "route": route,
            "deleted": True,
            "message": "Рейс удалён" if ok else "Ошибка удаления",
            "success": ok,
        },
    )


@router.get("/routes/{route_id}/cancel", response_class=HTMLResponse)
async def route_cancel_form(request: Request, route_id: str, _=Depends(require_admin)):
    _, route_repo = _get_repos()
    route = route_repo.get_by_id_str(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Рейс не найден")
    return templates.TemplateResponse(
        "route_cancel.html",
        {"request": request, "route": route, "cancelled": False},
    )


@router.post("/routes/{route_id}/cancel", response_class=HTMLResponse)
async def route_cancel_post(request: Request, route_id: str, _=Depends(require_admin)):
    user_repo, route_repo = _get_repos()
    route = route_repo.get_by_id_str(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Рейс не найден")
    route_repo.update_status_route(route_id, "cancelled")
    try:
        notification = NotificationService(user_repo)
        await notification.notify_route_cancelled(route_id, int(route.tg_id))
    except Exception:
        pass
    return templates.TemplateResponse(
        "route_cancel.html",
        {
            "request": request,
            "route": route,
            "cancelled": True,
            "message": "Рейс отменён",
            "success": True,
        },
    )


@router.get("/routes/{route_id}/reassign", response_class=HTMLResponse)
async def route_reassign_form(request: Request, route_id: str, _=Depends(require_admin)):
    user_repo, route_repo = _get_repos()
    route = route_repo.get_by_id_str(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Рейс не найден")
    drivers = user_repo.get_all_by_role(UserRole.DRIVER)
    drivers = [u for u in drivers if u.tg_id and str(u.tg_id) != "0"]
    return templates.TemplateResponse(
        "route_reassign.html",
        {"request": request, "route": route, "drivers": drivers},
    )


@router.post("/routes/{route_id}/reassign", response_class=HTMLResponse)
async def route_reassign_post(request: Request, route_id: str, _=Depends(require_admin)):
    user_repo, route_repo = _get_repos()
    route = route_repo.get_by_id_str(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Рейс не найден")
    form = await request.form()
    driver_tg_id = form.get("driver_tg_id")
    number_auto = (form.get("number_auto") or "").strip().upper()
    trailer_number = (form.get("trailer_number") or "").strip().upper()

    drivers = user_repo.get_all_by_role(UserRole.DRIVER)
    drivers = [u for u in drivers if u.tg_id and str(u.tg_id) != "0"]

    if not driver_tg_id:
        return templates.TemplateResponse(
            "route_reassign.html",
            {
                "request": request,
                "route": route,
                "drivers": drivers,
                "message": "Выберите водителя",
                "success": False,
            },
        )
    if number_auto and not _validate_number_auto(number_auto):
        return templates.TemplateResponse(
            "route_reassign.html",
            {
                "request": request,
                "route": route,
                "drivers": drivers,
                "message": "Неверный формат номера ТС",
                "success": False,
            },
        )

    try:
        tg_id = int(driver_tg_id)
    except (TypeError, ValueError):
        return templates.TemplateResponse(
            "route_reassign.html",
            {
                "request": request,
                "route": route,
                "drivers": drivers,
                "message": "Неверный водитель",
                "success": False,
            },
        )

    route_repo.reassign_driver(route_id, tg_id)
    if number_auto:
        route_repo.update_route_field(route_id, "number_auto", number_auto)
    if trailer_number is not None:
        route_repo.update_route_field(route_id, "trailer_number", trailer_number)

    return RedirectResponse(url=f"/admin/routes/{route_id}", status_code=302)


@router.get("/routes/{route_id}/edit", response_class=HTMLResponse)
async def route_edit_form(request: Request, route_id: str, _=Depends(require_admin)):
    _, route_repo = _get_repos()
    route = route_repo.get_by_id_str(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Рейс не найден")
    points_ids = [x for x in (route.points or "").split(",") if x.strip() and x.strip() != "0"]
    lines = []
    for pid in points_ids:
        try:
            pt = route_repo.get_point_by_id(int(pid))
            if pt:
                lines.append(f"{pt.type_point}|{pt.date_point}|{pt.place_point}")
        except ValueError:
            continue
    points_text = "\n".join(lines)
    return templates.TemplateResponse(
        "route_edit.html",
        {"request": request, "route": route, "points_text": points_text},
    )


@router.post("/routes/{route_id}/edit", response_class=HTMLResponse)
async def route_edit_post(request: Request, route_id: str, _=Depends(require_admin)):
    user_repo, route_repo = _get_repos()
    route = route_repo.get_by_id_str(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Рейс не найден")
    form = await request.form()
    number_auto = (form.get("number_auto") or "").strip().upper()
    trailer_number = (form.get("trailer_number") or "").strip().upper()
    temperature = (form.get("temperature") or "").strip()
    dispatcher_contacts = (form.get("dispatcher_contacts") or "").strip()
    registration_number = (form.get("registration_number") or "").strip()
    points_text = (form.get("points_text") or "").strip()

    if number_auto and not _validate_number_auto(number_auto):
        points_ids = [x for x in (route.points or "").split(",") if x.strip() and x.strip() != "0"]
        lines = []
        for pid in points_ids:
            try:
                pt = route_repo.get_point_by_id(int(pid))
                if pt:
                    lines.append(f"{pt.type_point}|{pt.date_point}|{pt.place_point}")
            except ValueError:
                continue
        return templates.TemplateResponse(
            "route_edit.html",
            {
                "request": request,
                "route": route,
                "points_text": "\n".join(lines),
                "message": "Неверный формат номера ТС",
                "success": False,
            },
        )

    route_repo.update_route_field(route_id, "number_auto", number_auto)
    route_repo.update_route_field(route_id, "trailer_number", trailer_number)
    route_repo.update_route_field(route_id, "temperature", temperature)
    route_repo.update_route_field(route_id, "dispatcher_contacts", dispatcher_contacts)
    route_repo.update_route_field(route_id, "registration_number", registration_number)

    points_data = _parse_points_text(points_text)
    route_repo.delete_points_by_route(route_id)
    point_ids = []
    for p in points_data:
        last_id = route_repo.get_last_point_id()
        point_id = last_id + 1 if last_id else 1
        route_repo.create_point(
            point_id=point_id,
            route_id=route_id,
            type_point=p["type_point"],
            place_point=p["place_point"],
            date_point=p["date_point"],
        )
        point_ids.append(str(point_id))
    if point_ids:
        route_repo.add_point_to_route(route_id, ",".join(point_ids))
    else:
        route_repo.add_point_to_route(route_id, "0")

    route = route_repo.get_by_id_str(route_id)
    try:
        notification = NotificationService(user_repo)
        await notification.notify_driver_route_changed(route, route_repo)
    except Exception:
        pass

    return RedirectResponse(url=f"/admin/routes/{route_id}", status_code=302)
