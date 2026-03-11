# CI/CD setup (GitHub Actions + Docker Hub + Portainer)

## Что делает workflow

Файл `.github/workflows/ci-cd-test.yml`:
1. Собирает Docker image из `Dockerfile`.
2. Пушит image в Docker Hub `recod0/dmkbot` с тегами:
   - `latest` (для default branch),
   - `sha-<short_commit_sha>`,
   - `<release-tag>` при push тега (например `4.1` или `v4.1` → `4.1`).
3. Деплоит на тест **только через Portainer API**:
   - через скрипт `deploy/portainer-deploy.sh`,
   - с обновлением stack env и compose из `deploy/docker-compose.test.yml`.

## Compose для деплоя

Используется `deploy/docker-compose.test.yml`:
- image: `${IMAGE_NAME:-recod0/dmkbot}:${TAG:-latest}`,
- фиксированный порт: `8010:8000`,
- volume для sqlite: `/var/opt/dmkbot/db:/olymp/db` (сохранение базы),
- переменные приложения: `${TG_TOKEN}`, `${API_KEY}`, `${WIALON_TOKEN}`.

## GitHub Secrets

Добавляются в Settings → Secrets and variables → Actions → **Secrets**.

### Основные (Docker Hub + Portainer + runtime secrets)

| Имя | Назначение | Пример-заглушка |
|---|---|---|
| `DOCKERHUB_USERNAME` | Логин Docker Hub | `recod0` |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token | `dckr_pat_xxxxxxxxxxxxxxxxx` |
| `PORTAINER_URL` | URL Portainer (без `/api` на конце) | `https://portainer.example.com` |
| `PORTAINER_API_TOKEN` | API Token Portainer для stack update | `ptr_xxxxxxxxxxxxxxxxx` |
| `TG_TOKEN` | Токен Telegram-бота | `123456:AA...` |
| `API_KEY` | Ключ API приложения | `xxxxxxxxxxxxxxxx` |
| `WIALON_TOKEN` | Токен Wialon | `xxxxxxxxxxxxxxxx` |

## GitHub Variables

Добавляются в Settings → Secrets and variables → Actions → **Variables**.

| Имя | Назначение | Пример-заглушка |
|---|---|---|
| `IMAGE_NAME` | Имя Docker image | `recod0/dmkbot` |
| `TAG` | Дефолтный deploy tag (не для релизных tag push) | `latest` |
| `PORTAINER_STACK_ID` | ID stack в Portainer | `17` |
| `PORTAINER_ENDPOINT_ID` | Endpoint ID в Portainer (если не определяется автоматически) | `1` |

## Runtime-переменные приложения

Workflow прокидывает переменные в шаг деплоя через `env`, а скрипт
`deploy/portainer-deploy.sh`:
- валидирует обязательные значения в bash (без `if` на GitHub expressions),
- делает upsert env в Portainer stack: `IMAGE_NAME`, `TAG`, `TG_TOKEN`, `API_KEY`, `WIALON_TOKEN`.

## Защита от пустого IMAGE_NAME/TAG

Workflow использует двойной fallback:
1. В build job шаг `Resolve image and deploy tag`:
   - `vars.IMAGE_NAME` → `DEFAULT_IMAGE_NAME=recod0/dmkbot`,
   - `vars.TAG` → `DEFAULT_DEPLOY_TAG=latest` (для non-tag push).
2. В deploy job:
   - `needs.build_and_push.outputs.image_name || env.DEFAULT_IMAGE_NAME`,
   - `needs.build_and_push.outputs.deploy_tag || env.DEFAULT_DEPLOY_TAG`.

Таким образом, деплой не падает даже если GitHub Variables не заполнены.

## Важно по безопасности

Не храните реальные токены в репозитории, workflow-файлах и документации. Используйте только GitHub Secrets / Portainer env.  
Если секреты когда-либо публиковались в чате или логах, их нужно немедленно ротировать (пересоздать).
