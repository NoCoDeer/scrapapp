"""
Pydantic схемы для API.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class JobBase(BaseModel):
    """Базовая схема вакансии."""
    job_title: str = Field(..., description="Название вакансии")
    location: Optional[str] = Field(None, description="Местоположение")
    posted_date: Optional[datetime] = Field(None, description="Дата публикации")
    job_url: str = Field(..., description="URL вакансии")
    description: Optional[str] = Field(None, description="Описание вакансии")
    salary: Optional[str] = Field(None, description="Зарплата")
    employment_type: Optional[str] = Field(None, description="Тип занятости")
    experience_level: Optional[str] = Field(None, description="Уровень опыта")
    remote_allowed: bool = Field(False, description="Возможность удаленной работы")
    skills: Optional[List[str]] = Field(None, description="Навыки")
    source_site: str = Field(..., description="Источник")


class JobCreate(JobBase):
    """Схема для создания вакансии."""
    company_id: int = Field(..., description="ID компании")


class JobUpdate(BaseModel):
    """Схема для обновления вакансии."""
    job_title: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    salary: Optional[str] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    remote_allowed: Optional[bool] = None
    skills: Optional[List[str]] = None


class CompanyBase(BaseModel):
    """Базовая схема компании."""
    name: str = Field(..., description="Название компании")
    website: Optional[str] = Field(None, description="Веб-сайт")
    description: Optional[str] = Field(None, description="Описание")
    location: Optional[str] = Field(None, description="Местоположение")
    industry: Optional[str] = Field(None, description="Отрасль")
    size: Optional[str] = Field(None, description="Размер компании")
    logo_url: Optional[str] = Field(None, description="URL логотипа")


class CompanyCreate(CompanyBase):
    """Схема для создания компании."""
    pass


class CompanyUpdate(BaseModel):
    """Схема для обновления компании."""
    name: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    logo_url: Optional[str] = None


class Company(CompanyBase):
    """Схема компании с ID."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="ID компании")
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: datetime = Field(..., description="Дата обновления")
    jobs_count: Optional[int] = Field(None, description="Количество вакансий")


class Job(JobBase):
    """Схема вакансии с ID и компанией."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="ID вакансии")
    company_id: int = Field(..., description="ID компании")
    company: Company = Field(..., description="Информация о компании")
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: datetime = Field(..., description="Дата обновления")


class JobSummary(BaseModel):
    """Краткая информация о вакансии."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    job_title: str
    company_name: str
    location: Optional[str]
    salary: Optional[str]
    posted_date: Optional[datetime]
    remote_allowed: bool
    source_site: str


class JobFilters(BaseModel):
    """Фильтры для поиска вакансий."""
    keyword: Optional[str] = Field(None, description="Ключевое слово для поиска")
    location: Optional[str] = Field(None, description="Местоположение")
    company: Optional[str] = Field(None, description="Название компании")
    salary_min: Optional[int] = Field(None, description="Минимальная зарплата")
    salary_max: Optional[int] = Field(None, description="Максимальная зарплата")
    employment_type: Optional[str] = Field(None, description="Тип занятости")
    experience_level: Optional[str] = Field(None, description="Уровень опыта")
    remote_allowed: Optional[bool] = Field(None, description="Удаленная работа")
    source_site: Optional[str] = Field(None, description="Источник")
    date_from: Optional[datetime] = Field(None, description="Дата публикации от")
    date_to: Optional[datetime] = Field(None, description="Дата публикации до")
    skills: Optional[List[str]] = Field(None, description="Навыки")


class PaginationParams(BaseModel):
    """Параметры пагинации."""
    page: int = Field(1, ge=1, description="Номер страницы")
    size: int = Field(20, ge=1, le=100, description="Размер страницы")


class PaginatedResponse(BaseModel):
    """Ответ с пагинацией."""
    items: List[Any] = Field(..., description="Элементы")
    total: int = Field(..., description="Общее количество")
    page: int = Field(..., description="Текущая страница")
    size: int = Field(..., description="Размер страницы")
    pages: int = Field(..., description="Общее количество страниц")
    has_next: bool = Field(..., description="Есть ли следующая страница")
    has_prev: bool = Field(..., description="Есть ли предыдущая страница")


