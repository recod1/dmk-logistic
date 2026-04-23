# Перенос данных между 2 серверами (Portainer): старая версия → новая версия

Эта инструкция покрывает **2 сценария** (выберите один):

- **Сценарий A: Postgres → Postgres (рекомендуемый для вас)**: и старая, и новая версия используют Postgres в Docker.
- **Сценарий B: SQLite → Postgres (legacy)**: старая версия хранит данные в SQLite (`db/olymp.db`), новая — в Postgres.

Цель: перенести данные на новый сервер так, чтобы **ничего не потерять** и иметь **понятный откат**.

> Важно про “ничего не сломалось”: миграция — это всегда риск. Поэтому мы делаем
> **бэкапы + “freeze” (остановить запись) + проверку + переключение + план отката**.

## 0) Что нужно заранее (чеклист)

- Доступ в Portainer на **оба** сервера (старый и новый).
- Возможность выполнять команды в контейнерах (**Console / Exec**) или по SSH на хост.
- Понимание, где реально лежат данные:
  - старый сервер: либо Postgres volume, либо SQLite файл;
  - новый сервер: Postgres volume (`pg_data` в `deploy/portainer/docker-compose.portainer.yml`).
- Достаточно места на диске под dump (часто от 100 МБ до нескольких ГБ).

Также: если используете скрипты/алембик, полезно прочитать `MIGRATION.md`, но ниже все команды уже прописаны.

## 1) Общий безопасный план (для обоих сценариев)

1. **Freeze**: остановить запись в старую базу (остановить API/бот/интеграции).
2. **Backup старой БД** (и backup новой БД “на всякий”).
3. **Перенос данных** (выберите сценарий A или B ниже).
4. **Проверка** (counts + 2–3 контрольных кейса в UI).
5. **Cutover**: переключить пользователей на новый сервер.
6. **Откат**: всегда держим возможность быстро вернуться.

## 2) СЦЕНАРИЙ A (Postgres → Postgres): полный перенос базы

Этот сценарий используйте, если **оба** сервера работают на Postgres и вы хотите, чтобы в новой версии
появились все данные старой.

### 2.1) Узнать имена контейнеров (на каждом сервере)

