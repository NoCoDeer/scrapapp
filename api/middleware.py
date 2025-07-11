"""
Middleware для FastAPI приложения.
"""
import time
import uuid
from typing import Callable
from datetime import datetime

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
import structlog

from shared.config import settings
from shared.logging_config import get_logger

logger = get_logger(__name__)


class PrometheusMetrics:
    """Метрики для Prometheus."""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        
        # HTTP метрики
        self.http_requests_total = Counter(
            'http_requests_total',
            'Общее количество HTTP запросов',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        self.http_request_duration_seconds = Histogram(
            'http_request_duration_seconds',
            'Время выполнения HTTP запросов',
            ['method', 'endpoint'],
            registry=self.registry
        )
        
        self.http_requests_in_progress = Gauge(
            'http_requests_in_progress',
            'Количество HTTP запросов в процессе выполнения',
            registry=self.registry
        )
        
        # API метрики
        self.api_jobs_total = Gauge(
            'api_jobs_total',
            'Общее количество вакансий в системе',
            registry=self.registry
        )
        
        self.api_companies_total = Gauge(
            'api_companies_total',
            'Общее количество компаний в системе',
            registry=self.registry
        )
        
        self.api_scrape_tasks_total = Counter(
            'api_scrape_tasks_total',
            'Количество запущенных задач скрапинга',
            ['site', 'status'],
            registry=self.registry
        )


# Глобальный экземпляр метрик
prometheus_metrics = PrometheusMetrics()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware для логирования запросов."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Генерируем уникальный ID запроса
        request_id = str(uuid.uuid4())
        
        # Добавляем ID в контекст логирования
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            user_agent=request.headers.get("user-agent"),
            client_ip=self._get_client_ip(request)
        )
        
        start_time = time.time()
        
        logger.info("Начало обработки запроса")
        
        try:
            response = await call_next(request)
            
            duration = time.time() - start_time
            
            logger.info(
                "Запрос обработан",
                status_code=response.status_code,
                duration=duration
            )
            
            # Добавляем заголовки
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(duration)
            
            return response
            
        except Exception as exc:
            duration = time.time() - start_time
            
            logger.error(
                "Ошибка при обработке запроса",
                error=str(exc),
                duration=duration,
                exc_info=True
            )
            
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Получение IP адреса клиента."""
        # Проверяем заголовки прокси
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware для сбора метрик Prometheus."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Увеличиваем счетчик активных запросов
        prometheus_metrics.http_requests_in_progress.inc()
        
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        # Нормализуем путь для метрик (убираем ID и параметры)
        endpoint = self._normalize_path(path)
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            
        except Exception as exc:
            status_code = 500
            raise
            
        finally:
            # Уменьшаем счетчик активных запросов
            prometheus_metrics.http_requests_in_progress.dec()
            
            # Записываем метрики
            duration = time.time() - start_time
            
            prometheus_metrics.http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()
            
            prometheus_metrics.http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
        
        return response
    
    def _normalize_path(self, path: str) -> str:
        """Нормализация пути для метрик."""
        # Заменяем ID на placeholder
        import re
        
        # /api/v1/jobs/123 -> /api/v1/jobs/{id}
        path = re.sub(r'/\d+', '/{id}', path)
        
        # Убираем query параметры
        path = path.split('?')[0]
        
        return path


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware для проверки API ключей."""
    
    # Пути, которые не требуют аутентификации
    EXEMPT_PATHS = {
        "/",
        "/docs",
        "/openapi.json",
        "/api/v1/openapi.json",
        "/api/v1/health",
        "/metrics"
    }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        
        # Проверяем, нужна ли аутентификация для этого пути
        if self._is_exempt_path(path):
            return await call_next(request)
        
        # Получаем API ключ из заголовка
        api_key = request.headers.get("X-API-KEY")
        
        if not api_key:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "API ключ не предоставлен",
                    "detail": "Добавьте заголовок X-API-KEY с вашим API ключом"
                }
            )
        
        # Проверяем валидность API ключа
        if not self._validate_api_key(api_key):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Недействительный API ключ",
                    "detail": "Предоставленный API ключ недействителен или истек"
                }
            )
        
        # Добавляем информацию об API ключе в запрос
        request.state.api_key = api_key
        
        return await call_next(request)
    
    def _is_exempt_path(self, path: str) -> bool:
        """Проверка, освобожден ли путь от аутентификации."""
        if path in self.EXEMPT_PATHS:
            return True
        
        # Проверяем паттерны
        exempt_patterns = [
            "/docs",
            "/redoc",
            "/static/",
            "/favicon.ico"
        ]
        
        for pattern in exempt_patterns:
            if path.startswith(pattern):
                return True
        
        return False
    
    def _validate_api_key(self, api_key: str) -> bool:
        """Валидация API ключа."""
        # Простая проверка по настройкам
        if api_key == settings.api_key:
            return True
        
        # TODO: Здесь можно добавить проверку по базе данных
        # для поддержки множественных API ключей
        
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware для ограничения частоты запросов."""
    
    def __init__(self, app, calls: int = 100, period: int = 60):
        super().__init__(app)
        self.calls = calls  # Количество запросов
        self.period = period  # Период в секундах
        self.clients = {}  # Хранилище для отслеживания клиентов
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Очищаем старые записи
        self._cleanup_old_entries(current_time)
        
        # Проверяем лимит для клиента
        if client_ip in self.clients:
            client_requests = self.clients[client_ip]
            
            # Фильтруем запросы в текущем периоде
            recent_requests = [
                req_time for req_time in client_requests
                if current_time - req_time < self.period
            ]
            
            if len(recent_requests) >= self.calls:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Превышен лимит запросов",
                        "detail": f"Максимум {self.calls} запросов в {self.period} секунд"
                    },
                    headers={
                        "Retry-After": str(self.period),
                        "X-RateLimit-Limit": str(self.calls),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(current_time + self.period))
                    }
                )
            
            self.clients[client_ip] = recent_requests + [current_time]
        else:
            self.clients[client_ip] = [current_time]
        
        response = await call_next(request)
        
        # Добавляем заголовки rate limit
        if client_ip in self.clients:
            remaining = max(0, self.calls - len(self.clients[client_ip]))
            response.headers["X-RateLimit-Limit"] = str(self.calls)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(current_time + self.period))
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Получение IP адреса клиента."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _cleanup_old_entries(self, current_time: float):
        """Очистка старых записей."""
        for client_ip in list(self.clients.keys()):
            self.clients[client_ip] = [
                req_time for req_time in self.clients[client_ip]
                if current_time - req_time < self.period
            ]
            
            if not self.clients[client_ip]:
                del self.clients[client_ip]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware для добавления заголовков безопасности."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Добавляем заголовки безопасности
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Content Security Policy
        if not response.headers.get("Content-Security-Policy"):
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https:; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "connect-src 'self'"
            )
            response.headers["Content-Security-Policy"] = csp
        
        return response


# Функция для обновления метрик из базы данных
async def update_database_metrics():
    """Обновление метрик из базы данных."""
    try:
        from shared.database import get_db_session
        from shared.models import Job, Company
        from sqlalchemy import func
        
        with get_db_session() as session:
            # Обновляем количество вакансий
            jobs_count = session.query(func.count(Job.id)).scalar()
            prometheus_metrics.api_jobs_total.set(jobs_count)
            
            # Обновляем количество компаний
            companies_count = session.query(func.count(Company.id)).scalar()
            prometheus_metrics.api_companies_total.set(companies_count)
            
    except Exception as e:
        logger.error(f"Ошибка обновления метрик: {e}")
