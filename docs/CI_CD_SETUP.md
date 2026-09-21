# CI/CD setup (GitHub Actions + Docker Hub + Portainer)

## Что делает workflow

Файл `.github/workflows/docker-publish.yml`:

1. Запускается при `push` в `main`, push тега или ручном `workflow_dispatch`.
2. Логинится в Docker Hub (`DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN`).
3. Собирает и пушит три образа:
   - `recod0/dmk-logistic-api` (`api/Dockerfile`),
   - `recod0/dmk-logistic-web` (`web/Dockerfile`),
   - `recod0/dmk-logistic-bot` (`bot/Dockerfile`).
4. Публикует теги `latest` и `sha-<short_sha>`.
5. Пишет итог в job **Build result** и в GitHub Step Summary.

Проверка запуска:

```bash
gh run list --workflow="Docker publish (api + web + bot)" --branch main --limit 5
gh run watch <run-id>
```

## GitHub Secrets

Settings → Secrets and variables → Actions → **Secrets**.

| Имя | Назначение |
|---|---|
| `DOCKERHUB_USERNAME` | Логин Docker Hub |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token |

## Portainer

Stack обновляется pull'ом новых образов.

1. Compose: `deploy/portainer/docker-compose.portainer.yml`.
2. Переменные: `API_IMAGE`, `WEB_IMAGE`, `BOT_IMAGE`, Postgres/JWT и токены.
3. Автообновление: webhook или periodic pull + redeploy.
