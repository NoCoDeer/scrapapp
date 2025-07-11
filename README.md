# Job Scraper - Система скрапинга вакансий

Полнофункциональная система для скрапинга и анализа вакансий с различных сайтов объявлений с поддержкой ротации прокси и ограничения скорости.

## 🚀 Возможности

- **Скрапинг вакансий** с множественных сайтов с использованием Scrapy и Playwright
- **Ротация прокси** и рандомизация User-Agent для обхода блокировок
- **Очередь задач** на основе Celery с Redis для асинхронной обработки
- **REST API** на FastAPI с автоматической документацией
- **React фронтенд** с современным UI на Ant Design
- **Админ-панель** для управления системой и мониторинга
- **Полнотекстовый поиск** с Elasticsearch
- **Мониторинг** с Prometheus и Sentry
- **Контейнеризация** с Docker и Kubernetes
- **CI/CD** с GitHub Actions

## 📋 Архитектура

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React SPA     │    │   FastAPI       │    │   Scrapy        │
│   (Frontend)    │◄──►│   (API Server)  │◄──►│   (Scraper)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │   PostgreSQL    │              │
         │              │   (Database)    │              │
         │              └─────────────────┘              │
         │                       │                       │
         │              ┌─────────────────┐              │
         └──────────────┤     Redis       ├──────────────┘
                        │ (Cache/Queue)   │
                        └─────────────────┘
                                 │
                        ┌─────────────────┐
                        │  Elasticsearch  │
                        │    (Search)     │
                        └─────────────────┘
```

## 🛠 Технологический стек

### Backend
- **Python 3.11+** - основной язык
- **Scrapy** - фреймворк для веб-скрапинга
- **Playwright** - для сайтов с динамическим контентом
- **FastAPI** - асинхронный веб-фреймворк
- **Celery 5.x** - очередь задач
- **SQLAlchemy** - ORM для работы с БД
- **Alembic** - миграции БД
- **Pydantic** - валидация данных

### Frontend
- **React 18** - UI библиотека
- **TypeScript** - типизированный JavaScript
- **Vite** - сборщик и dev-сервер
- **Ant Design** - UI компоненты
- **React Query** - управление состоянием сервера
- **React Router** - маршрутизация

### Инфраструктура
- **PostgreSQL** - основная база данных
- **Redis** - кеш и брокер сообщений
- **Elasticsearch** - полнотекстовый поиск
- **Docker** - контейнеризация
- **Kubernetes** - оркестрация
- **Nginx** - веб-сервер и прокси

### Мониторинг
- **Prometheus** - метрики
- **Sentry** - отслеживание ошибок
- **Structured logging** - логирование в JSON

## 🚀 Быстрый старт

### Предварительные требования

- Docker и Docker Compose
- Python 3.11+ (для локальной разработки)
- Node.js 18+ (для фронтенда)

### Запуск с Docker Compose

1. **Клонируйте репозиторий:**
```bash
git clone <repository-url>
cd scrapapp
```

2. **Скопируйте файл окружения:**
```bash
cp .env.example .env
```

3. **Отредактируйте переменные окружения в `.env`:**
```bash
# Основные настройки
ENVIRONMENT=development
SECRET_KEY=your-secret-key-here
API_KEY=your-api-key-here

# База данных
DB_HOST=postgres
DB_PORT=5432
DB_NAME=jobscraper
DB_USER=jobscraper
DB_PASSWORD=password

# Redis
REDIS_URL=redis://redis:6379/0

# Elasticsearch
ELASTICSEARCH_URL=http://elasticsearch:9200

# Прокси (опционально)
PROXIES=http://proxy1:8080,http://proxy2:8080

# Sentry (опционально)
SENTRY_DSN=your-sentry-dsn
```

4. **Запустите все сервисы:**
```bash
docker-compose up -d
```

5. **Выполните миграции базы данных:**
```bash
docker-compose exec api alembic upgrade head
```

6. **Создайте индексы Elasticsearch:**
```bash
docker-compose exec api python -c "
from shared.elasticsearch import setup_elasticsearch
setup_elasticsearch()
"
```

### Доступ к сервисам

- **Фронтенд:** http://localhost:3000
- **Админ-панель:** http://localhost:3001
- **API документация:** http://localhost:8000/docs
- **API:** http://localhost:8000/api
- **Prometheus:** http://localhost:9090
- **Grafana:** http://localhost:3002

## 📖 Использование

### Запуск скрапинга

#### Через API:
```bash
curl -X POST "http://localhost:8000/admin/scrape/trigger" \
  -H "X-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"site": "site1.com", "max_pages": 5}'
```

#### Через CLI:
```bash
# Запуск скрапинга конкретного сайта
python manage.py crawl --site site1.com

# Запуск всех пауков
python manage.py crawl --all

# Запуск с ограничением страниц
python manage.py crawl --site site1.com --max-pages 10
```

### API эндпоинты

#### Вакансии
- `GET /jobs` - список вакансий с фильтрами
- `GET /jobs/{id}` - детали вакансии
- `GET /jobs/stats/summary` - статистика по вакансиям

#### Компании
- `GET /companies` - список компаний
- `GET /companies/{id}` - детали компании
- `GET /companies/{id}/jobs` - вакансии компании

#### Поиск
- `GET /search?q=python` - поиск вакансий
- `GET /search/suggestions?q=py` - автодополнение
- `GET /search/trending` - популярные запросы

#### Администрирование
- `GET /admin/stats` - общая статистика
- `POST /admin/scrape/trigger` - запуск скрапинга
- `GET /admin/scrape/logs` - логи скрапинга
- `GET /admin/celery/workers` - статус воркеров

### Примеры фильтрации

```bash
# Поиск Python вакансий в Москве
curl "http://localhost:8000/jobs?keyword=python&location=москва"

