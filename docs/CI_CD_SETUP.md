# CI/CD setup (GitHub Actions + Docker Hub + Test server)

## Что делает workflow

Файл `.github/workflows/ci-cd-test.yml`:
1. Собирает Docker image из `Dockerfile`.
2. Пушит image в Docker Hub (`recod0/dmk-logistic`) с тегами:
   - `latest`
   - `sha-<short_commit_sha>`
3. По SSH деплоит на тестовый сервер через `docker compose`:
   - загружает `deploy/docker-compose.test.yml`
   - обновляет контейнер командой `pull + up -d`.

## Обязательные GitHub Secrets

Добавляются в Settings → Secrets and variables → Actions → **Secrets**.

| Имя | Назначение | Пример-заглушка |
|---|---|---|
| `DOCKERHUB_USERNAME` | Логин Docker Hub (ожидается `recod0`) | `recod0` |
| `DOCKERHUB_TOKEN` | Access token Docker Hub для push/pull | `dckr_pat_xxxxxxxxxxxxxxxxx` |
| `TEST_SERVER_HOST` | Хост тестового сервера для SSH | `203.0.113.10` |
| `TEST_SERVER_PORT` | SSH порт тестового сервера | `22` |
| `TEST_SERVER_USER` | SSH пользователь на тестовом сервере | `deploy` |
| `TEST_SERVER_SSH_KEY` | Приватный SSH-ключ (PEM/OpenSSH) | `-----BEGIN OPENSSH PRIVATE KEY-----...` |

## Обязательные GitHub Variables

Добавляются в Settings → Secrets and variables → Actions → **Variables**.

| Имя | Назначение | Пример-заглушка |
|---|---|---|
| `TEST_DEPLOY_PATH` | Каталог на тестовом сервере, где лежит compose и `.env` | `/opt/dmk-logistic` |

## Что должно быть на тестовом сервере

В каталоге `TEST_DEPLOY_PATH` должен быть файл `.env` для runtime-переменных приложения, например:

```env
TG_TOKEN=__TELEGRAM_BOT_TOKEN__
API_KEY=__API_ACCESS_KEY__
WIALON_TOKEN=__WIALON_TOKEN__
WIALON_BASE_URL=http://w1.wialon.justgps.ru
DB_PATH=/olymp/db/olymp.db
API_PORT=8000
```
