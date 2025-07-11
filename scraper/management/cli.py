"""
CLI команды для управления скрапингом.
"""
import sys
import click
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

# Добавляем путь к shared модулям
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.config import settings
from shared.logging_config import setup_logging, get_logger
from shared.database import get_db_session, init_db
from shared.models import Job, Company, ScrapeLog
from scraper.tasks import crawl_site, cleanup_old_data, generate_stats, health_check

# Настройка логирования
setup_logging()
logger = get_logger(__name__)


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Подробный вывод')
@click.pass_context
def cli(ctx, verbose):
    """Система управления скрапингом вакансий."""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    
    if verbose:
        logger.setLevel('DEBUG')


@cli.command()
@click.argument('site', type=click.Choice(['site1', 'site2', 'all']))
@click.option('--max-pages', '-p', default=10, help='Максимальное количество страниц')
@click.option('--async-mode', '-a', is_flag=True, help='Асинхронный режим через Celery')
@click.pass_context
def crawl(ctx, site: str, max_pages: int, async_mode: bool):
    """
    Запуск скрапинга для указанного сайта.
    
    SITE: Имя сайта для скрапинга (site1, site2, all)
    """
    verbose = ctx.obj.get('verbose', False)
    
    if verbose:
        click.echo(f"Запуск скрапинга для {site}")
        click.echo(f"Максимальное количество страниц: {max_pages}")
        click.echo(f"Асинхронный режим: {async_mode}")
    
    if site == 'all':
        sites = ['site1', 'site2']
    else:
        sites = [site]
    
    for site_name in sites:
        click.echo(f"\n🕷️  Запуск скрапинга для {site_name}...")
        
        try:
            if async_mode:
                # Асинхронный запуск через Celery
                from scraper.tasks import manual_crawl
                task = manual_crawl.delay(site_name, max_pages=max_pages)
                
                click.echo(f"✅ Задача запущена асинхронно (ID: {task.id})")
                click.echo(f"Для проверки статуса используйте: python manage.py status {task.id}")
                
            else:
                # Синхронный запуск
                import subprocess
                
                cmd = [
                    'scrapy', 'crawl', site_name,
                    '-a', f'max_pages={max_pages}',
                    '-s', f'LOG_LEVEL={"DEBUG" if verbose else "INFO"}'
                ]
                
                result = subprocess.run(
                    cmd,
                    cwd=Path(__file__).parent.parent,
                    capture_output=not verbose,
                    text=True
                )
                
                if result.returncode == 0:
                    click.echo(f"✅ Скрапинг {site_name} завершен успешно")
                else:
                    click.echo(f"❌ Ошибка скрапинга {site_name}")
                    if verbose and result.stderr:
                        click.echo(f"Ошибка: {result.stderr}")
                        
        except Exception as e:
            click.echo(f"❌ Ошибка при запуске скрапинга {site_name}: {e}")


@cli.command()
@click.option('--days', '-d', default=30, help='Количество дней для хранения данных')
@click.option('--dry-run', is_flag=True, help='Показать что будет удалено без фактического удаления')
@click.pass_context
def cleanup(ctx, days: int, dry_run: bool):
    """Очистка старых данных из базы."""
    verbose = ctx.obj.get('verbose', False)
    
    if verbose:
        click.echo(f"Очистка данных старше {days} дней")
        click.echo(f"Режим тестирования: {dry_run}")
    
    try:
        if dry_run:
            # Показываем что будет удалено
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            with get_db_session() as session:
                jobs_count = session.query(Job).filter(Job.created_at < cutoff_date).count()
                logs_count = session.query(ScrapeLog).filter(ScrapeLog.start_time < cutoff_date).count()
                companies_count = session.query(Company).filter(~Company.jobs.any()).count()
                
                click.echo(f"\n📊 Будет удалено:")
                click.echo(f"  - Вакансий: {jobs_count}")
                click.echo(f"  - Логов скрапинга: {logs_count}")
                click.echo(f"  - Компаний без вакансий: {companies_count}")
                click.echo(f"\nДля фактического удаления запустите без --dry-run")
        else:
            # Фактическая очистка
            result = cleanup_old_data(days)
            
            if result['status'] == 'success':
                click.echo(f"✅ Очистка завершена успешно:")
                click.echo(f"  - Удалено вакансий: {result['jobs_deleted']}")
                click.echo(f"  - Удалено логов: {result['logs_deleted']}")
                click.echo(f"  - Удалено компаний: {result['companies_deleted']}")
            else:
                click.echo(f"❌ Ошибка очистки: {result.get('error_message', 'Неизвестная ошибка')}")
                
    except Exception as e:
        click.echo(f"❌ Ошибка при очистке: {e}")


