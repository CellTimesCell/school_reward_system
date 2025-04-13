FROM python:3.10-slim

WORKDIR /app

# Установка зависимостей для PostgreSQL
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование файлов зависимостей
COPY requirements.txt .

# Установка зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование всего проекта
COPY . .

# Создание директорий
RUN mkdir -p app/static/uploads logs

# Установка переменных окружения
ENV FLASK_APP=run.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Экспозиция порта
EXPOSE 5000

# Проверка здоровья
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Инициализация базы данных и запуск приложения
CMD flask db upgrade && \
    uwsgi --http 0.0.0.0:5000 \
    --wsgi-file run.py \
    --callable app \
    --processes 4 \
    --threads 2 \
    --master \
    --vacuum \
    --die-on-term \
    --logto /app/logs/uwsgi.log