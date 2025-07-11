"""
Общие модели данных для всех сервисов.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
import hashlib

Base = declarative_base()


class Company(Base):
    """Модель компании."""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    website = Column(String(500))
    description = Column(Text)
    location = Column(String(255))
    industry = Column(String(255))
    size = Column(String(100))  # e.g., "1-10", "11-50", "51-200"
    logo_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    jobs = relationship("Job", back_populates="company")


class Job(Base):
    """Модель вакансии."""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    job_title = Column(String(255), nullable=False, index=True)
    location = Column(String(255), index=True)
    posted_date = Column(DateTime, index=True)
    job_url = Column(String(1000), nullable=False, unique=True, index=True)
    job_url_hash = Column(String(64), nullable=False, unique=True, index=True)
    description = Column(Text)
    salary = Column(String(255))
    employment_type = Column(String(100))  # full-time, part-time, contract
    experience_level = Column(String(100))  # junior, middle, senior
    remote_allowed = Column(Boolean, default=False)
    skills = Column(Text)  # JSON string of skills array
    source_site = Column(String(255), nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company = relationship("Company", back_populates="jobs")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.job_url and not self.job_url_hash:
            self.job_url_hash = hashlib.sha256(self.job_url.encode()).hexdigest()


class ScrapeLog(Base):
    """Модель логов скрапинга."""
    __tablename__ = "scrape_logs"

    id = Column(Integer, primary_key=True, index=True)
    site = Column(String(255), nullable=False, index=True)
    spider_name = Column(String(255), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    status = Column(String(50), nullable=False, index=True)  # running, completed, failed
    items_scraped = Column(Integer, default=0)
    items_dropped = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    error_message = Column(Text)
    duration_seconds = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


# Pydantic модели для API
class CompanyBase(BaseModel):
    name: str = Field(..., max_length=255)
    website: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=255)
    industry: Optional[str] = Field(None, max_length=255)
    size: Optional[str] = Field(None, max_length=100)
    logo_url: Optional[str] = Field(None, max_length=500)


class CompanyCreate(CompanyBase):
    pass


class CompanyResponse(CompanyBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JobBase(BaseModel):
    job_title: str = Field(..., max_length=255)
    location: Optional[str] = Field(None, max_length=255)
    posted_date: Optional[datetime] = None
    job_url: str = Field(..., max_length=1000)
    description: Optional[str] = None
    salary: Optional[str] = Field(None, max_length=255)
    employment_type: Optional[str] = Field(None, max_length=100)
    experience_level: Optional[str] = Field(None, max_length=100)
    remote_allowed: bool = False
    skills: Optional[str] = None
    source_site: str = Field(..., max_length=255)


class JobCreate(JobBase):
    company_id: int


class JobResponse(JobBase):
    id: int
    company_id: int
    job_url_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    company: Optional[CompanyResponse] = None

    class Config:
        from_attributes = True


class ScrapeLogBase(BaseModel):
    site: str = Field(..., max_length=255)
    spider_name: str = Field(..., max_length=255)
    start_time: datetime
    status: str = Field(..., max_length=50)


class ScrapeLogCreate(ScrapeLogBase):
    pass


class ScrapeLogUpdate(BaseModel):
    end_time: Optional[datetime] = None
    status: Optional[str] = Field(None, max_length=50)
    items_scraped: Optional[int] = None
    items_dropped: Optional[int] = None
    errors_count: Optional[int] = None
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None


class ScrapeLogResponse(ScrapeLogBase):
    id: int
    end_time: Optional[datetime] = None
    items_scraped: int
    items_dropped: int
    errors_count: int
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Модели для фильтрации и пагинации
class JobFilters(BaseModel):
    keyword: Optional[str] = None
    location: Optional[str] = None
    company_id: Optional[int] = None
    source_site: Optional[str] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    remote_allowed: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    is_active: bool = True


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def create(cls, items: list, total: int, page: int, size: int):
        pages = (total + size - 1) // size
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages
        )


# Модели для статистики
class ScrapeStats(BaseModel):
    total_jobs: int
    active_jobs: int
    total_companies: int
    jobs_today: int
    jobs_this_week: int
    last_scrape_time: Optional[datetime] = None
    scrape_success_rate: float
    top_companies: list[dict]
    top_locations: list[dict]