Если есть SSH на хост:

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
```

В Portainer: откройте Stack → увидите контейнеры, обычно называются вроде `<stack>_db_1`, `<stack>_api_1`, `<stack>_web_1`.

Дальше в командах используйте:

- `OLD_DB_CONTAINER` — контейнер Postgres на старом сервере
- `NEW_DB_CONTAINER` — контейнер Postgres на новом сервере
- `NEW_API_CONTAINER` — контейнер api на новом сервере (если надо прогнать alembic)

### 2.2) Freeze (старый сервер)

В Portainer остановите контейнер(ы), которые пишут в старую БД:

- старый `api`
- старый `bot` (если отдельный)
- любые интеграции/воркеры, создающие рейсы/точки/статусы

### 2.3) Backup старого Postgres (dump) — команды

#### Вариант A: через Portainer Console (в контейнере Postgres на старом сервере)

```bash
set -e
TS="$(date +%Y%m%d_%H%M%S)"
pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom -f "/tmp/old_${TS}.dump"
ls -lh "/tmp/old_${TS}.dump"
```

#### Вариант B: через SSH (docker exec)

```bash
OLD_DB_CONTAINER="<old_db_container_name>"
TS="$(date +%Y%m%d_%H%M%S)"
docker exec -e TS="$TS" "$OLD_DB_CONTAINER" sh -lc '
set -e
pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom -f "/tmp/old_${TS}.dump"
ls -lh "/tmp/old_${TS}.dump"
'
```

#### Скопировать dump со старого сервера

Если есть SSH на хост старого сервера:

```bash
OLD_DB_CONTAINER="<old_db_container_name>"
DUMP_IN_CONTAINER="/tmp/old_YYYYMMDD_HHMMSS.dump"
docker cp "$OLD_DB_CONTAINER:$DUMP_IN_CONTAINER" "./old.dump"
```

Далее перенесите `old.dump` на новый сервер:

```bash
scp ./old.dump user@NEW_SERVER:/tmp/old.dump
```

### 2.4) Backup нового Postgres “перед восстановлением” (на новом сервере)

```bash
NEW_DB_CONTAINER="<new_db_container_name>"
TS="$(date +%Y%m%d_%H%M%S)"
docker exec -e TS="$TS" "$NEW_DB_CONTAINER" sh -lc '
set -e
pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom -f "/tmp/new_before_restore_${TS}.dump"
ls -lh "/tmp/new_before_restore_${TS}.dump"
'
```

Сохраните этот dump вне контейнера:

```bash
docker cp "$NEW_DB_CONTAINER:/tmp/new_before_restore_YYYYMMDD_HHMMSS.dump" "./new_before_restore.dump"
```

### 2.5) Восстановление dump в новый Postgres (полная замена данных)

1) Положите `old.dump` внутрь контейнера Postgres нового сервера:

```bash
NEW_DB_CONTAINER="<new_db_container_name>"
docker cp /tmp/old.dump "$NEW_DB_CONTAINER:/tmp/old.dump"
```

2) Восстановите с очисткой существующих объектов:

```bash
docker exec "$NEW_DB_CONTAINER" sh -lc '
set -e
pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists /tmp/old.dump
'
```

> Примечание: `--clean` удалит объекты перед восстановлением. Поэтому мы и делали backup “new_before_restore”.

### 2.6) После восстановления — прогнать миграции схемы (если версии разные)

Если новая версия приложения содержит миграции поверх старой схемы — выполните:

```bash
NEW_API_CONTAINER="<new_api_container_name>"
docker exec "$NEW_API_CONTAINER" sh -lc 'alembic upgrade head'
```

Если в образе миграции запускаются автоматически — всё равно полезно выполнить вручную один раз, чтобы увидеть ошибки.

### 2.7) Проверка (counts + smoke)

Быстрый SQL чек в новом Postgres:

```bash
docker exec "$NEW_DB_CONTAINER" sh -lc '
set -e
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt"
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select count(*) as users from users;"
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select count(*) as routes from routes;"
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select count(*) as points from points;"
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select count(*) as route_points from route_points;"
'
```

Проверка пары рейсов вручную в UI:

- логин логист/админ
- список рейсов: есть ли старые `route_id`
- водитель: видит ли назначенные рейсы

### 2.8) Откат (если что-то пошло не так)

1) Вернуть трафик на старый сервер.
2) Восстановить Postgres нового сервера из `new_before_restore.dump`:

```bash
docker cp ./new_before_restore.dump "$NEW_DB_CONTAINER:/tmp/new_before_restore.dump"
docker exec "$NEW_DB_CONTAINER" sh -lc '
set -e
pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists /tmp/new_before_restore.dump
'
```

## 3) СЦЕНАРИЙ B (SQLite → Postgres): legacy перенос

## 2) Бэкап старой SQLite (старый сервер)

### Вариант A: файл доступен на хосте

Найдите реальный путь к `olymp.db` (часто лежит в каталоге проекта или примонтирован).
Скопируйте файл с timestamp:

```bash
mkdir -p backups
cp "./db/olymp.db" "./backups/olymp_$(date +%Y%m%d_%H%M%S).db"
```

Проверка, что файл читается:

```bash
python - <<'PY'
import sqlite3, os, glob
path = sorted(glob.glob("./backups/olymp_*.db"))[-1]
conn = sqlite3.connect(path)
print("backup:", path)
print("tables:", conn.execute("select count(*) from sqlite_master").fetchone()[0])
conn.close()
PY
```

### Вариант B: SQLite внутри контейнера

1) В Portainer откройте контейнер старого API/бота → **Console**.
2) Узнайте, где лежит `olymp.db` (обычно по env `DB_PATH`).
3) Скопируйте его во временный путь внутри контейнера и затем выгрузите с хоста (через bind/volume или `docker cp` по SSH).

Если у вас есть SSH на хост, самый прямой путь:

```bash
docker cp <container_name_or_id>:/app/db/olymp.db ./olymp.db
```

## 3) Бэкап Postgres (новый сервер)

Даже если “новая” база пустая — всё равно полезно иметь dump перед импортом.

В Portainer откройте контейнер `db` (Postgres) → Console и выполните:

```bash
pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom -f "/tmp/pg_backup_$(date +%Y%m%d_%H%M%S).dump"
ls -lh /tmp/pg_backup_*.dump
```

Дальше сохраните dump **вне контейнера** (через `docker cp` с хоста):

```bash
docker cp <postgres_container_id>:/tmp/pg_backup_YYYYMMDD_HHMMSS.dump ./pg_backup.dump
```

## 4) Freeze (остановить изменения данных)

Чтобы “ничего не сломалось” и не было рассинхрона:

- На **старом** сервере в Portainer остановите стек/контейнеры, которые пишут в SQLite
  (бот, API, любые интеграции, которые создают рейсы/точки/статусы).

Если вы не можете полностью остановить — хотя бы:

- отключите внешние интеграции, которые создают рейсы;
- предупредите пользователей, что в старой версии временно нельзя работать.

## 5) Подготовить схему Postgres (новый сервер)

Схема должна соответствовать текущему коду (Alembic на `head`).

Если в вашем образе `api` миграции применяются автоматически — проверьте логи контейнера `api`.
Если нужно вручную, можно выполнить внутри контейнера `api`:

```bash
alembic upgrade head
```

## 6) Импорт SQLite → Postgres (на новом сервере)

В репозитории уже есть поддерживаемый скрипт: `scripts/migrate_sqlite_to_postgres.py`.

### 6.1) Решите, “чистим ли” целевую базу

- Если новая база **пустая/тестовая** → используйте `--truncate`.
- Если в новой базе **уже есть рабочие данные** → **не** используйте `--truncate`, а делайте перенос в отдельную базу/стенд или заранее согласуйте, что именно перезаписываем.

### 6.2) Запуск скрипта

Запускать удобнее всего там, где доступен:

- файл SQLite backup (`olymp_*.db`);
- DSN до Postgres (`POSTGRES_DSN`/`DATABASE_URL`);
- Python и зависимости проекта.

Пример запуска (как в `MIGRATION.md`):

```bash
export POSTGRES_DSN="postgresql+psycopg://postgres:postgres@localhost:5432/dmk_logistic"

