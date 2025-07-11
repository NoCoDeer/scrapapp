"""
Celery приложение для управления задачами скрапинга.
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_prerun, task_postrun, task_failure

# Добавляем путь к shared модулям
sys.path.append(str(Path(__file__).parent.parent))

from shared.config import settings
from shared.logging_config import setup_logging, get_logger
from shared.database import get_db_session
from shared.models import ScrapeLog

# Настройка логирования
setup_logging()
logger = get_logger(__name__)

# Создание Celery приложения
app = Celery('jobscraper')

# Конфигурация Celery
app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    timezone=settings.celery_timezone,
    enable_utc=True,
    
    # Настройки задач
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Настройки воркеров
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    
    # Настройки результатов
    result_expires=3600,
    task_ignore_result=False,
    
    # Настройки маршрутизации
    task_routes={
        'scraper.tasks.crawl_site': {'queue': 'scraping'},
        'scraper.tasks.cleanup_old_data': {'queue': 'maintenance'},
        'scraper.tasks.generate_stats': {'queue': 'analytics'},
    },
    
    # Настройки повторов
    task_retry_delay=60,
    task_max_retries=3,
    
    # Мониторинг
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Безопасность
    worker_hijack_root_logger=False,
    worker_log_color=False,
)

# Расписание периодических задач
app.conf.beat_schedule = {
    # Скрапинг site1.com каждый час
    'crawl-site1-hourly': {
        'task': 'scraper.tasks.crawl_site',
        'schedule': crontab(minute=0),  # Каждый час в начале часа
        'args': ('site1',),
        'options': {'queue': 'scraping'}
    },
    
    # Скрапинг site2.com каждые 2 часа
    'crawl-site2-bi-hourly': {
        'task': 'scraper.tasks.crawl_site',
        'schedule': crontab(minute=0, hour='*/2'),  # Каждые 2 часа
        'args': ('site2',),
        'options': {'queue': 'scraping'}
    },
    
    # Очистка старых данных каждый день в 2:00
    'cleanup-old-data-daily': {
        'task': 'scraper.tasks.cleanup_old_data',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'maintenance'}
    },
    
    # Генерация статистики каждые 6 часов
    'generate-stats-6hourly': {
        'task': 'scraper.tasks.generate_stats',
        'schedule': crontab(minute=0, hour='*/6'),
        'options': {'queue': 'analytics'}
    },
    
    # Проверка здоровья системы каждые 30 минут
    'health-check-30min': {
        'task': 'scraper.tasks.health_check',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'maintenance'}
    },
}


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Обработчик перед выполнением задачи."""
    logger.info(f"Начало выполнения задачи {task.name} (ID: {task_id})")
    
    # Создаем запись в логах скрапинга для задач скрапинга
    if task.name == 'scraper.tasks.crawl_site' and args:
        site = args[0]
        spider_name = f"{site}_spider"
        
        try:
            with get_db_session() as session:
                scrape_log = ScrapeLog(
                    site=site,
                    spider_name=spider_name,
                    start_time=datetime.utcnow(),
                    status='running'
                )
                session.add(scrape_log)
                session.commit()
                
                # Сохраняем ID лога в контексте задачи
                task.request.scrape_log_id = scrape_log.id
                
        except Exception as e:
            logger.error(f"Ошибка создания лога скрапинга: {e}")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
    """Обработчик после выполнения задачи."""
    logger.info(f"Завершение задачи {task.name} (ID: {task_id}) со статусом {state}")
    
    # Обновляем лог скрапинга
    if hasattr(task.request, 'scrape_log_id'):
        try:
            with get_db_session() as session:
                scrape_log = session.get(ScrapeLog, task.request.scrape_log_id)
                if scrape_log:
                    scrape_log.end_time = datetime.utcnow()
                    scrape_log.status = 'completed' if state == 'SUCCESS' else 'failed'
                    
                    if scrape_log.start_time:
                        duration = (scrape_log.end_time - scrape_log.start_time).total_seconds()
                        scrape_log.duration_seconds = duration
                    
                    # Извлекаем статистику из результата
                    if isinstance(retval, dict):
                        scrape_log.items_scraped = retval.get('items_scraped', 0)
                        scrape_log.items_dropped = retval.get('items_dropped', 0)
                        scrape_log.errors_count = retval.get('errors_count', 0)
                    
                    session.commit()
                    
        except Exception as e:
            logger.error(f"Ошибка обновления лога скрапинга: {e}")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Обработчик ошибок задач."""
    logger.error(f"Ошибка в задаче {sender.name} (ID: {task_id}): {exception}")
    
    # Обновляем лог скрапинга при ошибке
    if hasattr(sender.request, 'scrape_log_id'):
        try:
            with get_db_session() as session:
                scrape_log = session.get(ScrapeLog, sender.request.scrape_log_id)
                if scrape_log:
                    scrape_log.end_time = datetime.utcnow()
                    scrape_log.status = 'failed'
                    scrape_log.error_message = str(exception)
                    scrape_log.errors_count = 1
                    
                    if scrape_log.start_time:
                        duration = (scrape_log.end_time - scrape_log.start_time).total_seconds()
                        scrape_log.duration_seconds = duration
                    
                    session.commit()
                    
        except Exception as e:
            logger.error(f"Ошибка обновления лога скрапинга при ошибке: {e}")


# Автоматическое обнаружение задач
app.autodiscover_tasks(['scraper.tasks'])


if __name__ == '__main__':
    app.start()
