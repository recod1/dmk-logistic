# PWA API: создание расчёта ЗП (structured) — поля и соответствие 1С

**Базовый URL:** `https://drive.dmk.msk.ru/api`  
**Метод:** `POST /v1/salary/structured`  
**Аутентификация:** `Authorization: Bearer <JWT>` (роли: бухгалтер, админ, супер-админ)

Альтернатива без отдельных полей: `POST /v1/salary` с полем `salary_line` (37 значений через пробел).

Интеграция без JWT: `POST /v1/salary/integration/structured`, заголовок `X-Salary-Api-Key`.

---

## Водитель (указать одно)

| Параметр API PWA | Тип | Описание | Аналог в 1С / legacy |
|------------------|-----|----------|----------------------|
| `driver_fio` | str | ФИО водителя (точное или единственное совпадение в БД) | `driver_name` в `POST /api/salary` |
| `driver_user_id` | int | ID пользователя-водителя в системе | — |
| `driver_login` | str | Логин водителя | — |

Приоритет: `driver_user_id` → `driver_login` → `driver_fio`.

---

## Форматы параметров и их соответствие полям 1С

Имена в JSON — **как в PWA API** (колонка «Поле 1С / legacy» — для выгрузки из 1С в старом API `POST /api/salary`).

```
driver_fio: str — ФИО водителя
```

```
date_salary: str — Дата расчёта (дд.мм.гггг)          | 1С: date_salary
type_route: str — г / мг / рд / пр / смг / пд         | 1С: type_route
sum_status: float — Сумма статус                      | 1С: sum_status
sum_daily: float — Сумма суточных                     | 1С: sum_sut
load_2_trips: float — Загр. 2 рейса                   | 1С: zagr_2_reysa
calc_shuttle: float — Расчёт шаттл                    | 1С: raschet_shuttle
sum_load_unload: float — Сумма загрузка/выгрузка      | 1С: sum_zagr_vygr
sum_curtain: float — Сумма штора                      | 1С: sum_shtora
sum_return: float — Сумма возврат                     | 1С: sum_vozvrat
sum_add_shuttle: float — Сумма доп. шаттл             | 1С: sum_dop_shuttle
sum_add_point: float — Сумма доп. точка               | 1С: sum_dop_tochka
sum_gas_station: float — Сумма АЗС                      | 1С: sum_azs
pallets_hyper: int — Поддоны гипер ТС                   | 1С: poddon_hyper_ts
pallets_metro: int — Поддоны Метро                      | 1С: poddon_metro
pallets_ashan: int — Поддоны Ашан                       | 1С: poddon_ashan
rate_3km: float — 3 р/км                               | 1С: n3r_km
rate_3_5km: float — 3,5 р/км                           | 1С: n3p5r_km
rate_5km: float — 5 р/км                               | 1С: n5r_km
rate_10km: float — 10 р/км                              | 1С: n10r_km
rate_12km: float — 12 р/км                              | 1С: n12r_km
rate_12_5km: float — 12,5 р/км                          | 1С: n12p5r_km
mileage: float — Пробег (в БД сохраняется целым)        | 1С: probeg
sum_cell_compensation: float — Компенсация сот. связи   | 1С: sum_komp_sot_svyazi
experience: int — Стаж                                   | 1С: stazh
percent_10: float — 10%                                 | 1С: n10percent
sum_bonus: float — Сумма премии                         | 1С: sum_premii
withhold: float — Удержать                              | 1С: uderzhat
compensation: float — Возмещение                        | 1С: vozmeshenie
dr: float — ДР                                          | 1С: dr
sum_without_daily_dr_bonus_exp: float — Сумма без сут., ДР, премии, стажа | 1С: sum_bez_sut_dr_prem_stazha
sum_without_daily_dr_bonus: float — Сумма без сут., ДР, премии            | 1С: sum_bez_sut_dr_prem
total: float — Итого                                    | 1С: itogo
load_address: str — Адрес загрузки                      | 1С: adres_zagruzki
unload_address: str — Адрес выгрузки                    | 1С: adres_vygruzki
transport: str — Транспорт                              | 1С: transport
trailer_number: str — Номер прицепа                    | 1С: nomer_pricepa
route_number: str — № рейса                             | 1С: no_reysa
```

Обязательны: **водитель** (`driver_fio` / `driver_user_id` / `driver_login`) и `date_salary`. Остальные поля необязательны (по умолчанию `0` или `""`).

---

## Пример JSON для 1С → PWA

```json
{
  "driver_fio": "Иванов Иван Иванович",
  "date_salary": "15.01.2026",
  "type_route": "г",
  "sum_status": 50000,
  "sum_daily": 0,
  "load_2_trips": 0,
  "calc_shuttle": 1000,
  "sum_load_unload": 20,
  "sum_curtain": 0,
  "sum_return": 0,
  "sum_add_shuttle": 0,
  "sum_add_point": 0,
  "sum_gas_station": 0,
  "pallets_hyper": 0,
  "pallets_metro": 0,
  "pallets_ashan": 0,
  "rate_3km": 0,
  "rate_3_5km": 0,
  "rate_5km": 0,
  "rate_10km": 0,
  "rate_12km": 0,
  "rate_12_5km": 0,
  "mileage": 150,
  "sum_cell_compensation": 0,
  "experience": 5,
  "percent_10": 0,
  "sum_bonus": 0,
  "withhold": 0,
  "compensation": 0,
  "dr": 0,
  "sum_without_daily_dr_bonus_exp": 0,
  "sum_without_daily_dr_bonus": 0,
  "total": 51000.0,
  "load_address": "Склад ул. Ленина, 1",
  "unload_address": "Магазин ул. Мира, 10",
  "transport": "А123ВС456",
  "trailer_number": "ОО 123",
  "route_number": "00ДМ-000701"
}
```

См. также: [API_PWA.md](./API_PWA.md).
