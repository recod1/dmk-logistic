# api/api_server.py - API для добавления расчётов ЗП и создания рейсов

import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, List
from database.repositories.user_repository import UserRepository
from database.repositories.salary_repository import SalaryRepository
from database.repositories.route_repository import RouteRepository
from config.settings import UserRole
from services.notification_service import NotificationService
from mobile_api.router import router as mobile_router
from mobile_api.admin_router import router as admin_users_router
from mobile_api.admin_routes_router import router as admin_mobile_routes_router
from mobile_api.notifications_router import router as notifications_router
from mobile_api.point_documents_router import router as point_documents_router
from mobile_api.chat_router import router as chat_router
from mobile_api.bootstrap import ensure_demo_user
from mobile_api.db import SessionLocal

app = FastAPI(
    title="DMK API Server",
    description="API для интеграции с базой данных бота DMK",
    version="1.0.0"
)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_KEY")


@app.on_event("startup")
def bootstrap_mobile_user():
    """Опционально создаёт демо-пользователя для нового mobile-стека."""
    try:
        with SessionLocal() as db:
            ensure_demo_user(db)
    except Exception as exc:
        # Не прерываем запуск текущего бота/старого API при проблемах с Postgres.
        logger.warning("Mobile bootstrap skipped: %s", exc)


@app.get("/")
async def root():
    """Редирект на админ-панель рейсов."""
    return RedirectResponse(url="/admin/routes", status_code=302)


def verify_api_key(x_api_key: str = Header(None)):
    if not API_KEY:
        return x_api_key
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_api_key


class SalaryCreate(BaseModel):
    driver_name: str
    date_salary: str
    type_route: str
    sum_status: float
    sum_sut: float
    zagr_2_reysa: float
    raschet_shuttle: float
    sum_zagr_vygr: float
    sum_shtora: float
    sum_vozvrat: float
    sum_dop_shuttle: float
    sum_dop_tochka: float
    sum_azs: float
    poddon_hyper_ts: int
    poddon_metro: int
    poddon_ashan: int
    n3r_km: float
    n3p5r_km: float
    n5r_km: float
    n10r_km: float
    n12r_km: float
    n12p5r_km: float
    probeg: float  # Принимает int и float (например, 150 или 150.5)
    sum_komp_sot_svyazi: float
    stazh: float
    n10percent: float
    sum_premii: float
    uderzhat: float
    vozmeshenie: float
    dr: float
    sum_bez_sut_dr_prem_stazha: float
    sum_bez_sut_dr_prem: float
    itogo: float
    adres_zagruzki: str
    adres_vygruzki: str
    transport: str
    nomer_pricepa: str
    no_reysa: str
    status_driver: Optional[str] = " "
    comment_driver: Optional[str] = " "


user_repo = UserRepository()
salary_repo = SalaryRepository()
route_repo = RouteRepository()


class RoutePointCreate(BaseModel):
    """Точка маршрута (загрузка/выгрузка)."""
    type_point: str  # "loading" или "unloading"
    place_point: str
    date_point: str  # формат дд.мм.гггг


class RouteCreate(BaseModel):
    """Создание рейса. Обязательны: route_id и водитель (driver_name или driver_tg_id). Остальные поля опциональны."""
    route_id: str
    driver_name: Optional[str] = None
    driver_tg_id: Optional[int] = None
    number_auto: Optional[str] = ""
    temperature: Optional[str] = ""
    dispatcher_contacts: Optional[str] = ""
    registration_number: Optional[str] = ""
    trailer_number: Optional[str] = ""
    points: Optional[List[RoutePointCreate]] = None