class JobsResponse(PaginatedResponse):
    """Ответ со списком вакансий."""
    items: List[JobSummary]


class CompaniesResponse(PaginatedResponse):
    """Ответ со списком компаний."""
    items: List[Company]


class SearchResult(BaseModel):
    """Результат поиска."""
    id: int
    job_title: str
    company_name: str
    location: Optional[str]
    description: Optional[str]
    salary: Optional[str]
    posted_date: Optional[datetime]
    source_site: str
    score: float = Field(..., description="Релевантность")


class SearchResponse(BaseModel):
    """Ответ поиска."""
    results: List[SearchResult]
    total: int
    query: str
    took: int = Field(..., description="Время выполнения в мс")


class StatsResponse(BaseModel):
    """Статистика системы."""
    total_jobs: int
    total_companies: int
    jobs_last_24h: int
    sites_stats: List[Dict[str, Any]]
    scraping_stats: Dict[str, Any]
    top_companies: List[Dict[str, Any]]
    generated_at: datetime


class HealthCheck(BaseModel):
    """Проверка здоровья системы."""
    status: str = Field(..., description="Статус системы")
    timestamp: datetime = Field(..., description="Время проверки")
    checks: Dict[str, str] = Field(..., description="Детальные проверки")
    version: str = Field("1.0.0", description="Версия API")


class ErrorResponse(BaseModel):
    """Ответ с ошибкой."""
    error: str = Field(..., description="Описание ошибки")
    detail: Optional[str] = Field(None, description="Детали ошибки")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ScrapeLogBase(BaseModel):
    """Базовая схема лога скрапинга."""
    site: str
    spider_name: str
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    items_scraped: Optional[int] = None
    items_dropped: Optional[int] = None
    errors_count: Optional[int] = None
    error_message: Optional[str] = None


class ScrapeLog(ScrapeLogBase):
    """Схема лога скрапинга с ID."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime


class ScrapeLogsResponse(PaginatedResponse):
    """Ответ со списком логов скрапинга."""
    items: List[ScrapeLog]


class TaskStatus(BaseModel):
    """Статус задачи Celery."""
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime


class TriggerScrapeRequest(BaseModel):
    """Запрос на запуск скрапинга."""
    site: str = Field(..., description="Сайт для скрапинга")
    max_pages: Optional[int] = Field(10, description="Максимальное количество страниц")
    priority: Optional[str] = Field("normal", description="Приоритет задачи")


class TriggerScrapeResponse(BaseModel):
    """Ответ на запуск скрапинга."""
    task_id: str = Field(..., description="ID задачи")
    message: str = Field(..., description="Сообщение")
    estimated_duration: Optional[int] = Field(None, description="Ожидаемое время выполнения в секундах")


# Схемы для Elasticsearch
class ElasticsearchQuery(BaseModel):
    """Запрос к Elasticsearch."""
    query: str = Field(..., description="Поисковый запрос")
    filters: Optional[Dict[str, Any]] = Field(None, description="Фильтры")
    size: int = Field(20, ge=1, le=100, description="Количество результатов")
    from_: int = Field(0, ge=0, description="Смещение", alias="from")
    sort: Optional[List[Dict[str, str]]] = Field(None, description="Сортировка")


class MetricsResponse(BaseModel):
    """Метрики для Prometheus."""
    content: str = Field(..., description="Метрики в формате Prometheus")
    content_type: str = Field("text/plain", description="Тип контента")


# Схемы для аутентификации (если потребуется)
class APIKeyCreate(BaseModel):
    """Создание API ключа."""
    name: str = Field(..., description="Название ключа")
    description: Optional[str] = Field(None, description="Описание")
    expires_at: Optional[datetime] = Field(None, description="Дата истечения")


class APIKey(BaseModel):
    """API ключ."""
    id: int
    name: str
    key: str
    description: Optional[str]
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
