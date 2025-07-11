# Dockerfile для скрапера
FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libjpeg-dev \
    libpng-dev \
    libgif-dev \
    libtiff-dev \
    libopenjp2-7-dev \
    curl \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Node.js для Playwright
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs

# Создаем пользователя для приложения
RUN useradd --create-home --shell /bin/bash app

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Устанавливаем Playwright браузеры
RUN playwright install chromium && \
    playwright install-deps chromium

# Копируем shared модули
COPY ../shared ./shared

# Копируем код скрапера
COPY . ./scraper

# Создаем директории для логов и данных
RUN mkdir -p /app/logs /app/data && \
    chown -R app:app /app

# Переключаемся на пользователя app
USER app

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV SCRAPY_SETTINGS_MODULE=scraper.settings

# Команда по умолчанию (Celery worker)
CMD ["celery", "-A", "scraper.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
