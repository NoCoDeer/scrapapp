"""
Роутер для административных функций.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

# Добавляем путь к shared модулям
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.database import get_db_session
from shared.models import Job, Company, ScrapeLog
from shared.logging_config import get_logger
from api.schemas import (
    StatsResponse,
    TriggerScrapeRequest,
    TriggerScrapeResponse,
    TaskStatus,
    ScrapeLogsResponse,
    ScrapeLog as ScrapeLogSchema
)

logger = get_logger(__name__)

router = APIRouter()


def get_db():
    """Dependency для получения сессии базы данных."""
    with get_db_session() as session:
        yield session


@router.get("/stats", response_model=StatsResponse)
async def get_system_stats(
    db: Session = Depends(get_db)
):
    """
    Получение общей статистики системы.
    """
    try:
        # Общая статистика
        total_jobs = db.query(func.count(Job.id)).scalar()
        total_companies = db.query(func.count(Company.id)).scalar()
        
        # Статистика за последние 24 часа
        yesterday = datetime.utcnow() - timedelta(days=1)
        jobs_last_24h = db.query(func.count(Job.id)).filter(
            Job.created_at >= yesterday
        ).scalar()
        
        # Статистика по сайтам
        sites_stats = db.query(
            Job.source_site,
            func.count(Job.id).label('jobs_count')
        ).group_by(Job.source_site).all()
        
        sites_list = [
            {"site": site, "jobs_count": count}
            for site, count in sites_stats
        ]
        
        # Статистика скрапинга
        total_scrapes = db.query(func.count(ScrapeLog.id)).scalar()
        successful_scrapes = db.query(func.count(ScrapeLog.id)).filter(
            ScrapeLog.status == 'completed'
        ).scalar()
        failed_scrapes = db.query(func.count(ScrapeLog.id)).filter(
            ScrapeLog.status == 'failed'
        ).scalar()
        
        success_rate = (successful_scrapes / total_scrapes * 100) if total_scrapes > 0 else 0
        
        # Среднее время выполнения скрапинга
        avg_duration = db.query(func.avg(ScrapeLog.duration_seconds)).filter(
            ScrapeLog.duration_seconds.isnot(None)
        ).scalar()
        
        scraping_stats = {
            "total_scrapes": total_scrapes,
            "successful_scrapes": successful_scrapes,
            "failed_scrapes": failed_scrapes,
            "success_rate": round(success_rate, 1),
            "avg_duration_seconds": round(float(avg_duration), 1) if avg_duration else 0
        }
        
        # Топ компаний по количеству вакансий
        top_companies = db.query(
            Company.name,
            func.count(Job.id).label('jobs_count')
        ).join(Job).group_by(Company.id, Company.name).order_by(
            desc(func.count(Job.id))
        ).limit(10).all()
        
        top_companies_list = [
            {"name": name, "jobs_count": count}
            for name, count in top_companies
        ]
        
        return StatsResponse(
            total_jobs=total_jobs,
            total_companies=total_companies,
            jobs_last_24h=jobs_last_24h,
            sites_stats=sites_list,
            scraping_stats=scraping_stats,
            top_companies=top_companies_list,
            generated_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении статистики"
        )


@router.post("/scrape/trigger", response_model=TriggerScrapeResponse)
async def trigger_scrape(
    request: TriggerScrapeRequest
):
    """
    Запуск задачи скрапинга.
    """
    try:
        # Валидация сайта
        allowed_sites = ["site1", "site2"]
        if request.site not in allowed_sites:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неподдерживаемый сайт. Доступные: {', '.join(allowed_sites)}"
            )
        
        # Импортируем Celery задачу
        from scraper.tasks import manual_crawl
        
        # Запускаем задачу
        task = manual_crawl.delay(
            site=request.site,
            max_pages=request.max_pages
        )
        
        # Оценка времени выполнения (примерная)
        estimated_duration = request.max_pages * 30  # 30 секунд на страницу
        
        logger.info(f"Запущена задача скрапинга: {task.id} для сайта {request.site}")
        
        return TriggerScrapeResponse(
            task_id=task.id,
            message=f"Задача скрапинга для {request.site} запущена",
            estimated_duration=estimated_duration
        )
        
    except Exception as e:
        logger.error(f"Ошибка при запуске скрапинга: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при запуске скрапинга"
        )


@router.get("/scrape/status/{task_id}", response_model=TaskStatus)
async def get_scrape_status(
    task_id: str
):
    """
    Получение статуса задачи скрапинга.
    """
    try:
        from scraper.celery_app import app as celery_app
        
        result = celery_app.AsyncResult(task_id)
        
        # Получаем информацию о задаче
        task_info = {
            "task_id": task_id,
            "status": result.state,
            "result": None,
            "error": None,
            "created_at": datetime.utcnow()  # В реальности нужно получать из метаданных
        }
        
        if result.state == 'SUCCESS':
            task_info["result"] = result.result
        elif result.state == 'FAILURE':
            task_info["error"] = str(result.info)
        elif result.state == 'PENDING':
            task_info["status"] = "PENDING"
        else:
            task_info["result"] = result.info
        
        return TaskStatus(**task_info)
        
    except Exception as e:
        logger.error(f"Ошибка при получении статуса задачи {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении статуса задачи"
        )


@router.get("/scrape/logs", response_model=ScrapeLogsResponse)
async def get_scrape_logs(
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(20, ge=1, le=100, description="Размер страницы"),
    site: Optional[str] = Query(None, description="Фильтр по сайту"),
    status_filter: Optional[str] = Query(None, description="Фильтр по статусу", alias="status"),
    date_from: Optional[datetime] = Query(None, description="Дата от"),
    date_to: Optional[datetime] = Query(None, description="Дата до"),
    db: Session = Depends(get_db)
):
    """
    Получение логов скрапинга.
    """
    try:
        # Базовый запрос
        query = db.query(ScrapeLog)
        
        # Применяем фильтры
        if site:
            query = query.filter(ScrapeLog.site == site)
        
        if status_filter:
            query = query.filter(ScrapeLog.status == status_filter)
        
        if date_from:
            query = query.filter(ScrapeLog.start_time >= date_from)
        
        if date_to:
            query = query.filter(ScrapeLog.start_time <= date_to)
        
        # Сортировка по дате (новые первыми)
        query = query.order_by(desc(ScrapeLog.start_time))
        
        # Подсчет общего количества
        total = query.count()
        
        # Применяем пагинацию
        offset = (page - 1) * size
        logs = query.offset(offset).limit(size).all()
        
        # Преобразуем в схемы
        log_items = [ScrapeLogSchema.model_validate(log) for log in logs]
        
        # Вычисляем метаданные пагинации
        from math import ceil
        pages = ceil(total / size)
        has_next = page < pages
        has_prev = page > 1
        
        return ScrapeLogsResponse(
            items=log_items,
            total=total,
            page=page,
            size=size,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
        
    except Exception as e:
        logger.error(f"Ошибка при получении логов скрапинга: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении логов скрапинга"
        )


@router.delete("/scrape/logs/cleanup")
async def cleanup_old_logs(
    days: int = Query(30, ge=1, description="Количество дней для хранения"),
    dry_run: bool = Query(False, description="Показать что будет удалено без фактического удаления"),
    db: Session = Depends(get_db)
):
    """
    Очистка старых логов скрапинга.
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Подсчитываем количество логов для удаления
        logs_to_delete = db.query(ScrapeLog).filter(
            ScrapeLog.start_time < cutoff_date
        ).count()
        
        if dry_run:
            return {
                "dry_run": True,
                "logs_to_delete": logs_to_delete,
                "cutoff_date": cutoff_date.isoformat(),
                "message": f"Будет удалено {logs_to_delete} логов старше {days} дней"
            }
        
        # Фактическое удаление
        deleted_count = db.query(ScrapeLog).filter(
            ScrapeLog.start_time < cutoff_date
        ).delete()
        
        db.commit()
        
        logger.info(f"Удалено {deleted_count} старых логов скрапинга")
        
        return {
            "dry_run": False,
            "logs_deleted": deleted_count,
            "cutoff_date": cutoff_date.isoformat(),
            "message": f"Удалено {deleted_count} логов старше {days} дней"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при очистке логов: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при очистке логов"
        )


