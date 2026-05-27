# API PWA: JWT, создание рейса и зарплатного расчёта

Документ описывает HTTP API, которым пользуется веб-PWA (`web/`): те же эндпоинты, что вызываются из интерфейса логиста/бухгалтера/администратора.

Для интеграции **без JWT** (только ключ `X-API-Key`) см. отдельно:

- [API_ROUTE.md](./API_ROUTE.md) — создание рейса в legacy-стеке;
- `POST /api/salary` в `api/api_server.py` — расчёт ЗП по отдельным JSON-полям (не строка из 37 значений).

---

## Базовый URL

| Окружение | URL API |
|-----------|---------|
| PWA за nginx (docker-compose) | `https://<хост>/api` |
| API напрямую | `http://localhost:8000` (без префикса `/api` в путях) |

В PWA переменная `VITE_API_BASE_URL` по умолчанию равна `/api`. Все пути ниже указаны **относительно этого префикса**, например: `POST /api/auth/login`.

---

## 1. Получение JWT-токена

### Запрос

**POST** `/auth/login`

**Content-Type:** `application/json`

```json
{
  "login": "logistic",
  "password": "your-password"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `login` | string | Логин пользователя в таблице `users` (1–64 символа) |
| `password` | string | Пароль (1–128 символов) |

### Успешный ответ (200)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_at": "2026-06-03T12:00:00+00:00",
  "user": {
    "id": 5,
    "login": "logistic",
    "role": "logistic",
    "role_code": "logistic",
    "role_label": "Логист",
    "full_name": "Петров Пётр",
    "phone": "+7..."
  }
}
```

| Поле | Описание |
|------|----------|
| `access_token` | JWT для заголовка `Authorization` |
| `token_type` | Всегда `bearer` |
| `expires_at` | Время истечения (UTC, ISO 8601) |
| `user` | Данные вошедшего пользователя |

Срок жизни задаётся `JWT_EXPIRE_MINUTES` (по умолчанию 10080 минут = 7 суток). Секрет — `JWT_SECRET` в `.env`.

### Ошибки

| Код | Причина |
|-----|---------|
| 401 | Неверный логин/пароль или пользователь неактивен (`is_active = false`) |
| 422 | Невалидное тело запроса |

### Пример (curl)

```bash
curl -s -X POST "https://example.com/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"login":"accountant","password":"secret"}'
```

Сохраните `access_token` из ответа.

---

## 2. Использование JWT в запросах

Для всех защищённых методов PWA передаёт заголовок:

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

При истечении или неверном токене сервер отвечает **401** (`Missing authorization token`, `Invalid access token` и т.п.) — нужно снова вызвать `/auth/login`.

---

## 3. Роли и доступ

| `role_code` | Создание рейса | Создание расчёта ЗП |
|-------------|----------------|---------------------|
| `logistic` | да | нет |
| `accountant` | да | да |
| `admin` | да | да |
| `superadmin` | да | да |
| `driver` | нет | нет (только просмотр своих расчётов) |

---

## 4. Создание рейса (как в PWA)

Эндпоинт, который вызывает экран «Рейсы» в PWA: `createAdminRoute` → **POST** `/v1/admin/routes`.

**Требуется роль:** логист, бухгалтер, администратор или супер-админ.

### Тело запроса

| Поле | Тип | Обязательность | Описание |
|------|-----|----------------|----------|
| `route_id` | string | **да** | Уникальный номер рейса (например `00ДМ-000600`) |
| `driver_user_id` | number | рекомендуется | ID водителя в `users` (роль `driver`, активен) |
| `driver_fio` | string | альтернатива | ФИО для поиска, если `driver_user_id` не передан; должно **однозначно** найти одного водителя |
| `number_auto` | string | нет | Номер ТС |
| `temperature` | string | нет | Температурный режим |
| `dispatcher_contacts` | string | нет | Контакты диспетчера |
| `registration_number` | string | нет | Номер для регистрации |
| `trailer_number` | string | нет | Номер прицепа |
| `points` | array | нет | Точки маршрута (до 200) |

Каждая точка в `points`:

