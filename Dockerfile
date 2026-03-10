FROM python:3.12-slim
WORKDIR /olymp

COPY . .

RUN pip install -r requirements.txt

# Скрипт запуска бота и API в одном контейнере
RUN chmod +x start.sh

# Бот — polling; API — порт 8000 (при запуске контейнера пробросьте: -p 8000:8000)
EXPOSE 8000

CMD ["./start.sh"]
