"""
Роутер для проверки здоровья системы.
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response

# Добавляем путь к shared модулям
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.logging_config import get_logger
from api.schemas import HealthCheck

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthCheck)
async def health_check():
    """
    Проверка здоровья системы.
    
    Проверяет состояние всех компонентов системы:
    - База данных
    - Redis
    - Elasticsearch (если настроен)
    - Celery workers
    """
    checks = {}
    overall_status = "healthy"
    
    # Проверка базы данных
    try:
        from shared.database import get_db_session
        with get_db_session() as session:
            session.execute("SELECT 1")
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"
        overall_status = "unhealthy"
    
    # Проверка Redis
    try:
        from shared.config import settings
        import redis
        
        redis_client = redis.from_url(settings.redis_url)
        redis_client.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)}"
        overall_status = "unhealthy"
    
    # Проверка Elasticsearch (если настроен)
    try:
        from shared.config import settings
        if settings.elasticsearch_url:
            from elasticsearch import Elasticsearch
            
            es = Elasticsearch([settings.elasticsearch_url])
            if es.ping():
                checks["elasticsearch"] = "healthy"
            else:
                checks["elasticsearch"] = "unhealthy: ping failed"
                if overall_status == "healthy":
                    overall_status = "degraded"
        else:
            checks["elasticsearch"] = "not configured"
    except Exception as e:
        checks["elasticsearch"] = f"unhealthy: {str(e)}"
        if overall_status == "healthy":
            overall_status = "degraded"
    
    # Проверка Celery workers
    try:
        from scraper.celery_app import app as celery_app
        
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        
        if active_workers:
            worker_count = len(active_workers)
            checks["celery_workers"] = f"healthy: {worker_count} workers active"
        else:
            checks["celery_workers"] = "warning: no active workers"
            if overall_status == "healthy":
                overall_status = "degraded"
    except Exception as e:
        checks["celery_workers"] = f"unhealthy: {str(e)}"
        if overall_status == "healthy":
            overall_status = "degraded"
    
    # Проверка дискового пространства
    try:
        import shutil
        
        total, used, free = shutil.disk_usage("/")
        free_percent = (free / total) * 100
        
        if free_percent > 20:
            checks["disk_space"] = f"healthy: {free_percent:.1f}% free"
        elif free_percent > 10:
            checks["disk_space"] = f"warning: {free_percent:.1f}% free"
            if overall_status == "healthy":
                overall_status = "degraded"
        else:
            checks["disk_space"] = f"critical: {free_percent:.1f}% free"
            overall_status = "unhealthy"
    except Exception as e:
        checks["disk_space"] = f"error: {str(e)}"
    
    # Проверка памяти
    try:
        import psutil
        
        memory = psutil.virtual_memory()
        if memory.percent < 80:
            checks["memory"] = f"healthy: {memory.percent:.1f}% used"
        elif memory.percent < 90:
            checks["memory"] = f"warning: {memory.percent:.1f}% used"
            if overall_status == "healthy":
                overall_status = "degraded"
        else:
            checks["memory"] = f"critical: {memory.percent:.1f}% used"
            overall_status = "unhealthy"
    except ImportError:
        checks["memory"] = "not available: psutil not installed"
    except Exception as e:
        checks["memory"] = f"error: {str(e)}"
    
    return HealthCheck(
        status=overall_status,
        timestamp=datetime.utcnow(),
        checks=checks
    )


@router.get("/health/live")
async def liveness_probe():
    """
    Liveness probe для Kubernetes.
    
    Простая проверка, что приложение запущено и отвечает.
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/health/ready")
async def readiness_probe():
    """
    Readiness probe для Kubernetes.
    
    Проверяет, что приложение готово принимать трафик.
    """
    try:
        # Проверяем критически важные компоненты
        from shared.database import get_db_session
        with get_db_session() as session:
            session.execute("SELECT 1")
        
        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
    
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
        return Response(
            content=f'{{"status": "not ready", "error": "{str(e)}"}}',
            status_code=503,
            media_type="application/json"
        )


@router.get("/health/metrics")
async def health_metrics():
    """
    Метрики здоровья системы в формате, удобном для мониторинга.
    """
    metrics = {}
    
    # Метрики базы данных
    try:
        from shared.database import get_db_session
        from shared.models import Job, Company, ScrapeLog
        from sqlalchemy import func
        
        with get_db_session() as session:
            # Количество записей
            metrics["jobs_total"] = session.query(func.count(Job.id)).scalar()
            metrics["companies_total"] = session.query(func.count(Company.id)).scalar()
            metrics["scrape_logs_total"] = session.query(func.count(ScrapeLog.id)).scalar()
            
            # Последняя активность
            last_job = session.query(func.max(Job.created_at)).scalar()
            if last_job:
                metrics["last_job_created"] = last_job.isoformat()
            
            last_scrape = session.query(func.max(ScrapeLog.start_time)).scalar()
            if last_scrape:
                metrics["last_scrape_started"] = last_scrape.isoformat()
    
    except Exception as e:
        metrics["database_error"] = str(e)
    
    # Метрики Celery
    try:
        from scraper.celery_app import app as celery_app
        
        inspect = celery_app.control.inspect()
        
        # Активные задачи
        active_tasks = inspect.active()
        if active_tasks:
            total_active = sum(len(tasks) for tasks in active_tasks.values())
            metrics["celery_active_tasks"] = total_active
            metrics["celery_workers"] = len(active_tasks)
        else:
            metrics["celery_active_tasks"] = 0
            metrics["celery_workers"] = 0
        
        # Запланированные задачи
        scheduled_tasks = inspect.scheduled()
        if scheduled_tasks:
            total_scheduled = sum(len(tasks) for tasks in scheduled_tasks.values())
            metrics["celery_scheduled_tasks"] = total_scheduled
        else:
            metrics["celery_scheduled_tasks"] = 0
    
    except Exception as e:
        metrics["celery_error"] = str(e)
    
    # Системные метрики
    try:
        import psutil
        
        # CPU
        metrics["cpu_percent"] = psutil.cpu_percent(interval=1)
        
        # Память
        memory = psutil.virtual_memory()
        metrics["memory_percent"] = memory.percent
        metrics["memory_available_gb"] = round(memory.available / (1024**3), 2)
        
        # Диск
        disk = psutil.disk_usage("/")
        metrics["disk_percent"] = round((disk.used / disk.total) * 100, 1)
        metrics["disk_free_gb"] = round(disk.free / (1024**3), 2)
        
    except ImportError:
        metrics["system_metrics"] = "psutil not available"
    except Exception as e:
        metrics["system_error"] = str(e)
    
    metrics["timestamp"] = datetime.utcnow().isoformat()
    
    return metrics