| Поле | Тип | Обязательность | Описание |
|------|-----|----------------|----------|
| `type_point` | string | да | `loading` / `unloading` (иначе сохранится как загрузка) |
| `place_point` | string | да | Адрес / место |
| `date_point` | string | да | Дата/время (как в PWA, например `15.03.2026` или `15.03.2026 14:00`) |
| `point_name` | string | нет | Название точки |
| `point_contacts` | string | нет | Контакты на точке |
| `point_time` | string | нет | Время |
| `point_note` | string | нет | Примечание |
| `order_index` | number | нет | Порядок сортировки |

### Успешный ответ (201)

Объект рейса с вложенными `driver`, `points`, `status: "new"` и т.д. (как `AdminRoute` в PWA).

### Коды ошибок

| Код | Описание |
|-----|----------|
| 401 | Нет или неверный JWT |
| 403 | Недостаточно прав (не route manager) |
| 409 | Рейс с таким `route_id` уже есть |
| 422 | Не указан водитель или ФИО неоднозначно |
| 404 | `driver_user_id` не найден |
| 400 | Назначенный пользователь не водитель или неактивен |

### Список водителей (перед созданием)

**GET** `/v1/admin/routes/drivers` — список активных водителей для выбора `driver_user_id`.

### Пример (curl)

```bash
TOKEN="<access_token>"

curl -s -X POST "https://example.com/api/v1/admin/routes" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "route_id": "00ДМ-000700",
    "driver_user_id": 12,
    "number_auto": "А123ВС456",
    "trailer_number": "ОО 123",
    "temperature": "+2...+6",
    "points": [
      {
        "type_point": "loading",
        "place_point": "Склад ул. Ленина, 1",
        "date_point": "10.03.2026"
      },
      {
        "type_point": "unloading",
        "place_point": "Магазин ул. Мира, 10",
        "date_point": "11.03.2026"
      }
    ]
  }'
```

### Создание из текста 1С (дополнительно)

**POST** `/v1/admin/routes/onec` — тот же JWT и роли; тело:

```json
{
  "raw_text": "<текст сообщения из 1С>",
  "driver_user_id": 12,
  "number_auto": "А123ВС456",
  "trailer_number": "ОО 123"
}
```

После создания водителю уходит уведомление (как при ручном создании в боте/PWA).

---

## 5. Создание зарплатного расчёта (как в PWA)

Два способа создания (одинаковый результат в БД и уведомление водителю):

| Способ | Endpoint |
|--------|----------|
| Одна строка из 37 значений | **POST** `/v1/salary` |
| **Отдельные поля JSON** | **POST** `/v1/salary/structured` |

**Требуется роль:** `accountant`, `admin` или `superadmin`.

### Водитель в запросе

Укажите **одно** из полей (приоритет: `driver_user_id` → `driver_login` → `driver_fio`):

| Поле | Описание |
|------|----------|
| `driver_user_id` | ID водителя в `users` |
| `driver_fio` | ФИО: сначала точное совпадение с `full_name`, иначе единственный результат по подстроке (как при создании рейса) |
| `driver_login` | Логин водителя |

Опционально: **GET** `/v1/salary/lookup/drivers?q=<ФИО>` — список кандидатов, если по ФИО неоднозначно.

### Тело запроса создания

**POST** `/v1/salary`

