"""
Celery задачи для скрапинга.
"""
import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from celery import Task
from celery.exceptions import Retry
from sqlalchemy import func, and_

# Добавляем путь к shared модулям
sys.path.append(str(Path(__file__).parent.parent))

from shared.config import settings
from shared.logging_config import get_logger
from shared.database import get_db_session
from shared.models import Job, Company, ScrapeLog
from .celery_app import app

logger = get_logger(__name__)


class BaseScrapingTask(Task):
    """Базовый класс для задач скрапинга."""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Обработка ошибок задачи."""
        logger.error(f"Задача {self.name} (ID: {task_id}) завершилась с ошибкой: {exc}")
        
        # Отправляем уведомление в Sentry если настроен
        if settings.sentry_dsn:
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(exc)
            except ImportError:
                pass
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Обработка повторных попыток."""
        logger.warning(f"Повторная попытка задачи {self.name} (ID: {task_id}): {exc}")
    
    def on_success(self, retval, task_id, args, kwargs):
        """Обработка успешного выполнения."""
        logger.info(f"Задача {self.name} (ID: {task_id}) успешно завершена")


@app.task(bind=True, base=BaseScrapingTask, name='scraper.tasks.crawl_site')
def crawl_site(self, spider_name: str, **kwargs) -> Dict[str, Any]:
    """
    Запуск скрапинга для указанного сайта.
    
    Args:
        spider_name: Имя паука (site1, site2, etc.)
        **kwargs: Дополнительные параметры для паука
    
    Returns:
        Словарь с результатами скрапинга
    """
    logger.info(f"Запуск скрапинга для {spider_name}")
    
    try:
        # Подготавливаем команду для запуска Scrapy
        scrapy_cmd = [
            'scrapy', 'crawl', spider_name,
            '-s', f'LOG_LEVEL={settings.scraper_settings.log_level}',
            '-s', f'JOBDIR=crawls/{spider_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        ]
        
        # Добавляем дополнительные параметры
        for key, value in kwargs.items():
            scrapy_cmd.extend(['-a', f'{key}={value}'])
        
        # Запускаем Scrapy как подпроцесс
        result = subprocess.run(
            scrapy_cmd,
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=settings.scraper_settings.task_timeout
        )
        
        # Парсим статистику из вывода Scrapy
        stats = parse_scrapy_stats(result.stdout)
        
        if result.returncode == 0:
            logger.info(f"Скрапинг {spider_name} завершен успешно")
            stats['status'] = 'success'
        else:
            logger.error(f"Ошибка скрапинга {spider_name}: {result.stderr}")
            stats['status'] = 'error'
            stats['error_message'] = result.stderr
        
        return stats
        
    except subprocess.TimeoutExpired:
        logger.error(f"Таймаут скрапинга {spider_name}")
        return {
            'status': 'timeout',
            'error_message': 'Превышено время выполнения задачи',
            'items_scraped': 0,
            'items_dropped': 0,
            'errors_count': 1
        }
    
    except Exception as exc:
        logger.error(f"Неожиданная ошибка при скрапинге {spider_name}: {exc}")
        
        # Повторяем задачу при определенных ошибках
        if self.request.retries < self.max_retries:
            logger.info(f"Повторная попытка {self.request.retries + 1}/{self.max_retries}")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        
        return {
            'status': 'failed',
            'error_message': str(exc),
            'items_scraped': 0,
            'items_dropped': 0,
            'errors_count': 1
        }


@app.task(bind=True, base=BaseScrapingTask, name='scraper.tasks.cleanup_old_data')
def cleanup_old_data(self, days_to_keep: int = 30) -> Dict[str, Any]:
    """
    Очистка старых данных из базы.
    
    Args:
        days_to_keep: Количество дней для хранения данных
    
    Returns:
        Статистика очистки
    """
    logger.info(f"Начало очистки данных старше {days_to_keep} дней")
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        with get_db_session() as session:
            # Удаляем старые вакансии
            old_jobs = session.query(Job).filter(
                Job.created_at < cutoff_date
            )
            jobs_count = old_jobs.count()
            old_jobs.delete(synchronize_session=False)
            
            # Удаляем старые логи скрапинга
            old_logs = session.query(ScrapeLog).filter(
                ScrapeLog.start_time < cutoff_date
            )
            logs_count = old_logs.count()
            old_logs.delete(synchronize_session=False)
            
            # Удаляем компании без вакансий
            companies_without_jobs = session.query(Company).filter(
                ~Company.jobs.any()
            )
            companies_count = companies_without_jobs.count()
            companies_without_jobs.delete(synchronize_session=False)
            
            session.commit()
            
            result = {
                'status': 'success',
                'jobs_deleted': jobs_count,
                'logs_deleted': logs_count,
                'companies_deleted': companies_count,
                'cutoff_date': cutoff_date.isoformat()
            }
            
            logger.info(f"Очистка завершена: {result}")
            return result
            
    except Exception as exc:
        logger.error(f"Ошибка при очистке данных: {exc}")
        return {
            'status': 'failed',
            'error_message': str(exc),
            'jobs_deleted': 0,
            'logs_deleted': 0,
            'companies_deleted': 0
        }


@app.task(bind=True, base=BaseScrapingTask, name='scraper.tasks.generate_stats')
def generate_stats(self) -> Dict[str, Any]:
    """
    Генерация статистики по скрапингу.
    
    Returns:
        Словарь со статистикой
    """
    logger.info("Генерация статистики скрапинга")
    
    try:
        with get_db_session() as session:
            # Общая статистика
            total_jobs = session.query(func.count(Job.id)).scalar()
            total_companies = session.query(func.count(Company.id)).scalar()
            
            # Статистика за последние 24 часа
            last_24h = datetime.utcnow() - timedelta(hours=24)
            jobs_last_24h = session.query(func.count(Job.id)).filter(
                Job.created_at >= last_24h
            ).scalar()
            
            # Статистика по сайтам
            sites_stats = session.query(
                Job.source_site,
                func.count(Job.id).label('jobs_count')
            ).group_by(Job.source_site).all()
            
            # Статистика по логам скрапинга за последнюю неделю
            last_week = datetime.utcnow() - timedelta(days=7)
            scrape_logs = session.query(ScrapeLog).filter(
                ScrapeLog.start_time >= last_week
            ).all()
            
            # Анализ логов
            successful_scrapes = len([log for log in scrape_logs if log.status == 'completed'])
            failed_scrapes = len([log for log in scrape_logs if log.status == 'failed'])
            
            avg_duration = 0
            if scrape_logs:
                durations = [log.duration_seconds for log in scrape_logs if log.duration_seconds]
                if durations:
                    avg_duration = sum(durations) / len(durations)
            
            # Топ компаний по количеству вакансий
            top_companies = session.query(
                Company.name,
                func.count(Job.id).label('jobs_count')
            ).join(Job).group_by(Company.name).order_by(
                func.count(Job.id).desc()
            ).limit(10).all()
            
            result = {
                'status': 'success',
                'generated_at': datetime.utcnow().isoformat(),
                'total_jobs': total_jobs,
                'total_companies': total_companies,
                'jobs_last_24h': jobs_last_24h,
                'sites_stats': [
                    {'site': site, 'jobs_count': count} 
                    for site, count in sites_stats
                ],
                'scraping_stats': {
                    'successful_scrapes': successful_scrapes,
                    'failed_scrapes': failed_scrapes,
                    'success_rate': successful_scrapes / len(scrape_logs) * 100 if scrape_logs else 0,
                    'avg_duration_seconds': avg_duration
                },
                'top_companies': [
                    {'name': name, 'jobs_count': count}
                    for name, count in top_companies
                ]
            }
            
            logger.info("Статистика сгенерирована успешно")
            return result
            
    except Exception as exc:
        logger.error(f"Ошибка при генерации статистики: {exc}")
        return {
            'status': 'failed',
            'error_message': str(exc)
        }


@app.task(bind=True, base=BaseScrapingTask, name='scraper.tasks.health_check')
def health_check(self) -> Dict[str, Any]:
    """
    Проверка здоровья системы скрапинга.
    
    Returns:
        Статус системы
    """
    logger.info("Проверка здоровья системы")
    
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'checks': {}
    }
    
    try:
        # Проверка подключения к базе данных
        try:
            with get_db_session() as session:
                session.execute('SELECT 1')
                health_status['checks']['database'] = 'healthy'
        except Exception as e:
            health_status['checks']['database'] = f'unhealthy: {str(e)}'
            health_status['status'] = 'unhealthy'
        
        # Проверка Redis
        try:
            import redis
            r = redis.from_url(settings.celery_broker_url)
            r.ping()
            health_status['checks']['redis'] = 'healthy'
        except Exception as e:
            health_status['checks']['redis'] = f'unhealthy: {str(e)}'
            health_status['status'] = 'unhealthy'
        
        # Проверка Elasticsearch (если настроен)
        if settings.scraper_settings.elasticsearch_url:
            try:
                from elasticsearch import Elasticsearch
                es = Elasticsearch([settings.scraper_settings.elasticsearch_url])
                es.ping()
                health_status['checks']['elasticsearch'] = 'healthy'
            except Exception as e:
                health_status['checks']['elasticsearch'] = f'unhealthy: {str(e)}'
                health_status['status'] = 'degraded'
        
        # Проверка последних скрапингов
        try:
            with get_db_session() as session:
                last_hour = datetime.utcnow() - timedelta(hours=1)
                recent_logs = session.query(ScrapeLog).filter(
                    ScrapeLog.start_time >= last_hour
                ).count()
                
                if recent_logs > 0:
                    health_status['checks']['recent_activity'] = 'healthy'
                else:
                    health_status['checks']['recent_activity'] = 'no recent activity'
                    
        except Exception as e:
            health_status['checks']['recent_activity'] = f'error: {str(e)}'
        
        # Проверка дискового пространства
        try:
            import shutil
            total, used, free = shutil.disk_usage('/')
            free_percent = (free / total) * 100
            
            if free_percent > 20:
                health_status['checks']['disk_space'] = 'healthy'
            elif free_percent > 10:
                health_status['checks']['disk_space'] = 'warning'
                health_status['status'] = 'degraded'
            else:
                health_status['checks']['disk_space'] = 'critical'
                health_status['status'] = 'unhealthy'
                
        except Exception as e:
            health_status['checks']['disk_space'] = f'error: {str(e)}'
        
        logger.info(f"Проверка здоровья завершена: {health_status['status']}")
        return health_status
        
    except Exception as exc:
        logger.error(f"Ошибка при проверке здоровья: {exc}")
        return {
            'status': 'error',
            'error_message': str(exc),
            'timestamp': datetime.utcnow().isoformat()
        }


