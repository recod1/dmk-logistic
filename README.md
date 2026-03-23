# dmk-logistic

Репозиторий содержит:

1. Legacy-бот + старые endpoints/админку (`/api/route`, `/admin/*`) на SQLite.
2. Новый стек рядом с legacy:
   - FastAPI + Postgres + Alembic
   - JWT auth (`/auth/login`)
   - Mobile API (`/v1/mobile/*`)
   - PWA (Vue 3 + Vite + TS + Dexie offline outbox)

## Быстрый запуск нового стека (docker-compose)

```bash
cp .env.example .env
docker compose up --build
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
  --role driver
```

