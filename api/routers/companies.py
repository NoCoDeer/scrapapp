"""
Роутер для работы с компаниями.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, asc

# Добавляем путь к shared модулям
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.database import get_db_session
from shared.models import Job, Company
from shared.logging_config import get_logger
from api.schemas import (
    Company as CompanySchema,
    CompaniesResponse,
    CompanyCreate,
    CompanyUpdate,
    JobSummary
)

logger = get_logger(__name__)

router = APIRouter()


def get_db():
    """Dependency для получения сессии базы данных."""
    with get_db_session() as session:
        yield session


@router.get("", response_model=CompaniesResponse)
async def get_companies(
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(20, ge=1, le=100, description="Размер страницы"),
    name: Optional[str] = Query(None, description="Название компании"),
    industry: Optional[str] = Query(None, description="Отрасль"),
    location: Optional[str] = Query(None, description="Местоположение"),
    size_filter: Optional[str] = Query(None, description="Размер компании", alias="company_size"),
    has_jobs: Optional[bool] = Query(None, description="Только компании с вакансиями"),
    sort_by: str = Query("name", description="Поле для сортировки"),
    sort_order: str = Query("asc", description="Порядок сортировки (asc/desc)"),
    db: Session = Depends(get_db)
):
    """
    Получение списка компаний с фильтрацией и пагинацией.
    
    Поддерживаемые поля для сортировки:
    - name (по умолчанию)
    - created_at
    - jobs_count
    - industry
    - location
    """
    try:
        # Базовый запрос с подсчетом вакансий
        query = db.query(
            Company,
            func.count(Job.id).label('jobs_count')
        ).outerjoin(Job).group_by(Company.id)
        
        # Применяем фильтры
        if name:
            query = query.filter(Company.name.ilike(f"%{name}%"))
        
        if industry:
            query = query.filter(Company.industry.ilike(f"%{industry}%"))
        
        if location:
            query = query.filter(Company.location.ilike(f"%{location}%"))
        
        if size_filter:
            query = query.filter(Company.size == size_filter)
        
        if has_jobs is not None:
            if has_jobs:
                query = query.having(func.count(Job.id) > 0)
            else:
                query = query.having(func.count(Job.id) == 0)
        
        # Сортировка
        if sort_by == "jobs_count":
            sort_column = func.count(Job.id)
        else:
            sort_column = getattr(Company, sort_by, Company.name)
        
        if sort_order.lower() == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        
        # Подсчет общего количества
        total = query.count()
        
        # Применяем пагинацию
        offset = (page - 1) * size
        results = query.offset(offset).limit(size).all()
        
        # Преобразуем результаты
        companies = []
        for company, jobs_count in results:
            company_dict = {
                "id": company.id,
                "name": company.name,
                "website": company.website,
                "description": company.description,
                "location": company.location,
                "industry": company.industry,
                "size": company.size,
                "logo_url": company.logo_url,
                "created_at": company.created_at,
                "updated_at": company.updated_at,
                "jobs_count": jobs_count
            }
            companies.append(CompanySchema(**company_dict))
        
        # Вычисляем метаданные пагинации
        pages = ceil(total / size)
        has_next = page < pages
        has_prev = page > 1
        
        return CompaniesResponse(
            items=companies,
            total=total,
            page=page,
            size=size,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка компаний: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении списка компаний"
        )


@router.get("/{company_id}", response_model=CompanySchema)
async def get_company(
    company_id: int,
    db: Session = Depends(get_db)
):
    """Получение детальной информации о компании."""
    try:
        # Получаем компанию с подсчетом вакансий
        result = db.query(
            Company,
            func.count(Job.id).label('jobs_count')
        ).outerjoin(Job).filter(Company.id == company_id).group_by(Company.id).first()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Компания не найдена"
            )
        
        company, jobs_count = result
        
        # Создаем схему с количеством вакансий
        company_dict = {
            "id": company.id,
            "name": company.name,
            "website": company.website,
            "description": company.description,
            "location": company.location,
            "industry": company.industry,
            "size": company.size,
            "logo_url": company.logo_url,
            "created_at": company.created_at,
            "updated_at": company.updated_at,
            "jobs_count": jobs_count
        }
        
        return CompanySchema(**company_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении компании {company_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении компании"
        )


@router.get("/{company_id}/jobs")
async def get_company_jobs(
    company_id: int,
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(20, ge=1, le=100, description="Размер страницы"),
    active_only: bool = Query(True, description="Только активные вакансии"),
    db: Session = Depends(get_db)
):
    """Получение вакансий компании."""
    try:
        # Проверяем существование компании
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Компания не найдена"
            )
        
        # Запрос вакансий компании
        query = db.query(Job).filter(Job.company_id == company_id)
        
        if active_only:
            # Считаем активными вакансии, опубликованные не более 30 дней назад
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            query = query.filter(Job.posted_date >= cutoff_date)
        
        # Сортируем по дате создания (новые первыми)
        query = query.order_by(desc(Job.created_at))
        
        # Подсчет общего количества
        total = query.count()
        
        # Применяем пагинацию
        offset = (page - 1) * size
        jobs = query.offset(offset).limit(size).all()
        
        # Преобразуем в краткий формат
        job_summaries = []
        for job in jobs:
            job_summaries.append(JobSummary(
                id=job.id,
                job_title=job.job_title,
                company_name=company.name,
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
        
        return {
            "company": {
                "id": company.id,
                "name": company.name,
                "website": company.website,
                "location": company.location
            },
            "jobs": {
                "items": job_summaries,
                "total": total,
                "page": page,
                "size": size,
                "pages": pages,
                "has_next": has_next,
                "has_prev": has_prev
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении вакансий компании {company_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении вакансий компании"
        )


@router.post("", response_model=CompanySchema, status_code=status.HTTP_201_CREATED)
async def create_company(
    company_data: CompanyCreate,
    db: Session = Depends(get_db)
):
    """Создание новой компании."""
    try:
        # Проверяем уникальность названия
        existing_company = db.query(Company).filter(Company.name == company_data.name).first()
        if existing_company:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Компания с таким названием уже существует"
            )
        
        # Создаем новую компанию
        company = Company(**company_data.model_dump())
        db.add(company)
        db.commit()
        db.refresh(company)
        
        # Создаем схему с количеством вакансий (0 для новой компании)
        company_dict = {
            "id": company.id,
            "name": company.name,
            "website": company.website,
            "description": company.description,
            "location": company.location,
            "industry": company.industry,
            "size": company.size,
            "logo_url": company.logo_url,
            "created_at": company.created_at,
            "updated_at": company.updated_at,
            "jobs_count": 0
        }
        
        logger.info(f"Создана новая компания: {company.id}")
        return CompanySchema(**company_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при создании компании: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при создании компании"
        )


@router.put("/{company_id}", response_model=CompanySchema)
async def update_company(
    company_id: int,
    company_data: CompanyUpdate,
    db: Session = Depends(get_db)
):
    """Обновление компании."""
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Компания не найдена"
            )
        
        # Проверяем уникальность названия (если оно изменяется)
        if company_data.name and company_data.name != company.name:
            existing_company = db.query(Company).filter(
                Company.name == company_data.name,
                Company.id != company_id
            ).first()
            if existing_company:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Компания с таким названием уже существует"
                )
        
        # Обновляем только переданные поля
        update_data = company_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(company, field, value)
        
        company.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(company)
        
        # Получаем количество вакансий
        jobs_count = db.query(func.count(Job.id)).filter(Job.company_id == company_id).scalar()
        
        # Создаем схему с количеством вакансий
        company_dict = {
            "id": company.id,
            "name": company.name,
            "website": company.website,
            "description": company.description,
            "location": company.location,
            "industry": company.industry,
            "size": company.size,
            "logo_url": company.logo_url,
            "created_at": company.created_at,
            "updated_at": company.updated_at,
            "jobs_count": jobs_count
        }
        
        logger.info(f"Обновлена компания: {company.id}")
        return CompanySchema(**company_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при обновлении компании {company_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при обновлении компании"
        )


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: int,
    force: bool = Query(False, description="Принудительное удаление с вакансиями"),
    db: Session = Depends(get_db)
):
    """Удаление компании."""
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Компания не найдена"
            )
        
        # Проверяем наличие вакансий
        jobs_count = db.query(func.count(Job.id)).filter(Job.company_id == company_id).scalar()
        
        if jobs_count > 0 and not force:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Нельзя удалить компанию с {jobs_count} вакансиями. Используйте force=true для принудительного удаления."
            )
        
        # Удаляем все вакансии компании (если force=true)
        if force and jobs_count > 0:
            db.query(Job).filter(Job.company_id == company_id).delete()
        
        # Удаляем компанию
        db.delete(company)
        db.commit()
        
        logger.info(f"Удалена компания: {company_id} (с {jobs_count} вакансиями)")
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при удалении компании {company_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при удалении компании"
        )


@router.get("/stats/summary")
async def get_companies_stats(
    db: Session = Depends(get_db)
):
    """Получение статистики по компаниям."""
    try:
        # Общая статистика
        total_companies = db.query(func.count(Company.id)).scalar()
        
        # Компании с вакансиями
        companies_with_jobs = db.query(func.count(func.distinct(Job.company_id))).scalar()
        
        # Статистика по отраслям
        industry_stats = db.query(
            Company.industry,
            func.count(Company.id).label('count')
        ).filter(Company.industry.isnot(None)).group_by(Company.industry).order_by(
            desc(func.count(Company.id))
        ).limit(10).all()
        
        # Статистика по размерам компаний
        size_stats = db.query(
            Company.size,
            func.count(Company.id).label('count')
        ).filter(Company.size.isnot(None)).group_by(Company.size).all()
        
        # Топ компаний по количеству вакансий
        top_companies = db.query(
            Company.name,
            func.count(Job.id).label('jobs_count')
        ).join(Job).group_by(Company.id, Company.name).order_by(
            desc(func.count(Job.id))
        ).limit(10).all()
        
        # Топ локаций компаний
        location_stats = db.query(
            Company.location,
            func.count(Company.id).label('count')
        ).filter(Company.location.isnot(None)).group_by(Company.location).order_by(
            desc(func.count(Company.id))
        ).limit(10).all()
        
        return {
            "total_companies": total_companies,
            "companies_with_jobs": companies_with_jobs,
            "companies_without_jobs": total_companies - companies_with_jobs,
            "industries": [{"industry": industry, "count": count} for industry, count in industry_stats],
            "company_sizes": [{"size": size, "count": count} for size, count in size_stats],
            "top_companies": [{"name": name, "jobs_count": count} for name, count in top_companies],
            "top_locations": [{"location": location, "count": count} for location, count in location_stats],
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики компаний: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении статистики"
        )
