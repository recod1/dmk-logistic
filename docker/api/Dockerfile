FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ARG CACHE_BUST=unset
ARG REQUIREMENTS_HASH=unset

COPY requirements.txt /app/requirements.txt
RUN echo "cache_bust=${CACHE_BUST} requirements_hash=${REQUIREMENTS_HASH}" \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN chmod +x /app/start.sh

EXPOSE 8000

# Запускаем миграции Postgres и затем стартуем legacy+new API (и бота, если включён TG_TOKEN).
CMD ["bash", "-lc", "alembic upgrade head && ./start.sh"]

