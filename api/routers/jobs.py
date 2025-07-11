"""
Роутер для работы с вакансиями.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc

# Добавляем путь к shared модулям
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.database import get_db_session
from shared.models import Job, Company
from shared.logging_config import get_logger
from api.schemas import (
    Job as JobSchema,
    JobSummary,
    JobsResponse,
    JobFilters,
    PaginationParams,
    JobCreate,
    JobUpdate
)

logger = get_logger(__name__)

router = APIRouter()


def get_db():
    """Dependency для получения сессии базы данных."""
    with get_db_session() as session:
        yield session


@router.get("", response_model=JobsResponse)
async def get_jobs(
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(20, ge=1, le=100, description="Размер страницы"),
    keyword: Optional[str] = Query(None, description="Ключевое слово для поиска"),
    location: Optional[str] = Query(None, description="Местоположение"),
    company: Optional[str] = Query(None, description="Название компании"),
    salary_min: Optional[int] = Query(None, description="Минимальная зарплата"),
    salary_max: Optional[int] = Query(None, description="Максимальная зарплата"),
    employment_type: Optional[str] = Query(None, description="Тип занятости"),
    experience_level: Optional[str] = Query(None, description="Уровень опыта"),
    remote_allowed: Optional[bool] = Query(None, description="Удаленная работа"),
    source_site: Optional[str] = Query(None, description="Источник"),
    date_from: Optional[datetime] = Query(None, description="Дата публикации от"),
    date_to: Optional[datetime] = Query(None, description="Дата публикации до"),
    sort_by: str = Query("created_at", description="Поле для сортировки"),
    sort_order: str = Query("desc", description="Порядок сортировки (asc/desc)"),
    db: Session = Depends(get_db)
):
    """
    Получение списка вакансий с фильтрацией и пагинацией.
    
    Поддерживаемые поля для сортировки:
    - created_at (по умолчанию)
    - posted_date
    - job_title
    - company_name
    - location
    """
    try:
        # Базовый запрос с join к компании
        query = db.query(Job).join(Company)
        
        # Применяем фильтры
        if keyword:
            # Поиск по названию вакансии и описанию
            keyword_filter = or_(
                Job.job_title.ilike(f"%{keyword}%"),
                Job.description.ilike(f"%{keyword}%"),
                Company.name.ilike(f"%{keyword}%")
            )
            query = query.filter(keyword_filter)
        
        if location:
            query = query.filter(Job.location.ilike(f"%{location}%"))
        
        if company:
            query = query.filter(Company.name.ilike(f"%{company}%"))
        
        if employment_type:
            query = query.filter(Job.employment_type == employment_type)
        
        if experience_level:
            query = query.filter(Job.experience_level == experience_level)
        
        if remote_allowed is not None:
            query = query.filter(Job.remote_allowed == remote_allowed)
        
        if source_site:
            query = query.filter(Job.source_site == source_site)
        
        if date_from:
            query = query.filter(Job.posted_date >= date_from)
        
        if date_to:
            query = query.filter(Job.posted_date <= date_to)
        
        # Фильтрация по зарплате (простая проверка на наличие чисел)
        if salary_min or salary_max:
            salary_conditions = []
            
            if salary_min:
                # Ищем числа в поле зарплаты больше минимума
                salary_conditions.append(
                    func.regexp_replace(Job.salary, r'[^\d]', '', 'g').cast(db.Integer) >= salary_min
                )
            
            if salary_max:
                # Ищем числа в поле зарплаты меньше максимума
                salary_conditions.append(
                    func.regexp_replace(Job.salary, r'[^\d]', '', 'g').cast(db.Integer) <= salary_max
                )
            
            if salary_conditions:
                query = query.filter(and_(*salary_conditions))
        
        # Сортировка
        sort_column = getattr(Job, sort_by, None)
        if sort_by == "company_name":
            sort_column = Company.name
        
        if sort_column is not None:
            if sort_order.lower() == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
        else:
            # По умолчанию сортируем по дате создания
            query = query.order_by(desc(Job.created_at))
        
        # Подсчет общего количества
        total = query.count()
        
        # Применяем пагинацию
        offset = (page - 1) * size
        jobs = query.offset(offset).limit(size).options(joinedload(Job.company)).all()
        
        # Преобразуем в краткий формат
        job_summaries = []
        for job in jobs:
            job_summaries.append(JobSummary(
                id=job.id,
                job_title=job.job_title,
                company_name=job.company.name,
                location=job.location,
                salary=job.salary,
                posted_date=job.posted_date,
                remote_allowed=job.remote_allowed,
                source_site=job.source_site
            ))
        
        # Вычисляем метаданные пагинации
        pages = ceil(total / size)
        has_next = page < pages
        has_prev = page > 1
        
        return JobsResponse(
            items=job_summaries,
            total=total,
            page=page,
            size=size,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка вакансий: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении списка вакансий"
        )


@router.get("/{job_id}", response_model=JobSchema)
async def get_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Получение детальной информации о вакансии."""
    try:
        job = db.query(Job).options(joinedload(Job.company)).filter(Job.id == job_id).first()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Вакансия не найдена"
            )
        
        return job
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении вакансии {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении вакансии"
        )


@router.post("", response_model=JobSchema, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: JobCreate,
    db: Session = Depends(get_db)
):
    """Создание новой вакансии."""
    try:
        # Проверяем существование компании
        company = db.query(Company).filter(Company.id == job_data.company_id).first()
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Компания не найдена"
            )
        
        # Проверяем уникальность URL
        existing_job = db.query(Job).filter(Job.job_url == job_data.job_url).first()
        if existing_job:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Вакансия с таким URL уже существует"
            )
        
        # Создаем новую вакансию
        job = Job(**job_data.model_dump())
        db.add(job)
        db.commit()
        db.refresh(job)
        
        # Загружаем с компанией
        job = db.query(Job).options(joinedload(Job.company)).filter(Job.id == job.id).first()
        
        logger.info(f"Создана новая вакансия: {job.id}")
        return job
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при создании вакансии: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при создании вакансии"
        )


