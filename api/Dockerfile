FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

ARG CACHE_BUST=unset
ARG REQUIREMENTS_HASH=unset

COPY api/requirements.txt /app/requirements.txt
RUN echo "cache_bust=${CACHE_BUST} requirements_hash=${REQUIREMENTS_HASH}" \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY shared/ /app/
COPY bot/keyboards /app/keyboards
COPY api/ /app/

RUN chmod +x /app/start.sh

EXPOSE 8000

CMD ["bash", "-lc", "alembic upgrade head && ./start.sh"]
