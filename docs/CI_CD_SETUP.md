# CI/CD setup (GitHub Actions + Docker Hub + Portainer script)

## Что реализовано

- Workflow: `.github/workflows/ci-cd-test.yml`
- Скрипт деплоя: `deploy/portainer-deploy.sh`
- Compose stack: `deploy/docker-compose.test.yml`

Pipeline:
1. Собирает и пушит image в Docker Hub (`recod0/dmkbot`).
2. Теги image:
   - `latest` (для default branch),
   - `sha-<short_commit_sha>`,
   - `<release-tag>` при push git-тега (например `v4.1` -> `4.1`).
3. Вызывает `deploy/portainer-deploy.sh`, который обновляет Portainer stack (по умолчанию `stack id = 17`).

## Compose для stack

`deploy/docker-compose.test.yml` хранит только шаблонные переменные:
- `image: ${IMAGE_NAME:-recod0/dmkbot}:${TAG:-4.1}`
- `TG_TOKEN`, `API_KEY`, `WIALON_TOKEN` (и опциональные `WIALON_BASE_URL`, `DB_PATH`, `API_PORT`)
- volume для sqlite: `/var/opt/dmkbot/db:/olymp/db`

Никакие реальные значения в репозиторий не коммитятся.

## GitHub Secrets (обязательно)

Settings → Secrets and variables → Actions → **Secrets**

| Имя | Назначение | Пример-заглушка |
|---|---|---|
| `DOCKERHUB_USERNAME` | Логин Docker Hub | `recod0` |
| `DOCKERHUB_TOKEN` | Docker Hub access token | `dckr_pat_xxxxxxxxxxxxxxxxx` |
| `PORTAINER_URL` | URL Portainer (без `/api` в конце) | `https://portainer.example.com` |
| `PORTAINER_API_TOKEN` | API token Portainer | `ptr_xxxxxxxxxxxxxxxxx` |
| `TG_TOKEN` | Telegram bot token (для stack env) | `123456:AA...` |
| `API_KEY` | API key приложения (для stack env) | `xxxxxxxxxxxxxxxx` |
| `WIALON_TOKEN` | Wialon token (для stack env) | `xxxxxxxxxxxxxxxx` |

### Дополнительно (по необходимости, тоже в Secrets)

| Имя | Назначение | Пример-заглушка |
|---|---|---|
| `WIALON_BASE_URL` | Базовый URL Wialon | `http://w1.wialon.justgps.ru` |
| `DB_PATH` | Путь к sqlite в контейнере | `/olymp/db/olymp.db` |
| `API_PORT` | Порт API внутри stack env | `8000` |

## GitHub Variables

Settings → Secrets and variables → Actions → **Variables**

| Имя | Назначение | Пример-заглушка |
|---|---|---|
| `IMAGE_NAME` | Имя Docker image | `recod0/dmkbot` |
| `TAG` | Дефолтный тег деплоя (для non-tag запусков) | `latest` |
| `PORTAINER_STACK_ID` | ID stack в Portainer | `17` |
| `PORTAINER_ENDPOINT_ID` | Endpoint ID (если не автоопределится) | `1` |
| `DEPLOY_PATH` | Опциональная переменная для stack env | `/opt/dmkbot` |

## Как работает `deploy/portainer-deploy.sh`

Скрипт:
1. Читает env:  
   `PORTAINER_URL`, `PORTAINER_API_TOKEN`, `PORTAINER_STACK_ID`, `PORTAINER_ENDPOINT_ID(optional)`, `IMAGE_NAME`, `TAG`, `DEPLOY_PATH(optional)`, `TG_TOKEN`, `API_KEY`, `WIALON_TOKEN`.
2. Запрашивает текущий stack (`/api/stacks/{id}`), определяет endpoint.
3. Берёт compose из `deploy/docker-compose.test.yml`.
4. Обновляет stack через `PUT /api/stacks/{id}?endpointId=...` с `stackFileContent` и `env`.
5. Для совместимости с версиями Portainer пробует оба варианта ключей в JSON payload:
   - `stackFileContent/env/prune/pullImage`
   - `StackFileContent/Env/Prune/PullImage`

Если ваша версия Portainer ожидает другой формат (например multipart), нужно адаптировать скрипт под конкретный API release.

## Важно по безопасности

Не храните реальные токены в репозитории и документации. Используйте только GitHub Secrets.  
Если токены когда-либо были опубликованы в чатах, логах или скриншотах — их нужно немедленно ротировать.
