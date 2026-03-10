#!/bin/sh
# Запуск бота и API в одном контейнере

set -e

echo "Starting bot in background..."
python app.py &
BOTPID=$!

echo "Starting API server on 0.0.0.0:8000..."
uvicorn api.api_server:app --host 0.0.0.0 --port 8000 &
UVIPID=$!

# При завершении контейнера останавливаем оба процесса
trap 'echo "Shutting down..."; kill $BOTPID $UVIPID 2>/dev/null; wait $BOTPID $UVIPID 2>/dev/null; exit 0' TERM INT

# Ждём завершения uvicorn (основной процесс); при его выходе останавливаем бота
wait $UVIPID
EXIT=$?
kill $BOTPID 2>/dev/null || true
wait $BOTPID 2>/dev/null || true
exit $EXIT