python scripts/migrate_sqlite_to_postgres.py \
  --sqlite-path "./backups/olymp_YYYYMMDD_HHMMSS.db" \
  --pg-dsn "$POSTGRES_DSN" \
  --default-password "ChangeMe123!" \
  --truncate
```

**Важно про пароли**:

- У пользователей, перенесённых из SQLite, логины будут вида `tg_123456` или производные от имени.
- Пароль всем будет назначен `--default-password` (захешированный). После миграции смените пароли нужным ролям.

## 7) Проверка целостности (обязательно)

### 7.1) Сравнить counts SQLite vs Postgres

Используйте проверку из `MIGRATION.md` (она сравнивает `Users/Route/Point/Salary/Repair`).

### 7.2) Проверить привязки точек

В Postgres:

```sql
SELECT route_id, count(*) FROM route_points GROUP BY route_id ORDER BY count(*) DESC LIMIT 20;
```

### 7.3) Проверка в UI PWA

1) Залогиньтесь админом/логистом.
2) Откройте **Рейсы** — найдите 2–3 реальных `route_id` из старой системы.
3) Проверьте, что:
   - у рейса есть водитель;
   - точки отображаются в нужном порядке;
   - статусы/время/комментарии (если были) корректны.

## 8) Переключение (cutover) и откат

### Переключение

- Переключите DNS/прокси так, чтобы пользователи заходили на **новый** сервер (PWA).
- Старый сервер оставьте выключенным или в режиме “только чтение” на время (1–3 дня), чтобы иметь быстрый откат.

### Откат

Если что-то пошло не так:

- возвращаете трафик на старый сервер;
- восстанавливаете Postgres из `pg_dump` (если импорт повредил данные) или пересоздаёте Postgres volume и повторяете процедуру.

## 9) Важные нюансы именно для вашей конфигурации (Portainer + 2 сервера)

1) **Не путайте endpoints**:
   - legacy API для интеграций: обычно `POST /api/route` (часто с внешним префиксом получается `/api/api/route`).
   - PWA API: `/auth/login`, `/v1/admin/routes`, `/v1/mobile/...` (под внешним префиксом `/api`).

2) **Одинаковые секреты в новом стеке**:
   - `JWT_SECRET` должен быть стабильный (иначе токены “обнулятся” при смене сервера).
   - `VAPID_*` для push (если используете) тоже должны быть одинаковыми.

3) **Старый `API_KEY` и новый JWT — разные системы доступа**:
   - после миграции лучше постепенно переводить интеграции на новый механизм (JWT) или сделать мост (legacy endpoint, который пишет в Postgres).

## 10) Если хотите самый “безболезненный” путь для интеграций

Чтобы внешние системы продолжали слать **старый** запрос (`X-API-Key`, `driver_name`, `points`) и при этом рейсы появлялись в PWA:

- сделайте/используйте legacy endpoint, но чтобы он создавал данные **в Postgres**.

Это отдельная задача (мост), но она сильно упрощает эксплуатацию, если у вас уже есть внешние интеграции “под бота”.

