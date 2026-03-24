# DATABASE: структура Postgres

Документ описывает новую PostgreSQL схему для FastAPI/mobile стека.

## Таблицы

## 1) `users`

Основные поля:

- `id` (PK)
- `login` (unique)
- `password_hash`
- `role_code` (`driver|logistic|accountant|admin|superadmin`)
- `full_name` (ФИО)
- `phone`
- `legacy_tg_id`
- `is_active`
- `created_at`, `updated_at`

Назначение: единая авторизация по логину/паролю + RBAC.

## 2) `routes`

- `id` (PK, строковый id рейса)
- `legacy_driver_tg_id`
- `assigned_user_id` -> `users.id` (водитель)
- `created_by_user_id` -> `users.id` (кто создал)
- `status` (`new|process|success|...`)
- `number_auto`, `temperature`, `dispatcher_contacts`, `registration_number`, `trailer_number`
- `accepted_at`, `created_at`, `updated_at`

## 3) `points`

- `id` (PK)
- `route_id` -> `routes.id`
- `type_point`, `place_point`, `date_point`
- `status` (`new|process|registration|load|docs|success`)
- timestamps: `time_accepted`, `time_registration`, `time_put_on_gate`, `time_docs`, `time_departure`
- `lat`, `lng`, `odometer`
- `created_at`, `updated_at`

## 4) `route_points`

Нормализованный порядок точек в рейсе:

- `route_id` -> `routes.id`
- `point_id` -> `points.id`
- `order_index`

Ограничения:

- уникальность (`route_id`, `point_id`)
- уникальность (`route_id`, `order_index`)

## 5) `route_events`

События смены статусов (offline batch):

- `route_id`, `point_id`, `user_id`
- `device_id`, `client_event_id`
- `occurred_at_client`
- `to_status`
- `applied`, `error`
- `server_received_at`

Идемпотентность:

- уникальный ключ (`user_id`, `device_id`, `client_event_id`).

## 6) Legacy-подсистемы (перенесены в Postgres)

- `salary`
- `repair`

Сохранены для совместимости с текущими данными/процессами.

## Связи

- `users (1) -> (N) routes.assigned_user_id`
- `users (1) -> (N) routes.created_by_user_id`
- `routes (1) -> (N) points`
- `routes (1) -> (N) route_points`
- `points (1) -> (N) route_events`
- `users (1) -> (N) route_events`

## Статусы точек и переходы

Допустимая последовательность:

`new -> process -> registration -> load -> docs -> success`

Смена статуса валидируется на backend в `POST /v1/mobile/events:batch`.

## Роли и доступ

- `admin`, `superadmin`:
  - `/v1/admin/users/*`
  - `/v1/admin/routes/*`
- `logistic`, `accountant`:
  - `/v1/admin/routes/*`
- `driver`:
  - `/v1/mobile/*` (active route, accept, events batch)

## Миграции

Применяются через Alembic:

```bash
alembic upgrade head
```

