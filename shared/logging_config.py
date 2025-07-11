"""
Конфигурация логирования для всех сервисов.
"""
import logging
import logging.config
import sys
from typing import Dict, Any
import json
from datetime import datetime

from .config import settings


class JSONFormatter(logging.Formatter):
    """Форматтер для вывода логов в JSON формате."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Добавляем дополнительные поля если они есть
        if hasattr(record, 'spider'):
            log_entry['spider'] = record.spider
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        
        # Добавляем информацию об исключении если есть
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)


def get_logging_config() -> Dict[str, Any]:
    """Получить конфигурацию логирования."""
    
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
            'detailed': {
                'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s'
            },
            'json': {
                '()': JSONFormatter,
            },
        },
        'handlers': {
            'console': {
                'level': settings.log_level,
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
                'stream': sys.stdout,
            },
            'file': {
                'level': settings.log_level,
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'detailed',
                'filename': 'logs/app.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
            },
            'json_file': {
                'level': settings.log_level,
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'json',
                'filename': 'logs/app.json',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
            },
        },
        'loggers': {
            'scraper': {
                'handlers': ['console', 'file', 'json_file'],
                'level': settings.log_level,
                'propagate': False,
            },
            'api': {
                'handlers': ['console', 'file', 'json_file'],
                'level': settings.log_level,
                'propagate': False,
            },
            'celery': {
                'handlers': ['console', 'file', 'json_file'],
                'level': settings.log_level,
                'propagate': False,
            },
            'sqlalchemy.engine': {
                'handlers': ['file'],
                'level': 'WARNING',
                'propagate': False,
            },
            'elasticsearch': {
                'handlers': ['file'],
                'level': 'WARNING',
                'propagate': False,
            },
        },
        'root': {
            'level': settings.log_level,
            'handlers': ['console', 'file'],
        }
    }
    
    # В режиме разработки используем более простое форматирование
    if settings.debug:
        config['handlers']['console']['formatter'] = 'detailed'
    
    return config


def setup_logging():
    """Настроить логирование для приложения."""
    import os
    
    # Создаем директорию для логов если её нет
    os.makedirs('logs', exist_ok=True)
    
    # Применяем конфигурацию
    logging.config.dictConfig(get_logging_config())
    
    # Настраиваем Sentry если DSN указан
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
            from sentry_sdk.integrations.redis import RedisIntegration
            
            sentry_logging = LoggingIntegration(
                level=logging.INFO,        # Capture info and above as breadcrumbs
                event_level=logging.ERROR  # Send errors as events
            )
            
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                integrations=[
                    sentry_logging,
                    SqlalchemyIntegration(),
                    RedisIntegration(),
                ],
                traces_sample_rate=0.1,
                environment=settings.environment,
            )
            
            logging.info("Sentry инициализирован успешно")
        except ImportError:
            logging.warning("Sentry SDK не установлен, мониторинг ошибок недоступен")
        except Exception as e:
            logging.error(f"Ошибка инициализации Sentry: {e}")


def get_logger(name: str) -> logging.Logger:
    """Получить логгер с указанным именем."""
    return logging.getLogger(name)


class LoggerMixin:
    """Миксин для добавления логгера в классы."""
    
    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(self.__class__.__module__ + '.' + self.__class__.__name__)


def log_function_call(func):
    """Декоратор для логирования вызовов функций."""
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        logger.debug(f"Вызов функции {func.__name__} с args={args}, kwargs={kwargs}")
        
        try:
            result = func(*args, **kwargs)
            logger.debug(f"Функция {func.__name__} выполнена успешно")
            return result
        except Exception as e:
            logger.error(f"Ошибка в функции {func.__name__}: {e}")
            raise
    
    return wrapper


def log_execution_time(func):
    """Декоратор для логирования времени выполнения функций."""
    import time
    
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"Функция {func.__name__} выполнена за {execution_time:.2f} секунд")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Функция {func.__name__} завершилась с ошибкой за {execution_time:.2f} секунд: {e}")
            raise
    
    return wrapper
