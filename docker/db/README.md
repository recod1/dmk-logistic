# Database container

Для сервиса `db` используется официальный образ Postgres:

```yaml
image: postgres:16-alpine
```

Отдельный `Dockerfile` для БД в проекте не требуется.

Если понадобятся init-скрипты, добавьте их в `docker/db/init/` и подключите volume в `docker-compose.yml`:

```yaml
volumes:
  - ./docker/db/init:/docker-entrypoint-initdb.d:ro
```

