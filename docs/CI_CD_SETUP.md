# CI/CD setup (GitHub Actions + Docker Hub + Portainer)

## Что делает workflow

Файл `.github/workflows/deploy-test.yml`:
1. Запускается при push в ветки `main` и `develop`.
2. Берет repository variable `DOCKER_IMAGE` (например `recod0/dmkbot:latest`) и вычисляет итоговый тег:
   - для `main` → `latest`,
   - для `develop` → `${GITHUB_SHA::7}`.
3. Логинится в Docker Hub и пушит собранный образ с тегом из шага выше.
4. Обновляет Portainer stack через `deploy/portainer_update_stack.sh`.

## Deploy template

Используется `deploy/stack-compose.tpl.yml`:
- image: `${DOCKER_IMAGE}`,
- restart: `unless-stopped`,
- ports: `8010:8000`,
- volume: `/var/opt/dmkbot/db:/olymp/db`,
- env: `${TG_TOKEN}`, `${API_KEY}`, `${WIALON_TOKEN}`.

## GitHub Secrets

Добавляются в Settings → Secrets and variables → Actions → **Secrets**.

| Имя | Назначение |
|---|---|
| `DOCKERHUB_USERNAME` | Логин Docker Hub |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token |
| `PORTAINER_API_KEY` | API key Portainer для обновления stack |
| `TG_TOKEN` | Telegram token |
| `API_KEY` | API key приложения |
| `WIALON_TOKEN` | Wialon token |

## GitHub Variables

Добавляются в Settings → Secrets and variables → Actions → **Variables**.

| Имя | Назначение | Примечание |
|---|---|---|
| `DOCKER_IMAGE` | Базовое имя Docker image | Пример: `recod0/dmkbot:latest` |
| `PORTAINER_URL` | URL Portainer (без `/api`) | Пример: `https://portainer.example.com` |
| `PORTAINER_STACK_ID` | ID stack в Portainer | По умолчанию в скрипте: `17` |
| `ENDPOINT_ID` | Endpoint ID в Portainer | Рекомендуется задать явно |

## Обязательные переменные для deploy-скрипта

`deploy/portainer_update_stack.sh` требует:
- `PORTAINER_API_KEY`
- `TG_TOKEN`
- `API_KEY`
- `WIALON_TOKEN`
- `DOCKER_IMAGE`

Дополнительно:
- `PORTAINER_URL` обязателен для вызова API,
- `PORTAINER_STACK_ID` по умолчанию `17`,
- `ENDPOINT_ID` можно передать через vars (если пустой, скрипт пытается взять из stack details).
