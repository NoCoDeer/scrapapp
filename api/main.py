"""
Главное приложение FastAPI для API сервера.
"""
import sys
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
import uvicorn

# Добавляем путь к shared модулям
sys.path.append(str(Path(__file__).parent.parent))

from shared.config import settings
from shared.logging_config import setup_logging, get_logger
from api.middleware import APIKeyMiddleware, PrometheusMiddleware, LoggingMiddleware
from api.routers import jobs, companies, search, admin, health
from api.schemas import ErrorResponse

# Настройка логирования
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    # Startup
    logger.info("Запуск API сервера...")
    
    # Инициализация Sentry если настроен
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
            
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                integrations=[
                    FastApiIntegration(auto_enabling_integrations=False),
                    SqlalchemyIntegration(),
                ],
                traces_sample_rate=0.1,
                environment=settings.environment,
            )
            logger.info("Sentry инициализирован")
        except ImportError:
            logger.warning("Sentry SDK не установлен")
    
    # Проверка подключения к базе данных
    try:
        from shared.database import get_db_session
        with get_db_session() as session:
            session.execute("SELECT 1")
        logger.info("Подключение к базе данных успешно")
    except Exception as e:
        logger.error(f"Ошибка подключения к базе данных: {e}")
    
    logger.info("API сервер запущен успешно")
    
    yield
    
    # Shutdown
    logger.info("Остановка API сервера...")


# Создание приложения FastAPI
app = FastAPI(
    title="Job Scraper API",
    description="API для доступа к данным скрапинга вакансий",
    version="1.0.0",
    docs_url=None,  # Отключаем стандартные docs
    redoc_url=None,  # Отключаем redoc
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.api_settings.allowed_hosts
)

# Добавляем кастомные middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_middleware(APIKeyMiddleware)


# Обработчики ошибок
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Обработчик HTTP ошибок."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            detail=getattr(exc, 'detail', None)
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Обработчик общих ошибок."""
    logger.error(f"Необработанная ошибка: {exc}", exc_info=True)
    
    # Отправляем в Sentry если настроен
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc)
        except ImportError:
            pass
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Внутренняя ошибка сервера",
            detail=str(exc) if settings.environment == "development" else None
        ).model_dump()
    )


# Подключение роутеров
app.include_router(
    health.router,
    prefix="/api/v1",
    tags=["health"]
)

app.include_router(
    jobs.router,
    prefix="/api/v1/jobs",
    tags=["jobs"]
)

app.include_router(
    companies.router,
    prefix="/api/v1/companies",
    tags=["companies"]
)

app.include_router(
    search.router,
    prefix="/api/v1/search",
    tags=["search"]
)

app.include_router(
    admin.router,
    prefix="/api/v1/admin",
    tags=["admin"]
)


# Кастомная документация
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Кастомная страница документации."""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )


def custom_openapi():
    """Кастомная схема OpenAPI."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Добавляем информацию о безопасности
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-KEY"
        }
    }
    
    # Применяем безопасность ко всем эндпоинтам кроме health и docs
    for path, path_item in openapi_schema["paths"].items():
        if not path.startswith("/api/v1/health") and not path.startswith("/docs"):
            for operation in path_item.values():
                if isinstance(operation, dict) and "operationId" in operation:
                    operation["security"] = [{"ApiKeyAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Корневой эндпоинт
@app.get("/", include_in_schema=False)
async def root():
    """Корневой эндпоинт."""
    return {
        "message": "Job Scraper API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
        "timestamp": datetime.utcnow().isoformat()
    }


# Эндпоинт для метрик Prometheus
@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Метрики для Prometheus."""
    from api.middleware import prometheus_metrics
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    
    return Response(
        generate_latest(prometheus_metrics.registry),
        media_type=CONTENT_TYPE_LATEST
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_settings.host,
        port=settings.api_settings.port,
        reload=settings.environment == "development",
        log_level="info",
        access_log=True
    )