@app.task(bind=True, base=BaseScrapingTask, name='scraper.tasks.manual_crawl')
def manual_crawl(self, spider_name: str, **kwargs) -> Dict[str, Any]:
    """
    Ручной запуск скрапинга (для CLI команд).
    
    Args:
        spider_name: Имя паука
        **kwargs: Дополнительные параметры
    
    Returns:
        Результат скрапинга
    """
    logger.info(f"Ручной запуск скрапинга для {spider_name}")
    
    # Добавляем метку ручного запуска
    kwargs['manual'] = True
    
    # Вызываем основную задачу скрапинга
    return crawl_site(spider_name, **kwargs)


def parse_scrapy_stats(output: str) -> Dict[str, Any]:
    """
    Парсинг статистики из вывода Scrapy.
    
    Args:
        output: Вывод команды scrapy
    
    Returns:
        Словарь со статистикой
    """
    stats = {
        'items_scraped': 0,
        'items_dropped': 0,
        'errors_count': 0,
        'requests_count': 0,
        'response_received_count': 0
    }
    
    try:
        # Ищем статистику в выводе
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Парсим различные метрики
            if "'item_scraped_count':" in line:
                stats['items_scraped'] = extract_number_from_line(line)
            elif "'item_dropped_count':" in line:
                stats['items_dropped'] = extract_number_from_line(line)
            elif "'spider_exceptions':" in line:
                stats['errors_count'] = extract_number_from_line(line)
            elif "'downloader/request_count':" in line:
                stats['requests_count'] = extract_number_from_line(line)
            elif "'downloader/response_count':" in line:
                stats['response_received_count'] = extract_number_from_line(line)
    
    except Exception as e:
        logger.warning(f"Ошибка парсинга статистики Scrapy: {e}")
    
    return stats