@cli.command()
@click.option('--format', '-f', type=click.Choice(['table', 'json']), default='table', help='Формат вывода')
@click.pass_context
def stats(ctx, format: str):
    """Показать статистику скрапинга."""
    verbose = ctx.obj.get('verbose', False)
    
    try:
        result = generate_stats()
        
        if result['status'] != 'success':
            click.echo(f"❌ Ошибка получения статистики: {result.get('error_message')}")
            return
        
        if format == 'json':
            import json
            click.echo(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            # Табличный формат
            click.echo("\n📊 Статистика скрапинга")
            click.echo("=" * 50)
            
            click.echo(f"\n📈 Общая статистика:")
            click.echo(f"  Всего вакансий: {result['total_jobs']}")
            click.echo(f"  Всего компаний: {result['total_companies']}")
            click.echo(f"  Вакансий за 24ч: {result['jobs_last_24h']}")
            
            click.echo(f"\n🌐 Статистика по сайтам:")
            for site_stat in result['sites_stats']:
                click.echo(f"  {site_stat['site']}: {site_stat['jobs_count']} вакансий")
            
            scraping_stats = result['scraping_stats']
            click.echo(f"\n🕷️  Статистика скрапинга:")
            click.echo(f"  Успешных запусков: {scraping_stats['successful_scrapes']}")
            click.echo(f"  Неудачных запусков: {scraping_stats['failed_scrapes']}")
            click.echo(f"  Процент успеха: {scraping_stats['success_rate']:.1f}%")
            click.echo(f"  Среднее время выполнения: {scraping_stats['avg_duration_seconds']:.1f}с")
            
            click.echo(f"\n🏢 Топ компаний:")
            for i, company in enumerate(result['top_companies'][:5], 1):
                click.echo(f"  {i}. {company['name']}: {company['jobs_count']} вакансий")
                
    except Exception as e:
        click.echo(f"❌ Ошибка при получении статистики: {e}")


@cli.command()
@click.pass_context
def health(ctx):
    """Проверка здоровья системы."""
    verbose = ctx.obj.get('verbose', False)
    
    try:
        result = health_check()
        
        status_emoji = {
            'healthy': '✅',
            'degraded': '⚠️',
            'unhealthy': '❌',
            'error': '💥'
        }
        
        overall_status = result['status']
        click.echo(f"\n{status_emoji.get(overall_status, '❓')} Общий статус системы: {overall_status.upper()}")
        
        if 'checks' in result:
            click.echo("\n🔍 Детальная проверка:")
            for check_name, check_result in result['checks'].items():
                if 'healthy' in check_result:
                    emoji = '✅'
                elif 'warning' in check_result or 'degraded' in check_result:
                    emoji = '⚠️'
                elif 'unhealthy' in check_result or 'error' in check_result:
                    emoji = '❌'
                else:
                    emoji = 'ℹ️'
                
                click.echo(f"  {emoji} {check_name}: {check_result}")
        
        if result['status'] != 'healthy':
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"❌ Ошибка при проверке здоровья: {e}")
        sys.exit(1)


@cli.command()
@click.argument('task_id', required=False)
@click.option('--all', '-a', is_flag=True, help='Показать все активные задачи')
@click.pass_context
def status(ctx, task_id: Optional[str], all: bool):
    """Проверка статуса задач Celery."""
    verbose = ctx.obj.get('verbose', False)
    
    try:
        from celery import Celery
        from scraper.celery_app import app
        
        if task_id:
            # Статус конкретной задачи
            result = app.AsyncResult(task_id)
            
            click.echo(f"\n📋 Статус задачи {task_id}:")
            click.echo(f"  Состояние: {result.state}")
            
            if result.state == 'PENDING':
                click.echo("  Задача ожидает выполнения")
            elif result.state == 'SUCCESS':
                click.echo("  ✅ Задача выполнена успешно")
                if verbose and result.result:
                    click.echo(f"  Результат: {result.result}")
            elif result.state == 'FAILURE':
                click.echo("  ❌ Задача завершилась с ошибкой")
                if verbose:
                    click.echo(f"  Ошибка: {result.info}")
            else:
                click.echo(f"  Состояние: {result.state}")
                if verbose and result.info:
                    click.echo(f"  Информация: {result.info}")
        
        elif all:
            # Все активные задачи
            inspect = app.control.inspect()
            
            active_tasks = inspect.active()
            if active_tasks:
                click.echo("\n🔄 Активные задачи:")
                for worker, tasks in active_tasks.items():
                    if tasks:
                        click.echo(f"\n  Воркер: {worker}")
                        for task in tasks:
                            click.echo(f"    📋 {task['id']}: {task['name']}")
                            if verbose:
                                click.echo(f"       Аргументы: {task.get('args', [])}")
            else:
                click.echo("ℹ️  Нет активных задач")
            
            scheduled_tasks = inspect.scheduled()
            if scheduled_tasks:
                click.echo("\n⏰ Запланированные задачи:")
                for worker, tasks in scheduled_tasks.items():
                    if tasks:
                        click.echo(f"\n  Воркер: {worker}")
                        for task in tasks:
                            click.echo(f"    📅 {task['request']['id']}: {task['request']['task']}")
        else:
            click.echo("❓ Укажите ID задачи или используйте --all для просмотра всех задач")
            
    except Exception as e:
        click.echo(f"❌ Ошибка при получении статуса: {e}")