@router.get("/celery/workers")
async def get_celery_workers():
    """
    Получение информации о Celery workers.
    """
    try:
        from scraper.celery_app import app as celery_app
        
        inspect = celery_app.control.inspect()
        
        # Получаем информацию о workers
        stats = inspect.stats()
        active_tasks = inspect.active()
        scheduled_tasks = inspect.scheduled()
        reserved_tasks = inspect.reserved()
        
        workers_info = []
        
        if stats:
            for worker_name, worker_stats in stats.items():
                worker_info = {
                    "name": worker_name,
                    "status": "online",
                    "pool": worker_stats.get("pool", {}),
                    "rusage": worker_stats.get("rusage", {}),
                    "active_tasks": len(active_tasks.get(worker_name, [])) if active_tasks else 0,
                    "scheduled_tasks": len(scheduled_tasks.get(worker_name, [])) if scheduled_tasks else 0,
                    "reserved_tasks": len(reserved_tasks.get(worker_name, [])) if reserved_tasks else 0
                }
                workers_info.append(worker_info)
        
        return {
            "workers": workers_info,
            "total_workers": len(workers_info),
            "total_active_tasks": sum(w["active_tasks"] for w in workers_info),
            "total_scheduled_tasks": sum(w["scheduled_tasks"] for w in workers_info),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации о workers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении информации о workers"
        )


