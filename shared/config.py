"""
Общие настройки конфигурации для всех сервисов.
"""
import os
from typing import List, Optional
from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """Основные настройки приложения."""
    
    # Database
    db_url: str = Field(..., env="DB_URL")
    db_host: str = Field("localhost", env="DB_HOST")
    db_port: int = Field(5432, env="DB_PORT")
    db_name: str = Field("jobscraper", env="DB_NAME")
    db_user: str = Field("postgres", env="DB_USER")
    db_password: str = Field("password", env="DB_PASSWORD")
    
    # Redis
    redis_url: str = Field(..., env="REDIS_URL")
    redis_host: str = Field("localhost", env="REDIS_HOST")
    redis_port: int = Field(6379, env="REDIS_PORT")
    redis_db: int = Field(0, env="REDIS_DB")
    
    # Elasticsearch
    elasticsearch_url: str = Field("http://localhost:9200", env="ELASTICSEARCH_URL")
    elasticsearch_index: str = Field("jobs", env="ELASTICSEARCH_INDEX")
    
    # API
    api_key: str = Field(..., env="API_KEY")
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000, env="API_PORT")
    cors_origins: List[str] = Field(
        ["http://localhost:3000", "http://localhost:5173"],
        env="CORS_ORIGINS"
    )
    
    # Scraper
    proxies: List[str] = Field([], env="PROXIES")
    user_agents: List[str] = Field([], env="USER_AGENTS")
    delay_min: int = Field(1, env="DELAY_MIN")
    delay_max: int = Field(5, env="DELAY_MAX")
    concurrent_requests: int = Field(8, env="CONCURRENT_REQUESTS")
    download_timeout: int = Field(30, env="DOWNLOAD_TIMEOUT")
    
    # Celery
    celery_broker_url: str = Field(..., env="CELERY_BROKER_URL")
    celery_result_backend: str = Field(..., env="CELERY_RESULT_BACKEND")
    celery_timezone: str = Field("UTC", env="CELERY_TIMEZONE")
    
    # Monitoring
    sentry_dsn: Optional[str] = Field(None, env="SENTRY_DSN")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    prometheus_port: int = Field(9090, env="PROMETHEUS_PORT")
    
    # Security
    secret_key: str = Field(..., env="SECRET_KEY")
    algorithm: str = Field("HS256", env="ALGORITHM")
    access_token_expire_minutes: int = Field(30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Development
    debug: bool = Field(False, env="DEBUG")
    environment: str = Field("production", env="ENVIRONMENT")
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("proxies", pre=True)
    def parse_proxies(cls, v):
        if isinstance(v, str):
            return [proxy.strip() for proxy in v.split(",") if proxy.strip()]
        return v
    
    @validator("user_agents", pre=True)
    def parse_user_agents(cls, v):
        if isinstance(v, str):
            return [ua.strip() for ua in v.split(",") if ua.strip()]
        return v or [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0"
        ]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class ScraperSettings(Settings):
    """Настройки специфичные для скрапера."""
    
    # Scrapy settings
    scrapy_settings = {
        'BOT_NAME': 'jobscraper',
        'SPIDER_MODULES': ['scraper.spiders'],
        'NEWSPIDER_MODULE': 'scraper.spiders',
        'ROBOTSTXT_OBEY': False,
        'CONCURRENT_REQUESTS': 16,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'COOKIES_ENABLED': True,
        'TELNETCONSOLE_ENABLED': False,
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en',
        },
        'ITEM_PIPELINES': {
            'scraper.pipelines.ValidationPipeline': 300,
            'scraper.pipelines.DuplicationPipeline': 400,
            'scraper.pipelines.DatabasePipeline': 500,
            'scraper.pipelines.ElasticsearchPipeline': 600,
        },
        'DOWNLOADER_MIDDLEWARES': {
            'scraper.middlewares.ProxyMiddleware': 350,
            'scraper.middlewares.UserAgentMiddleware': 400,
            'scraper.middlewares.RetryMiddleware': 500,
        },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 1,
        'AUTOTHROTTLE_MAX_DELAY': 60,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,
        'AUTOTHROTTLE_DEBUG': False,
        'HTTPCACHE_ENABLED': False,
        'LOG_LEVEL': 'INFO',
    }


class APISettings(Settings):
    """Настройки специфичные для API."""
    
    # FastAPI settings
    title: str = "Job Scraper API"
    description: str = "API для управления данными о вакансиях и компаниях"
    version: str = "1.0.0"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"


# Глобальные экземпляры настроек
settings = Settings()
scraper_settings = ScraperSettings()
api_settings = APISettings()


def get_database_url() -> str:
    """Получить URL базы данных."""
    return settings.db_url


def get_redis_url() -> str:
    """Получить URL Redis."""
    return settings.redis_url


def get_elasticsearch_url() -> str:
    """Получить URL Elasticsearch."""
    return settings.elasticsearch_url


def is_development() -> bool:
    """Проверить, запущено ли приложение в режиме разработки."""
    return settings.environment.lower() in ("development", "dev", "local")


def is_production() -> bool:
    """Проверить, запущено ли приложение в режиме производства."""
    return settings.environment.lower() in ("production", "prod")
