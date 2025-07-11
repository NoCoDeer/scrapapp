"""
Роутер для поиска вакансий.
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc

# Добавляем путь к shared модулям
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.database import get_db_session
from shared.models import Job, Company
from shared.config import settings
from shared.logging_config import get_logger
from api.schemas import SearchResponse, SearchResult, ElasticsearchQuery

logger = get_logger(__name__)

router = APIRouter()


def get_db():
    """Dependency для получения сессии базы данных."""
    with get_db_session() as session:
        yield session


@router.get("", response_model=SearchResponse)
async def search_jobs(
    q: str = Query(..., description="Поисковый запрос"),
    location: Optional[str] = Query(None, description="Местоположение"),
    company: Optional[str] = Query(None, description="Компания"),
    employment_type: Optional[str] = Query(None, description="Тип занятости"),
    experience_level: Optional[str] = Query(None, description="Уровень опыта"),
    remote_allowed: Optional[bool] = Query(None, description="Удаленная работа"),
    source_site: Optional[str] = Query(None, description="Источник"),
    date_from: Optional[datetime] = Query(None, description="Дата публикации от"),
    date_to: Optional[datetime] = Query(None, description="Дата публикации до"),
    size: int = Query(20, ge=1, le=100, description="Количество результатов"),
    from_: int = Query(0, ge=0, description="Смещение", alias="from"),
    use_elasticsearch: bool = Query(True, description="Использовать Elasticsearch"),
    db: Session = Depends(get_db)
):
    """
    Поиск вакансий по ключевым словам.
    
    Поддерживает как полнотекстовый поиск через Elasticsearch,
    так и поиск по базе данных PostgreSQL.
    """
    start_time = datetime.utcnow()
    
    try:
        # Пытаемся использовать Elasticsearch если настроен и запрошен
        if use_elasticsearch and settings.elasticsearch_url:
            try:
                results = await _search_with_elasticsearch(
                    query=q,
                    location=location,
                    company=company,
                    employment_type=employment_type,
                    experience_level=experience_level,
                    remote_allowed=remote_allowed,
                    source_site=source_site,
                    date_from=date_from,
                    date_to=date_to,
                    size=size,
                    from_=from_
                )
                
                end_time = datetime.utcnow()
                took = int((end_time - start_time).total_seconds() * 1000)
                
                return SearchResponse(
                    results=results["hits"],
                    total=results["total"],
                    query=q,
                    took=took
                )
                
            except Exception as e:
                logger.warning(f"Elasticsearch поиск не удался, переключаемся на PostgreSQL: {e}")
                # Fallback на PostgreSQL поиск
        
        # Поиск через PostgreSQL
        results = await _search_with_postgresql(
            query=q,
            location=location,
            company=company,
            employment_type=employment_type,
            experience_level=experience_level,
            remote_allowed=remote_allowed,
            source_site=source_site,
            date_from=date_from,
            date_to=date_to,
            size=size,
            from_=from_,
            db=db
        )
        
        end_time = datetime.utcnow()
        took = int((end_time - start_time).total_seconds() * 1000)
        
        return SearchResponse(
            results=results["hits"],
            total=results["total"],
            query=q,
            took=took
        )
        
    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при выполнении поиска"
        )


async def _search_with_elasticsearch(
    query: str,
    location: Optional[str] = None,
    company: Optional[str] = None,
    employment_type: Optional[str] = None,
    experience_level: Optional[str] = None,
    remote_allowed: Optional[bool] = None,
    source_site: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    size: int = 20,
    from_: int = 0
) -> Dict[str, Any]:
    """Поиск через Elasticsearch."""
    from elasticsearch import Elasticsearch
    
    es = Elasticsearch([settings.elasticsearch_url])
    
    # Строим запрос
    search_body = {
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": [
                                "job_title^3",  # Больший вес для названия
                                "description^2",
                                "company_name^2",
                                "skills"
                            ],
                            "type": "best_fields",
                            "fuzziness": "AUTO"
                        }
                    }
                ],
                "filter": []
            }
        },
        "highlight": {
            "fields": {
                "job_title": {},
                "description": {"fragment_size": 150},
                "company_name": {}
            }
        },
        "sort": [
            {"_score": {"order": "desc"}},
            {"posted_date": {"order": "desc"}}
        ],
        "size": size,
        "from": from_
    }
    
    # Добавляем фильтры
    filters = search_body["query"]["bool"]["filter"]
    
    if location:
        filters.append({
            "match": {
                "location": {
                    "query": location,
                    "fuzziness": "AUTO"
                }
            }
        })
    
    if company:
        filters.append({
            "match": {
                "company_name": {
                    "query": company,
                    "fuzziness": "AUTO"
                }
            }
        })
    
    if employment_type:
        filters.append({"term": {"employment_type": employment_type}})
    
    if experience_level:
        filters.append({"term": {"experience_level": experience_level}})
    
    if remote_allowed is not None:
        filters.append({"term": {"remote_allowed": remote_allowed}})
    
    if source_site:
        filters.append({"term": {"source_site": source_site}})
    
    if date_from or date_to:
        date_range = {}
        if date_from:
            date_range["gte"] = date_from.isoformat()
        if date_to:
            date_range["lte"] = date_to.isoformat()
        
        filters.append({
            "range": {
                "posted_date": date_range
            }
        })
    
    # Выполняем поиск
    response = es.search(
        index="jobs",  # Предполагаем, что индекс называется "jobs"
        body=search_body
    )
    
    # Преобразуем результаты
    hits = []
    for hit in response["hits"]["hits"]:
        source = hit["_source"]
        
        result = SearchResult(
            id=source["id"],
            job_title=source["job_title"],
            company_name=source["company_name"],
            location=source.get("location"),
            description=source.get("description"),
            salary=source.get("salary"),
            posted_date=datetime.fromisoformat(source["posted_date"]) if source.get("posted_date") else None,
            source_site=source["source_site"],
            score=hit["_score"]
        )
        
        hits.append(result)
    
    return {
        "hits": hits,
        "total": response["hits"]["total"]["value"]
    }


async def _search_with_postgresql(
    query: str,
    location: Optional[str] = None,
    company: Optional[str] = None,
    employment_type: Optional[str] = None,
    experience_level: Optional[str] = None,
    remote_allowed: Optional[bool] = None,
    source_site: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    size: int = 20,
    from_: int = 0,
    db: Session = None
) -> Dict[str, Any]:
    """Поиск через PostgreSQL с полнотекстовым поиском."""
    
    # Базовый запрос с join к компании
    base_query = db.query(Job).join(Company)
    
    # Полнотекстовый поиск по нескольким полям
    search_conditions = []
    
    # Разбиваем запрос на слова для более гибкого поиска
    query_words = query.lower().split()
    
    for word in query_words:
        if len(word) > 2:  # Игнорируем очень короткие слова
            word_conditions = or_(
                Job.job_title.ilike(f"%{word}%"),
                Job.description.ilike(f"%{word}%"),
                Company.name.ilike(f"%{word}%"),
                Job.skills.any(func.lower(func.unnest(Job.skills)).like(f"%{word}%"))
            )
            search_conditions.append(word_conditions)
    
    if search_conditions:
        # Используем AND для всех слов (все слова должны встречаться)
        search_query = base_query.filter(and_(*search_conditions))
    else:
        search_query = base_query
    
    # Применяем дополнительные фильтры
    if location:
        search_query = search_query.filter(Job.location.ilike(f"%{location}%"))
    
    if company:
        search_query = search_query.filter(Company.name.ilike(f"%{company}%"))
    
    if employment_type:
        search_query = search_query.filter(Job.employment_type == employment_type)
    
    if experience_level:
        search_query = search_query.filter(Job.experience_level == experience_level)
    
    if remote_allowed is not None:
        search_query = search_query.filter(Job.remote_allowed == remote_allowed)
    
    if source_site:
        search_query = search_query.filter(Job.source_site == source_site)
    
    if date_from:
        search_query = search_query.filter(Job.posted_date >= date_from)
    
    if date_to:
        search_query = search_query.filter(Job.posted_date <= date_to)
    
    # Подсчет общего количества
    total = search_query.count()
    
    # Сортировка по релевантности (приблизительная)
    # Сначала по точному совпадению в названии, потом по дате
    search_query = search_query.order_by(
        desc(Job.job_title.ilike(f"%{query}%")),  # Точное совпадение в названии
        desc(Job.posted_date),  # Затем по дате
        desc(Job.created_at)  # И по дате создания
    )
    
    # Применяем пагинацию
    jobs = search_query.offset(from_).limit(size).options(joinedload(Job.company)).all()
    
    # Преобразуем результаты
    hits = []
    for job in jobs:
        # Простой расчет релевантности
        score = 1.0
        
        # Увеличиваем score если запрос найден в названии
        if query.lower() in job.job_title.lower():
            score += 2.0
        
        # Увеличиваем score если запрос найден в названии компании
        if query.lower() in job.company.name.lower():
            score += 1.0
        
        # Увеличиваем score для новых вакансий
        days_old = (datetime.utcnow() - job.created_at).days
        if days_old < 7:
            score += 0.5
        elif days_old < 30:
            score += 0.2
        
        result = SearchResult(
            id=job.id,
            job_title=job.job_title,
            company_name=job.company.name,
            location=job.location,
            description=job.description,
            salary=job.salary,
            posted_date=job.posted_date,
            source_site=job.source_site,
            score=score
        )
        
        hits.append(result)
    
    # Сортируем по score (в реальности это уже сделано в SQL)
    hits.sort(key=lambda x: x.score, reverse=True)
    
    return {
        "hits": hits,
        "total": total
    }


@router.get("/suggestions")
async def get_search_suggestions(
    q: str = Query(..., min_length=2, description="Частичный запрос"),
    type: str = Query("all", description="Тип предложений: all, jobs, companies, locations"),
    limit: int = Query(10, ge=1, le=50, description="Количество предложений"),
    db: Session = Depends(get_db)
):
    """
    Получение предложений для автодополнения поиска.
    """
    try:
        suggestions = []
        
        if type in ["all", "jobs"]:
            # Предложения по названиям вакансий
            job_suggestions = db.query(Job.job_title).filter(
                Job.job_title.ilike(f"%{q}%")
            ).distinct().limit(limit // 3 if type == "all" else limit).all()
            
            for (title,) in job_suggestions:
                suggestions.append({
                    "text": title,
                    "type": "job_title",
                    "category": "Вакансии"
                })
        
        if type in ["all", "companies"]:
            # Предложения по названиям компаний
            company_suggestions = db.query(Company.name).filter(
                Company.name.ilike(f"%{q}%")
            ).distinct().limit(limit // 3 if type == "all" else limit).all()
            
            for (name,) in company_suggestions:
                suggestions.append({
                    "text": name,
                    "type": "company",
                    "category": "Компании"
                })
        
        if type in ["all", "locations"]:
            # Предложения по локациям
            location_suggestions = db.query(Job.location).filter(
                Job.location.ilike(f"%{q}%"),
                Job.location.isnot(None)
            ).distinct().limit(limit // 3 if type == "all" else limit).all()
            
            for (location,) in location_suggestions:
                suggestions.append({
                    "text": location,
                    "type": "location",
                    "category": "Локации"
                })
        
        # Ограничиваем общее количество
        suggestions = suggestions[:limit]
        
        return {
            "query": q,
            "suggestions": suggestions,
            "total": len(suggestions)
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении предложений: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении предложений"
        )


@router.get("/trending")
async def get_trending_searches(
    period: str = Query("week", description="Период: day, week, month"),
    limit: int = Query(10, ge=1, le=50, description="Количество результатов"),
    db: Session = Depends(get_db)
):
    """
    Получение популярных поисковых запросов.
    
    Примечание: В реальном приложении здесь бы использовались
    логи поисковых запросов. Сейчас возвращаем популярные термины
    из данных.
    """
    try:
        # Определяем период
        if period == "day":
            days = 1
        elif period == "week":
            days = 7
        elif period == "month":
            days = 30
        else:
            days = 7
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Популярные названия вакансий
        popular_jobs = db.query(
            Job.job_title,
            func.count(Job.id).label('count')
        ).filter(
            Job.created_at >= cutoff_date
        ).group_by(Job.job_title).order_by(
            desc(func.count(Job.id))
        ).limit(limit).all()
        
        # Популярные компании
        popular_companies = db.query(
            Company.name,
            func.count(Job.id).label('count')
        ).join(Job).filter(
            Job.created_at >= cutoff_date
        ).group_by(Company.name).order_by(
            desc(func.count(Job.id))
        ).limit(limit).all()
        
        # Популярные локации
        popular_locations = db.query(
            Job.location,
            func.count(Job.id).label('count')
        ).filter(
            Job.created_at >= cutoff_date,
            Job.location.isnot(None)
        ).group_by(Job.location).order_by(
            desc(func.count(Job.id))
        ).limit(limit).all()
        
        return {
            "period": period,
            "trending": {
                "job_titles": [
                    {"term": title, "count": count}
                    for title, count in popular_jobs
                ],
                "companies": [
                    {"term": name, "count": count}
                    for name, count in popular_companies
                ],
                "locations": [
                    {"term": location, "count": count}
                    for location, count in popular_locations
                ]
            },
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении популярных запросов: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении популярных запросов"
        )


@router.post("/elasticsearch", response_model=SearchResponse)
async def advanced_elasticsearch_search(
    search_query: ElasticsearchQuery
):
    """
    Расширенный поиск через Elasticsearch с кастомными параметрами.
    
    Позволяет передать сложные запросы и фильтры напрямую в Elasticsearch.
    """
    try:
        if not settings.elasticsearch_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Elasticsearch не настроен"
            )
        
        from elasticsearch import Elasticsearch
        
        es = Elasticsearch([settings.elasticsearch_url])
        
        # Строим запрос на основе переданных параметров
        search_body = {
            "query": {
                "multi_match": {
                    "query": search_query.query,
                    "fields": ["job_title^3", "description^2", "company_name^2", "skills"],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            },
            "size": search_query.size,
            "from": search_query.from_
        }
        
        # Добавляем фильтры если есть
        if search_query.filters:
            search_body["query"] = {
                "bool": {
                    "must": [search_body["query"]],
                    "filter": search_query.filters
                }
            }
        
        # Добавляем сортировку если есть
        if search_query.sort:
            search_body["sort"] = search_query.sort
        else:
            search_body["sort"] = [
                {"_score": {"order": "desc"}},
                {"posted_date": {"order": "desc"}}
            ]
        
        # Добавляем подсветку
        search_body["highlight"] = {
            "fields": {
                "job_title": {},
                "description": {"fragment_size": 150},
                "company_name": {}
            }
        }
        
        start_time = datetime.utcnow()
        
        # Выполняем поиск
        response = es.search(
            index="jobs",
            body=search_body
        )
        
        end_time = datetime.utcnow()
        took = int((end_time - start_time).total_seconds() * 1000)
        
        # Преобразуем результаты
        hits = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            
            result = SearchResult(
                id=source["id"],
                job_title=source["job_title"],
                company_name=source["company_name"],
                location=source.get("location"),
                description=source.get("description"),
                salary=source.get("salary"),
                posted_date=datetime.fromisoformat(source["posted_date"]) if source.get("posted_date") else None,
                source_site=source["source_site"],
                score=hit["_score"]
            )
            
            hits.append(result)
        
        return SearchResponse(
            results=hits,
            total=response["hits"]["total"]["value"],
            query=search_query.query,
            took=took
        )
        
    except Exception as e:
        logger.error(f"Ошибка при расширенном поиске: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при выполнении расширенного поиска"
        )