# Удаленные вакансии с зарплатой от 100000
curl "http://localhost:8000/jobs?remote_allowed=true&salary_min=100000"

# Вакансии за последнюю неделю
curl "http://localhost:8000/jobs?date_from=2024-01-01"
```

## 🔧 Разработка

### Локальная разработка

1. **Установите зависимости Python:**
```bash
cd api
pip install -r requirements.txt

cd ../scraper
pip install -r requirements.txt
```

2. **Установите зависимости Node.js:**
```bash
cd frontend
npm install
```

3. **Запустите базы данных:**
```bash
docker-compose up -d postgres redis elasticsearch
```

4. **Запустите сервисы:**
```bash
# API сервер
cd api
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Celery worker
cd scraper
celery -A celery_app worker --loglevel=info

# Celery beat (планировщик)
cd scraper
celery -A celery_app beat --loglevel=info

# Frontend
cd frontend
npm run dev
```

### Добавление нового сайта для скрапинга

1. **Создайте новый паук:**
```python
# scraper/spiders/newsite_spider.py
import scrapy
from scraper.items import JobItem

class NewSiteSpider(scrapy.Spider):
    name = 'newsite'
    allowed_domains = ['newsite.com']
    start_urls = ['https://newsite.com/jobs']

    def parse(self, response):
        # Извлечение ссылок на вакансии
        job_links = response.css('.job-link::attr(href)').getall()
        for link in job_links:
            yield response.follow(link, self.parse_job)

    def parse_job(self, response):
        yield JobItem(
            job_title=response.css('h1::text').get(),
            company_name=response.css('.company::text').get(),
            location=response.css('.location::text').get(),
            description=response.css('.description::text').get(),
            salary=response.css('.salary::text').get(),
            job_url=response.url,
            source_site='newsite.com'
        )
```

2. **Добавьте задачу в Celery:**
```python
# scraper/tasks.py
@celery_app.task(bind=True)
def crawl_newsite(self, max_pages: int = 5):
    return run_spider('newsite', max_pages=max_pages)
```

3. **Добавьте в планировщик:**
```python
# scraper/celery_app.py
celery_app.conf.beat_schedule.update({
    'crawl-newsite': {
        'task': 'scraper.tasks.crawl_newsite',
        'schedule': crontab(minute=0, hour='*/3'),  # каждые 3 часа
        'kwargs': {'max_pages': 10}
    }
})
```

### Тестирование

```bash
# Python тесты
pytest

# Frontend тесты
cd frontend
npm test

# Линтинг
flake8 .
black --check .
isort --check .

cd frontend
npm run lint
```

## 🚀 Развертывание

### Docker Compose (Production)

```bash
# Сборка образов
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# Запуск в production режиме
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Kubernetes

1. **Создайте namespace:**
```bash
kubectl apply -f k8s/namespace.yaml
```

2. **Примените конфигурацию:**
```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/
```

3. **Проверьте статус:**
```bash
kubectl get pods -n job-scraper
kubectl get services -n job-scraper
```

### CI/CD с GitHub Actions

Пайплайн автоматически:
- Запускает тесты и линтинг
- Собирает Docker образы
- Сканирует на уязвимости
- Развертывает в staging и production

Необходимые секреты в GitHub:
- `DOCKER_USERNAME` - имя пользователя Docker Hub
- `DOCKER_PASSWORD` - пароль Docker Hub
- `KUBE_CONFIG_STAGING` - конфигурация kubectl для staging
- `KUBE_CONFIG_PRODUCTION` - конфигурация kubectl для production
- `SLACK_WEBHOOK` - webhook для уведомлений

## 📊 Мониторинг

### Метрики Prometheus

Доступны по адресу `/metrics`:
- Количество обработанных запросов
- Время ответа API
- Статус воркеров Celery
- Количество ошибок

### Логирование

Все логи структурированы в JSON формате:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "api",
  "message": "Job created",
  "job_id": 123,
  "user_id": "user123"
}
```

### Sentry

Автоматическое отслеживание ошибок во всех сервисах с контекстом и трассировкой.

## 🔒 Безопасность

- API ключи для аутентификации
- Валидация всех входных данных
- Rate limiting
- CORS настройки
- Безопасные заголовки HTTP
- Сканирование уязвимостей в CI/CD

## 🤝 Участие в разработке

1. Форкните репозиторий
2. Создайте ветку для фичи (`git checkout -b feature/amazing-feature`)
3. Зафиксируйте изменения (`git commit -m 'Add amazing feature'`)
4. Отправьте в ветку (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📝 Лицензия

Этот проект лицензирован под MIT License - см. файл [LICENSE](LICENSE) для деталей.

## 🆘 Поддержка

- Создайте [Issue](https://github.com/your-repo/issues) для багов и предложений
- Проверьте [документацию API](http://localhost:8000/docs)
- Посмотрите [примеры использования](examples/)

## 📈 Roadmap

- [ ] Поддержка дополнительных сайтов
- [ ] ML модели для классификации вакансий
- [ ] Telegram бот для уведомлений
- [ ] Экспорт данных в различные форматы
- [ ] Аналитика и дашборды
- [ ] Мобильное приложение
