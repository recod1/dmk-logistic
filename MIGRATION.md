# SQLite -> Postgres migration guide

Документ описывает перенос данных из legacy SQLite (`db/olymp.db`) в новый Postgres-стек (FastAPI + Alembic + mobile API).

## 0) Требования

- Python 3.12+
- Postgres 15+ (или контейнер из `docker-compose.yml`)
- Установленные зависимости проекта (`pip install -r requirements.txt`)

## 1) Backup SQLite

Сделайте копию текущей БД перед любыми операциями:

```bash
mkdir -p backups
cp "./db/olymp.db" "./backups/olymp_$(date +%Y%m%d_%H%M%S).db"
```

Проверьте backup:

```bash
python - <<'PY'
import sqlite3
conn = sqlite3.connect("./backups/" + sorted(__import__("os").listdir("./backups"))[-1])
print("ok", conn.execute("select count(*) from sqlite_master").fetchone()[0])
conn.close()
PY
```

## 2) Подготовить Postgres

Вариант через docker:

```bash
docker compose up -d db
```

Или вручную создайте базу и пользователя.

## 3) Прогон Alembic миграций

Экспортируйте DSN и выполните:

```bash
export POSTGRES_DSN="postgresql+psycopg://postgres:postgres@localhost:5432/dmk_logistic"
alembic upgrade head
```

После этого в PG появятся таблицы:

- `users`
- `routes`
- `points`
- `route_points` (нормализация `Route.points` CSV)
- `route_events`
- `salary`
- `repair`

## 4) Перенести данные (python script)

```bash
python -m scripts.migrate_sqlite_to_postgres \
  --sqlite-path "./db/olymp.db" \
  --pg-dsn "$POSTGRES_DSN" \
  --default-password "ChangeMe123!" \
  --truncate
```

Что делает скрипт:

1. Переносит `Users`, `Route`, `Point`, `Salary`, `Repair`.
2. Создаёт логины для новой таблицы `users` и хеширует пароль `bcrypt_sha256` (bcrypt-backed).
3. Преобразует CSV `Route.points` в `route_points(route_id, point_id, order_index)`.
4. Печатает count по ключевым таблицам.

## 4b) Альтернатива через pgloader (опционально)

Можно сначала загрузить таблицы `Route/Point/...` в staging через `pgloader`, затем выполнить SQL трансформацию:

```sql
INSERT INTO route_points(route_id, point_id, order_index)
SELECT r.id, (trim(value))::int, ordinality - 1
FROM routes r,
LATERAL unnest(string_to_array(r.points_csv, ',')) WITH ORDINALITY AS t(value, ordinality)
WHERE trim(value) <> '' AND trim(value) <> '0';
```

Но в этом репозитории базовый и поддерживаемый путь — `python -m scripts.migrate_sqlite_to_postgres ...`.

## 5) Валидация

Проверьте количество строк в SQLite и Postgres:

```bash
python - <<'PY'
import sqlite3
from sqlalchemy import create_engine, text
import os

sqlite = sqlite3.connect("./db/olymp.db")
pg = create_engine(os.environ["POSTGRES_DSN"])

for table_sqlite, table_pg in [("Users","users"), ("Route","routes"), ("Point","points"), ("Salary","salary"), ("Repair","repair")]:
    sc = sqlite.execute(f"select count(*) from {table_sqlite}").fetchone()[0]
    with pg.connect() as conn:
        pc = conn.execute(text(f"select count(*) from {table_pg}")).scalar_one()
    print(table_sqlite, sc, "->", table_pg, pc)
sqlite.close()
PY
```

И отдельная проверка нормализации:

```sql
SELECT route_id, count(*) FROM route_points GROUP BY route_id ORDER BY route_id LIMIT 20;
```

## 6) Переключить env

В `.env`/секретах среды:

- выставить `POSTGRES_DSN`/`DATABASE_URL` на Postgres
- задать `JWT_SECRET`
- отключить `BOOTSTRAP_DEMO_USER` в production

Пример:

```env
POSTGRES_DSN=postgresql+psycopg://app_user:strong_pass@db:5432/dmk_logistic
DATABASE_URL=postgresql+psycopg://app_user:strong_pass@db:5432/dmk_logistic
JWT_SECRET=<strong-secret>
BOOTSTRAP_DEMO_USER=0
```

## 7) Создание/обновление логина вручную

```bash
python -m scripts.create_mobile_user \
  --pg-dsn "$POSTGRES_DSN" \
  --login "driver1" \
  --password "StrongPass123!" \
  --role "driver" \
  --full-name "Иванов Иван"
```

Portainer Exec (если запускаете скрипт как файл):

```bash
PYTHONPATH=/app python3 scripts/create_mobile_user.py \
  --pg-dsn "$POSTGRES_DSN" \
  --login "driver1" \
  --password "StrongPass123!" \
  --role "driver"
```

## 8) После изменения зависимостей API

Если менялись зависимости в `requirements.txt` (например, `passlib`/`bcrypt`),
нужно пересобрать и заново запушить API-образ:

```bash
docker build -f docker/api/Dockerfile -t recod0/dmk-logistic-api:latest .
docker push recod0/dmk-logistic-api:latest
```

