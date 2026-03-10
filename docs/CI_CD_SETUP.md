# CI/CD setup (GitHub Actions + Docker Hub + Portainer)

## Что делает workflow

Файл `.github/workflows/ci-cd-test.yml`:
1. Собирает Docker image из `Dockerfile`.
2. Пушит image в Docker Hub `recod0/dmkbot` с тегами:
   - `latest` (для default branch),
   - `sha-<short_commit_sha>`,
   - `<release-tag>` при push тега (например `4.1` или `v4.1` → `4.1`).
3. Деплоит на тест:
   - **предпочтительно** через Portainer API (stack update),
   - **fallback** через SSH и `docker compose -p dmkbot -f ... up -d`.

## Compose для деплоя

Используется `deploy/docker-compose.test.yml`:
- image: `${IMAGE_NAME:-recod0/dmkbot}:${TAG:-4.1}`,
- volume для sqlite: `/var/opt/dmkbot/db:/olymp/db` (сохранение базы),
- переменные приложения через `${TG_TOKEN}`, `${API_KEY}`, `${WIALON_TOKEN}` и т.д.

## GitHub Secrets

Добавляются в Settings → Secrets and variables → Actions → **Secrets**.

### Основные (Docker Hub + Portainer)

| Имя | Назначение | Пример-заглушка |
|---|---|---|
| `DOCKERHUB_USERNAME` | Логин Docker Hub | `recod0` |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token | `dckr_pat_xxxxxxxxxxxxxxxxx` |
| `PORTAINER_URL` | URL Portainer (без `/api` на конце) | `https://portainer.example.com` |
| `PORTAINER_API_TOKEN` | API Token Portainer для stack update | `ptr_xxxxxxxxxxxxxxxxx` |

### Опционально для SSH fallback

| Имя | Назначение | Пример-заглушка |
|---|---|---|
| `TEST_SERVER_HOST` | SSH хост тестового сервера | `203.0.113.10` |
| `TEST_SERVER_PORT` | SSH порт | `22` |
| `TEST_SERVER_USER` | SSH пользователь | `deploy` |
| `TEST_SERVER_SSH_KEY` | Приватный SSH-ключ | `-----BEGIN OPENSSH PRIVATE KEY-----...` |

## GitHub Variables

Добавляются в Settings → Secrets and variables → Actions → **Variables**.

| Имя | Назначение | Пример-заглушка |
|---|---|---|
| `IMAGE_NAME` | Имя Docker image | `recod0/dmkbot` |
| `TAG` | Дефолтный deploy tag (не для релизных tag push) | `latest` |
| `DEPLOY_PATH` | Путь на сервере для fallback compose-деплоя | `/opt/dmkbot` |
| `PORTAINER_STACK_ID` | ID stack в Portainer | `17` |
| `PORTAINER_ENDPOINT_ID` | Endpoint ID в Portainer (если не определяется автоматически) | `1` |

## Runtime-переменные приложения

Для Portainer-деплоя переменные окружения должны быть заданы в самом stack (Portainer env):
- `TG_TOKEN`
- `API_KEY`
- `WIALON_TOKEN`
- `WIALON_BASE_URL` (опционально)
- `DB_PATH` (опционально, default `/olymp/db/olymp.db`)
- `API_PORT` (опционально, default `8000`)

Для SSH fallback эти переменные обычно лежат в `/opt/dmkbot/.env` (или в `DEPLOY_PATH/.env`).

## Важно по безопасности

Не храните реальные токены в репозитории, workflow-файлах и документации. Используйте только GitHub Secrets / Portainer env.  
Если секреты когда-либо публиковались в чате или логах, их нужно немедленно ротировать (пересоздать).
