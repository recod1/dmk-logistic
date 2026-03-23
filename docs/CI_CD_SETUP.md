# CI/CD setup (GitHub Actions + Docker Hub + Portainer)

## Что делает workflow

Файл `.github/workflows/docker-publish.yml`:

1. Запускается при:
   - `push` в `main`,
   - `push` тега,
   - ручном запуске (`workflow_dispatch`).
2. Логинится в Docker Hub.
3. Собирает и пушит два образа:
   - `recod0/dmk-logistic-api` (`docker/api/Dockerfile`),
   - `recod0/dmk-logistic-web` (`docker/web/Dockerfile`).
4. Публикует теги:
   - `latest`,
   - `sha-<short_sha>`.
5. Использует кэш сборки Buildx (`cache-from/cache-to`, `type=gha`).

## GitHub Secrets

Добавляются в Settings → Secrets and variables → Actions → **Secrets**.

| Имя | Назначение |
|---|---|
| `DOCKERHUB_USERNAME` | Логин Docker Hub |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token |

## Portainer deploy (без curl/API вызовов)

Stack обновляется в самом Portainer за счёт pull новых образов, а не через API-скрипты.

Рекомендуемая схема:

1. Создать/обновить stack в Portainer из Git-репозитория.
2. Использовать compose-файл: `deploy/portainer/docker-compose.portainer.yml`.
3. Настроить переменные stack environment:
   - `API_IMAGE`, `WEB_IMAGE`;
   - `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`;
   - `JWT_SECRET`, а также при необходимости `API_KEY`, `TG_TOKEN`, `WIALON_TOKEN`, `ADMIN_PASSWORD`.
4. Включить автообновление:
   - через webhook update, или
   - через periodic pull / re-pull image + redeploy.

## Проверка после публикации

1. Убедиться, что в Docker Hub появились теги:
   - `recod0/dmk-logistic-api:latest`,
   - `recod0/dmk-logistic-api:sha-<...>`,
   - `recod0/dmk-logistic-web:latest`,
   - `recod0/dmk-logistic-web:sha-<...>`.
2. В Portainer выполнить pull/redeploy (или дождаться автообновления).