@router.put("/{job_id}", response_model=JobSchema)
async def update_job(
    job_id: int,
    job_data: JobUpdate,
    db: Session = Depends(get_db)
):
    """Обновление вакансии."""
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Вакансия не найдена"
            )
        
        # Обновляем только переданные поля
        update_data = job_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(job, field, value)
        
        job.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(job)
        
        # Загружаем с компанией
        job = db.query(Job).options(joinedload(Job.company)).filter(Job.id == job.id).first()
        
        logger.info(f"Обновлена вакансия: {job.id}")
        return job
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при обновлении вакансии {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при обновлении вакансии"
        )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Удаление вакансии."""
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Вакансия не найдена"
            )
        
        db.delete(job)
        db.commit()
        
        logger.info(f"Удалена вакансия: {job_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при удалении вакансии {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при удалении вакансии"
        )


@router.get("/stats/summary")
async def get_jobs_stats(
    db: Session = Depends(get_db)
):
    """Получение статистики по вакансиям."""
    try:
        # Общая статистика
        total_jobs = db.query(func.count(Job.id)).scalar()
        
        # Статистика за последние 24 часа
        yesterday = datetime.utcnow() - timedelta(days=1)
        jobs_last_24h = db.query(func.count(Job.id)).filter(
            Job.created_at >= yesterday
        ).scalar()
        
        # Статистика по сайтам
        sites_stats = db.query(
            Job.source_site,
            func.count(Job.id).label('count')
        ).group_by(Job.source_site).all()
        
        # Статистика по типам занятости
        employment_stats = db.query(
            Job.employment_type,
            func.count(Job.id).label('count')
        ).filter(Job.employment_type.isnot(None)).group_by(Job.employment_type).all()
        
        # Статистика по уровням опыта
        experience_stats = db.query(
            Job.experience_level,
            func.count(Job.id).label('count')
        ).filter(Job.experience_level.isnot(None)).group_by(Job.experience_level).all()
        
        # Топ локаций
        location_stats = db.query(
            Job.location,
            func.count(Job.id).label('count')
        ).filter(Job.location.isnot(None)).group_by(Job.location).order_by(
            desc(func.count(Job.id))
        ).limit(10).all()
        
        # Статистика по удаленной работе
        remote_stats = db.query(
            Job.remote_allowed,
            func.count(Job.id).label('count')
        ).group_by(Job.remote_allowed).all()
        
        return {
            "total_jobs": total_jobs,
            "jobs_last_24h": jobs_last_24h,
            "sites": [{"site": site, "count": count} for site, count in sites_stats],
            "employment_types": [{"type": emp_type, "count": count} for emp_type, count in employment_stats],
            "experience_levels": [{"level": level, "count": count} for level, count in experience_stats],
            "top_locations": [{"location": location, "count": count} for location, count in location_stats],
            "remote_work": [{"remote_allowed": remote, "count": count} for remote, count in remote_stats],
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики вакансий: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении статистики"
        )


@router.get("/similar/{job_id}")
async def get_similar_jobs(
    job_id: int,
    limit: int = Query(5, ge=1, le=20, description="Количество похожих вакансий"),
    db: Session = Depends(get_db)
):
    """Получение похожих вакансий."""
    try:
        # Получаем исходную вакансию
        source_job = db.query(Job).filter(Job.id == job_id).first()
        
        if not source_job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Вакансия не найдена"
            )
        
        # Ищем похожие вакансии по различным критериям
        similar_query = db.query(Job).filter(Job.id != job_id)
        
        # Критерии похожести (в порядке приоритета)
        conditions = []
        
        # 1. Та же компания
        if source_job.company_id:
            conditions.append(Job.company_id == source_job.company_id)
        
        # 2. Похожее название (содержит ключевые слова)
        if source_job.job_title:
            title_words = source_job.job_title.lower().split()
            for word in title_words:
                if len(word) > 3:  # Игнорируем короткие слова
                    conditions.append(Job.job_title.ilike(f"%{word}%"))
        
        # 3. Та же локация
        if source_job.location:
            conditions.append(Job.location.ilike(f"%{source_job.location}%"))
        
        # 4. Тот же уровень опыта
        if source_job.experience_level:
            conditions.append(Job.experience_level == source_job.experience_level)
        
        # 5. Тот же тип занятости
        if source_job.employment_type:
            conditions.append(Job.employment_type == source_job.employment_type)
        
        # Применяем условия с OR (чем больше совпадений, тем выше в результатах)
        if conditions:
            similar_query = similar_query.filter(or_(*conditions))
        
        # Сортируем по дате создания (новые первыми)
        similar_jobs = similar_query.order_by(desc(Job.created_at)).limit(limit).options(
            joinedload(Job.company)
        ).all()
        
        # Преобразуем в краткий формат
        result = []
        for job in similar_jobs:
            result.append(JobSummary(
                id=job.id,
                job_title=job.job_title,
                company_name=job.company.name,
                location=job.location,
                salary=job.salary,
                posted_date=job.posted_date,
                remote_allowed=job.remote_allowed,
                source_site=job.source_site
            ))
        
        return {
            "source_job_id": job_id,
            "similar_jobs": result,
            "total_found": len(result)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при поиске похожих вакансий для {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при поиске похожих вакансий"
        )
