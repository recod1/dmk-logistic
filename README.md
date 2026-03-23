# dmk-logistic

Репозиторий содержит:

1. Legacy-бот + старые endpoints/админку (`/api/route`, `/admin/*`) на SQLite.
2. Новый стек рядом с legacy:
   - FastAPI + Postgres + Alembic
   - JWT auth (`/auth/login`)
   - Mobile API (`/v1/mobile/*`)
   - PWA (Vue 3 + Vite + TS + Dexie offline outbox)

## Документация

- [PWA возможности и роли](./docs/PWA.md)
- [Структура БД и связи](./docs/DATABASE.md)
- [Перенос SQLite -> Postgres](./MIGRATION.md)

## Быстрый запуск нового стека (docker-compose)

```bash
cp .env.example .env
docker compose up -d
```

Сервисы:

- web (nginx + PWA): http://localhost:8080
- api (fastapi): http://localhost:8000
- db (postgres): localhost:5432

Nginx проксирует backend как `/api/*`:

- `/api/auth/login`
- `/api/v1/mobile/routes/active`
- `/api/v1/mobile/routes/{id}/accept`
- `/api/v1/mobile/events:batch`
- `/api/v1/admin/users`
- `/api/v1/admin/routes`

## Deploy/CI (Docker Hub + Portainer)

### Docker images (image-only compose)

`docker-compose.yml` и `deploy/portainer/docker-compose.portainer.yml` используют готовые образы:

- `API_IMAGE` (по умолчанию `recod0/dmk-logistic-api:latest`)
- `WEB_IMAGE` (по умолчанию `recod0/dmk-logistic-web:latest`)

### CI публикация образов

Workflow: `.github/workflows/docker-publish.yml`

- запускается на `push` в `main` и на push тега;
- собирает и пушит **два образа**:
  - `recod0/dmk-logistic-api`
  - `recod0/dmk-logistic-web`
- публикует теги:
  - `latest`
  - `sha-<короткий_sha>`
- использует Buildx cache (`cache-from/cache-to` type=gha).

Обязательные GitHub Secrets:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

### Ручная публикация (опционально)

```bash
docker build -f docker/api/Dockerfile -t recod0/dmk-logistic-api:latest .
docker push recod0/dmk-logistic-api:latest

docker build -f docker/web/Dockerfile -t recod0/dmk-logistic-web:latest .
docker push recod0/dmk-logistic-web:latest
```

### Portainer stack (без curl API деплоя)

Используйте stack из Git-репозитория:

1. В Portainer откройте **Stacks** → **Add stack** → **Repository**.
2. Укажите репозиторий `recod1/dmk-logistic`.
3. Compose path: `deploy/portainer/docker-compose.portainer.yml`.
4. Задайте переменные stack environment:
   - `API_IMAGE` / `WEB_IMAGE` (например, `recod0/dmk-logistic-api:latest`, `recod0/dmk-logistic-web:latest`);
   - `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`;
   - `JWT_SECRET` (обязательно), а также при необходимости `API_KEY`, `TG_TOKEN`, `WIALON_TOKEN`, `ADMIN_PASSWORD`.
5. Включите автообновление стека одним из способов:
   - webhook update (если используется);
   - periodic pull / re-pull image + redeploy.

Запуск локально из опубликованных образов:

```bash
cp .env.example .env
docker compose pull
docker compose up -d
```

### Alembic через API image (при необходимости вручную)

В стандартном запуске миграции применяются автоматически в `api` контейнере.
Для ручного прогона можно выполнить:

```bash
docker run --rm --network host \
  -e POSTGRES_DSN="postgresql+psycopg://postgres:postgres@localhost:5432/dmk_logistic" \
  recod0/dmk-logistic-api:latest \
  bash -lc "alembic upgrade head"
```

## Логин в PWA

По умолчанию для локальной среды (через env):

- login: `driver`
- password: `driver123`

Управляется переменными:

- `BOOTSTRAP_DEMO_USER`
- `DEMO_LOGIN`
- `DEMO_PASSWORD`
- `DEMO_ROLE`

## Alembic / миграции

```bash
export POSTGRES_DSN="postgresql+psycopg://postgres:postgres@localhost:5432/dmk_logistic"
alembic upgrade head
```

## Миграция данных SQLite -> Postgres

Полная инструкция: [MIGRATION.md](./MIGRATION.md)

Коротко:

```bash
python scripts/migrate_sqlite_to_postgres.py \
  --sqlite-path ./db/olymp.db \
  --pg-dsn "$POSTGRES_DSN" \
  --default-password "ChangeMe123!" \
  --truncate
```

## Ручное создание пользователя для mobile API

```bash
python scripts/create_mobile_user.py \
  --pg-dsn "$POSTGRES_DSN" \
  --login driver1 \
  --password StrongPass123! \
  --role driver \
  --full-name "Иванов Иван" \
  --phone "+79990000000"
```

Создание администратора:

```bash
python scripts/create_mobile_user.py \
  --pg-dsn "$POSTGRES_DSN" \
  --login admin1 \
  --password StrongAdminPass123! \
  --role admin \
  --full-name "Петров Петр"
```

Допустимые роли (`--role`): `driver`, `logistic`, `accountant`, `admin`, `superadmin`
или русские значения: `Водитель`, `Логист`, `Бухгалтер`, `Администратор`, `Супер-админ`.

## Экраны PWA по ролям

- `admin` / `superadmin`:
  - раздел **Пользователи** (CRUD + блок/разблок);
  - раздел **Рейсы** (создание/просмотр/назначение водителя).
- `logistic` / `accountant`:
  - раздел **Рейсы** (создание/просмотр/назначение водителя).
- `driver`:
  - экран **Мой рейс** + офлайн-статусы точек через outbox.