@router.post("/celery/tasks/{task_id}/revoke")
async def revoke_task(
    task_id: str,
    terminate: bool = Query(False, description="Принудительно завершить задачу")
):
    """
    Отмена задачи Celery.
    """
    try:
        from scraper.celery_app import app as celery_app
        
        # Отменяем задачу
        celery_app.control.revoke(task_id, terminate=terminate)
        
        logger.info(f"Задача {task_id} отменена (terminate={terminate})")
        
        return {
            "task_id": task_id,
            "revoked": True,
            "terminated": terminate,
            "message": f"Задача {task_id} отменена"
        }
        
    except Exception as e:
        logger.error(f"Ошибка при отмене задачи {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при отмене задачи"
        )


@router.get("/database/stats")
async def get_database_stats(
    db: Session = Depends(get_db)
):
    """
    Получение статистики базы данных.
    """
    try:
        # Размеры таблиц
        table_stats = []
        
        # Статистика по таблице jobs
        jobs_count = db.query(func.count(Job.id)).scalar()
        jobs_size = db.execute(
            "SELECT pg_size_pretty(pg_total_relation_size('jobs'))"
        ).scalar()
        
        table_stats.append({
            "table": "jobs",
            "rows": jobs_count,
            "size": jobs_size
        })
        
        # Статистика по таблице companies
        companies_count = db.query(func.count(Company.id)).scalar()
        companies_size = db.execute(
            "SELECT pg_size_pretty(pg_total_relation_size('companies'))"
        ).scalar()
        
        table_stats.append({
            "table": "companies",
            "rows": companies_count,
            "size": companies_size
        })
        
        # Статистика по таблице scrape_logs
        logs_count = db.query(func.count(ScrapeLog.id)).scalar()
        logs_size = db.execute(
            "SELECT pg_size_pretty(pg_total_relation_size('scrape_logs'))"
        ).scalar()
        
        table_stats.append({
            "table": "scrape_logs",
            "rows": logs_count,
            "size": logs_size
        })
        
        # Общий размер базы данных
        db_size = db.execute(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        ).scalar()
        
        # Статистика подключений
        connections_stats = db.execute("""
            SELECT 
                count(*) as total_connections,
                count(*) FILTER (WHERE state = 'active') as active_connections,
                count(*) FILTER (WHERE state = 'idle') as idle_connections
            FROM pg_stat_activity 
            WHERE datname = current_database()
        """).fetchone()
        
        return {
            "database_size": db_size,
            "tables": table_stats,
            "connections": {
                "total": connections_stats[0],
                "active": connections_stats[1],
                "idle": connections_stats[2]
            },
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики базы данных: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении статистики базы данных"
        )


@router.post("/elasticsearch/reindex")
async def reindex_elasticsearch(
    batch_size: int = Query(1000, description="Размер батча для индексации"),
    force: bool = Query(False, description="Принудительная переиндексация")
):
    """
    Переиндексация данных в Elasticsearch.
    """
    try:
        from shared.config import settings
        
        if not settings.elasticsearch_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Elasticsearch не настроен"
            )
        
        # Здесь должна быть логика переиндексации
        # Для примера возвращаем заглушку
        
        return {
            "status": "started",
            "message": "Переиндексация запущена",
            "batch_size": batch_size,
            "force": force,
            "estimated_time": "5-10 минут",
            "started_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка при запуске переиндексации: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при запуске переиндексации"
        )


@router.get("/system/info")
async def get_system_info():
    """
    Получение информации о системе.
    """
    try:
        import platform
        import psutil
        from shared.config import settings
        
        # Системная информация
        system_info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "architecture": platform.architecture()[0],
            "processor": platform.processor(),
            "hostname": platform.node()
        }
        
        # Информация о ресурсах
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            
            resources = {
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "percent": memory.percent
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "percent": round((disk.used / disk.total) * 100, 1)
                }
            }
        except ImportError:
            resources = {"error": "psutil not available"}
        
        # Конфигурация приложения
        app_config = {
            "environment": settings.environment,
            "database_configured": bool(settings.database_url),
            "redis_configured": bool(settings.redis_url),
            "elasticsearch_configured": bool(settings.elasticsearch_url),
            "sentry_configured": bool(settings.sentry_dsn)
        }
        
        return {
            "system": system_info,
            "resources": resources,
            "application": app_config,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении системной информации: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении системной информации"
        )