```json
{
  "driver_fio": "Иванов Иван Иванович",
  "salary_line": "15.01.2026 г 50000 0 0 1000 ..."
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `driver_user_id` | number | ID водителя (необязательно, если есть `driver_fio` или `driver_login`) |
| `driver_fio` | string | ФИО водителя |
| `driver_login` | string | Логин водителя |
| `salary_line` | string | **Ровно 37 значений через пробел** — тот же формат, что в Telegram-боте и в textarea PWA |

### Формат `salary_line` (37 полей)

Порядок полей (через один пробел):

1. дата (`дд.мм.гггг`)
2. тип рейса (`г` / `мг` / `рд` / `пр` и т.д.)
3. оклад (`sum_status`)
4. сутки
5. загр. 2 рейса
6. шаттл
7. загр/выгр
8. штора (дт)
9. возврат
10. доп. шаттл
11. доп. точка
12. АЗС
13. паллет гипер
14. паллет метро
15. паллет ашан
16. тариф 3т
17. тариф 3.5т
18. тариф 5т
19. тариф 10т
20. тариф 12т
21. тариф 12.5т
22. пробег
23. комп. связи
24. стаж
25. 10%
26. премия
27. удержать
28. возмещение
29. др
30. без сут/др/прем/стажа
31. в день
32. **итого**
33. адрес загрузки
34. адрес выгрузки
35. транспорт
36. прицеп
37. № рейса

Дробные числа можно с точкой или запятой. Пустые суммы — `0`.

**Пример строки** (из бота):

```
15.01.2026 г 50000 0 0 1000 20 0 0 0 0 0 0 0 0 0 0 0 0 0 0 150 0 5 0 0 0 0 0 0 0 51000.00 адрес_загр адрес_выгр А123BC прицеп 001
```

Если полей не 37, ответ **400** с текстом вида: `Ожидается 37 значений через пробел, получено N`.

### Успешный ответ (201)

Объект расчёта, например:

```json
{
  "id": 101,
  "id_driver": "123456789",
  "date_salary": "15.01.2026",
  "type_route": "г",
  "total": 51000.0,
  "status_driver": "",
  "comment_driver": "",
  ...
}
```

Водителю создаётся push/уведомление «Новый расчёт зарплаты».

### Коды ошибок

| Код | Описание |
|-----|----------|
| 401 | Нет или неверный JWT |
| 403 | Роль не бухгалтер/админ |
| 404 | Водитель не найден |
| 422 | По `driver_fio` найдено ноль или несколько водителей |
| 400 | Неверная строка `salary_line` или пользователь не водитель |

### Пример (curl, строка)

```bash
TOKEN="<access_token>"

curl -s -X POST "https://example.com/api/v1/salary" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "driver_user_id": 12,
    "salary_line": "15.01.2026 г 50000 0 0 1000 20 0 0 0 0 0 0 0 0 0 0 0 0 0 0 150 0 5 0 0 0 0 0 0 0 51000.00 адрес_загр адрес_выгр А123BC прицеп 001"
  }'
```

### Создание с отдельными полями

**POST** `/v1/salary/structured`

Обязательны: **водитель** (`driver_user_id` или `driver_fio` или `driver_login`) и `date_salary` (`дд.мм.гггг`). Остальные числовые поля по умолчанию `0`, строковые — `""`. Имена полей совпадают с объектом расчёта в ответе API (`sum_status`, `sum_daily`, `total`, `load_address`, …).

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
  "load_address": "адрес_загр",
  "unload_address": "адрес_выгр",
  "transport": "А123BC",
  "trailer_number": "прицеп",
  "route_number": "001"
}
```

Пример для **https://drive.dmk.msk.ru/**:

```bash
curl -s -X POST "https://drive.dmk.msk.ru/api/v1/salary/structured" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d @salary.json
```

---

## 6. Интеграция без JWT (расчёт ЗП)

Для внешних систем (1С, скрипты) есть отдельный эндпоинт **без** Bearer-токена:

**POST** `/v1/salary/integration`

**Заголовок:** `X-Salary-Api-Key: <ключ>` (в `.env`: `SALARY_INTEGRATION_API_KEY`, если пусто — используется `API_KEY`).

```json
{
  "driver_user_id": 12,
  "salary_line": "..."
}
```

Идентификация водителя (одно из полей): `driver_user_id`, `driver_fio`, `driver_login`, `legacy_tg_id`.

Тот же формат с **отдельными полями**:

**POST** `/v1/salary/integration/structured` — заголовок `X-Salary-Api-Key` + водитель (см. выше) + все поля расчёта, как в `/v1/salary/structured` (без `salary_line`).

---

## 7. Типовой сценарий (скрипт)

```text
1. POST /auth/login          → access_token
2. GET  /v1/admin/routes/drivers  (опционально) → driver_user_id
3. POST /v1/admin/routes     → создать рейс
   — или —
   GET  /v1/salary/lookup/drivers?q=Иванов
   POST /v1/salary            → создать расчёт
```

---

## 8. Связанные материалы

- [PWA.md](./PWA.md) — роли, экраны, офлайн водителя
- [API_ROUTE.md](./API_ROUTE.md) — legacy API рейса по `X-API-Key`