@cli.command()
@click.pass_context
def init_db(ctx):
    """Инициализация базы данных."""
    verbose = ctx.obj.get('verbose', False)
    
    try:
        click.echo("🗄️  Инициализация базы данных...")
        
        from shared.database import init_db
        init_db()
        
        click.echo("✅ База данных инициализирована успешно")
        
    except Exception as e:
        click.echo(f"❌ Ошибка инициализации базы данных: {e}")


@cli.command()
@click.option('--site', type=click.Choice(['site1', 'site2']), help='Фильтр по сайту')
@click.option('--limit', '-l', default=10, help='Количество записей для показа')
@click.pass_context
def logs(ctx, site: Optional[str], limit: int):
    """Просмотр логов скрапинга."""
    verbose = ctx.obj.get('verbose', False)
    
    try:
        with get_db_session() as session:
            query = session.query(ScrapeLog).order_by(ScrapeLog.start_time.desc())
            
            if site:
                query = query.filter(ScrapeLog.site == site)
            
            logs = query.limit(limit).all()
            
            if not logs:
                click.echo("ℹ️  Логи скрапинга не найдены")
                return
            
            click.echo(f"\n📜 Последние {len(logs)} логов скрапинга:")
            click.echo("=" * 80)
            
            for log in logs:
                status_emoji = {
                    'running': '🔄',
                    'completed': '✅',
                    'failed': '❌'
                }.get(log.status, '❓')
                
                duration = ""
                if log.duration_seconds:
                    duration = f" ({log.duration_seconds:.1f}с)"
                
                click.echo(f"\n{status_emoji} {log.spider_name} - {log.site}")
                click.echo(f"   Время: {log.start_time}")
                click.echo(f"   Статус: {log.status}{duration}")
                
                if log.items_scraped is not None:
                    click.echo(f"   Обработано: {log.items_scraped} элементов")
                
                if log.error_message and verbose:
                    click.echo(f"   Ошибка: {log.error_message}")
                    
    except Exception as e:
        click.echo(f"❌ Ошибка при получении логов: {e}")


@cli.command()
@click.pass_context
def worker(ctx):
    """Запуск Celery worker."""
    verbose = ctx.obj.get('verbose', False)
    
    try:
        click.echo("🔧 Запуск Celery worker...")
        
        import subprocess
        
        cmd = [
            'celery', '-A', 'scraper.celery_app', 'worker',
            '--loglevel=DEBUG' if verbose else '--loglevel=INFO',
            '--concurrency=4'
        ]
        
        subprocess.run(cmd, cwd=Path(__file__).parent.parent)
        
    except KeyboardInterrupt:
        click.echo("\n👋 Worker остановлен")
    except Exception as e:
        click.echo(f"❌ Ошибка запуска worker: {e}")


@cli.command()
@click.pass_context
def beat(ctx):
    """Запуск Celery beat (планировщик)."""
    verbose = ctx.obj.get('verbose', False)
    
    try:
        click.echo("⏰ Запуск Celery beat...")
        
        import subprocess
        
        cmd = [
            'celery', '-A', 'scraper.celery_app', 'beat',
            '--loglevel=DEBUG' if verbose else '--loglevel=INFO'
        ]
        
        subprocess.run(cmd, cwd=Path(__file__).parent.parent)
        
    except KeyboardInterrupt:
        click.echo("\n👋 Beat остановлен")
    except Exception as e:
        click.echo(f"❌ Ошибка запуска beat: {e}")


if __name__ == '__main__':
    cli()