def extract_number_from_line(line: str) -> int:
    """Извлечение числа из строки статистики."""
    try:
        # Ищем число после двоеточия
        parts = line.split(':')
        if len(parts) >= 2:
            number_part = parts[1].strip().rstrip(',')
            return int(number_part)
    except:
        pass
    
    return 0


# Дополнительные утилитарные задачи

@app.task(name='scraper.tasks.test_task')
def test_task() -> Dict[str, Any]:
    """Тестовая задача для проверки работы Celery."""
    logger.info("Выполнение тестовой задачи")
    return {
        'status': 'success',
        'message': 'Тестовая задача выполнена успешно',
        'timestamp': datetime.utcnow().isoformat()
    }


@app.task(name='scraper.tasks.reindex_elasticsearch')
def reindex_elasticsearch() -> Dict[str, Any]:
    """Переиндексация данных в Elasticsearch."""
    logger.info("Начало переиндексации Elasticsearch")
    
    try:
        if not settings.scraper_settings.elasticsearch_url:
            return {
                'status': 'skipped',
                'message': 'Elasticsearch не настроен'
            }
        
        from elasticsearch import Elasticsearch
        
        es = Elasticsearch([settings.scraper_settings.elasticsearch_url])
        index_name = settings.scraper_settings.elasticsearch_index
        
        # Удаляем старый индекс
        if es.indices.exists(index=index_name):
            es.indices.delete(index=index_name)
        
        # Создаем новый индекс (маппинг создается в pipeline)
        
        # Переиндексируем все вакансии
        with get_db_session() as session:
            jobs = session.query(Job).all()
            
            for job in jobs:
                doc = {
                    'company': job.company.name if job.company else '',
                    'job_title': job.job_title,
                    'location': job.location,
                    'posted_date': job.posted_date.isoformat() if job.posted_date else None,
                    'job_url': job.job_url,
                    'description': job.description,
                    'salary': job.salary,
                    'employment_type': job.employment_type,
                    'experience_level': job.experience_level,
                    'remote_allowed': job.remote_allowed,
                    'skills': json.loads(job.skills) if job.skills else [],
                    'source_site': job.source_site,
                    'scraped_at': job.created_at.isoformat(),
                    'doc_type': 'job'
                }
                
                es.index(
                    index=index_name,
                    id=job.job_url_hash or job.id,
                    body=doc
                )
        
        return {
            'status': 'success',
            'message': f'Переиндексировано {len(jobs)} вакансий',
            'jobs_count': len(jobs)
        }
        
    except Exception as exc:
        logger.error(f"Ошибка переиндексации: {exc}")
        return {
            'status': 'failed',
            'error_message': str(exc)
        }