@app.post("/api/route", dependencies=[Depends(verify_api_key)])
async def create_route(route_data: RouteCreate):
    """Создать рейс. Водитель задаётся driver_name (ФИО) или driver_tg_id (Telegram ID)."""
    if route_repo.route_id_exists(route_data.route_id):
        raise HTTPException(status_code=409, detail=f"Route with id '{route_data.route_id}' already exists")
    tg_id = None
    if route_data.driver_tg_id is not None:
        user = user_repo.get_by_tg_id(route_data.driver_tg_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"Driver with tg_id {route_data.driver_tg_id} not found")
        tg_id = int(user.tg_id)
    elif route_data.driver_name and route_data.driver_name.strip():
        user = user_repo.get_by_name(route_data.driver_name.strip())
        if not user:
            raise HTTPException(status_code=404, detail=f"Driver with name '{route_data.driver_name}' not found")
        if user.role != UserRole.DRIVER:
            raise HTTPException(status_code=400, detail="User must be a driver")
        tg_id = int(user.tg_id)
    else:
        raise HTTPException(status_code=400, detail="Provide driver_name or driver_tg_id")
    route = route_repo.create(
        route_id=route_data.route_id,
        tg_id=tg_id,
        number_auto=(route_data.number_auto or "").strip(),
        temperature=(route_data.temperature or "").strip(),
        dispatcher_contacts=(route_data.dispatcher_contacts or "").strip(),
        registration_number=(route_data.registration_number or "").strip(),
        trailer_number=(route_data.trailer_number or "").strip().upper(),
    )
    if not route:
        raise HTTPException(status_code=500, detail="Failed to create route")
    point_ids = []
    if route_data.points:
        for p in route_data.points:
            type_point = (p.type_point or "").strip().lower()
            if type_point not in ("loading", "unloading"):
                type_point = "loading"
            last_id = route_repo.get_last_point_id()
            point_id = last_id + 1 if last_id else 1
            route_repo.create_point(
                point_id=point_id,
                route_id=route_data.route_id,
                type_point=type_point,
                place_point=(p.place_point or "").strip(),
                date_point=(p.date_point or "").strip(),
            )
            point_ids.append(str(point_id))
        if point_ids:
            route_repo.add_point_to_route(route_data.route_id, ",".join(point_ids))
    route = route_repo.get_by_id_str(route_data.route_id)
    if route and route.tg_id:
        try:
            notification = NotificationService(user_repo)
            await notification.notify_driver_new_route(route, route_repo)
        except Exception as e:
            pass
    return {"id": route_data.route_id, "message": "Route created successfully", "points_count": len(point_ids) if route_data.points else 0}


@app.post("/api/salary", dependencies=[Depends(verify_api_key)])
async def create_salary(salary_data: SalaryCreate):
    user = user_repo.get_by_name(salary_data.driver_name)
    if not user:
        raise HTTPException(status_code=404, detail=f"Driver with name '{salary_data.driver_name}' not found")
    if user.role != "driver":
        raise HTTPException(status_code=400, detail="User must be a driver")

    id_driver = user.tg_id

    new_id = salary_repo.create_salary(
        id_driver,
        salary_data.date_salary,
        salary_data.type_route,
        salary_data.sum_status,
        salary_data.sum_sut,
        salary_data.zagr_2_reysa,
        salary_data.raschet_shuttle,
        salary_data.sum_zagr_vygr,
        salary_data.sum_shtora,
        salary_data.sum_vozvrat,
        salary_data.sum_dop_shuttle,
        salary_data.sum_dop_tochka,
        salary_data.sum_azs,
        salary_data.poddon_hyper_ts,
        salary_data.poddon_metro,
        salary_data.poddon_ashan,
        salary_data.n3r_km,
        salary_data.n3p5r_km,
        salary_data.n5r_km,
        salary_data.n10r_km,
        salary_data.n12r_km,
        salary_data.n12p5r_km,
        salary_data.probeg,
        salary_data.sum_komp_sot_svyazi,
        int(salary_data.stazh),
        salary_data.n10percent,
        salary_data.sum_premii,
        salary_data.uderzhat,
        salary_data.vozmeshenie,
        salary_data.dr,
        salary_data.sum_bez_sut_dr_prem_stazha,
        salary_data.sum_bez_sut_dr_prem,
        salary_data.itogo,
        salary_data.adres_zagruzki,
        salary_data.adres_vygruzki,
        salary_data.transport,
        salary_data.nomer_pricepa,
        salary_data.no_reysa
    )

    if salary_data.status_driver and salary_data.status_driver.strip() and salary_data.status_driver != " ":
        salary_repo.update_status(new_id, salary_data.status_driver)
    if salary_data.comment_driver and salary_data.comment_driver.strip() and salary_data.comment_driver != " ":
        salary_repo.update_comment(new_id, salary_data.comment_driver)

    return {"id": new_id, "message": "Salary record created successfully"}


# Админ-панель рейсов (веб-интерфейс)
from api.admin_routes_web import router as admin_routes_router
app.include_router(admin_routes_router)
app.include_router(mobile_router)
app.include_router(admin_users_router)
app.include_router(admin_mobile_routes_router)
app.include_router(notifications_router)
app.include_router(point_documents_router)
app.include_router(chat_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
