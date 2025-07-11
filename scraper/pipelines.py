"""
Pipelines для обработки данных в Scrapy.
"""
import logging
import hashlib
import json
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import urljoin, urlparse

import scrapy
from scrapy.exceptions import DropItem
from itemadapter import ItemAdapter
from sqlalchemy.exc import IntegrityError
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ElasticsearchException

from shared.database import get_db_session
from shared.models import Job, Company
from shared.config import settings
from .items import JobItem, CompanyItem

logger = logging.getLogger(__name__)


class ValidationPipeline:
    """Pipeline для валидации данных."""
    
    def __init__(self):
        self.required_fields = {
            'JobItem': ['company', 'job_title', 'job_url', 'source_site'],
            'CompanyItem': ['name', 'source_site']
        }
    
    def process_item(self, item, spider):
        """Валидация элемента."""
        adapter = ItemAdapter(item)
        item_type = type(item).__name__
        
        # Проверяем обязательные поля
        required = self.required_fields.get(item_type, [])
        for field in required:
            if not adapter.get(field):
                raise DropItem(f"Отсутствует обязательное поле '{field}' в {item_type}")
        
        # Валидация URL
        if 'job_url' in adapter:
            url = adapter['job_url']
            if not self._is_valid_url(url):
                raise DropItem(f"Некорректный URL: {url}")
        
        # Валидация даты
        if 'posted_date' in adapter and adapter['posted_date']:
            if not isinstance(adapter['posted_date'], datetime):
                try:
                    import dateparser
                    parsed_date = dateparser.parse(str(adapter['posted_date']))
                    if parsed_date:
                        adapter['posted_date'] = parsed_date
                    else:
                        adapter['posted_date'] = None
                except:
                    adapter['posted_date'] = None
        
        # Валидация remote_allowed
        if 'remote_allowed' in adapter:
            remote_value = adapter['remote_allowed']
            if isinstance(remote_value, str):
                adapter['remote_allowed'] = remote_value.lower() in ('true', 'yes', '1', 'да', 'удаленно')
            elif not isinstance(remote_value, bool):
                adapter['remote_allowed'] = False
        
        spider.logger.debug(f"Валидация пройдена для {item_type}")
        return item
    
    def _is_valid_url(self, url: str) -> bool:
        """Проверка корректности URL."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False


class DuplicationPipeline:
    """Pipeline для удаления дубликатов."""
    
    def __init__(self):
        self.seen_urls = set()
        self.seen_companies = set()
    
    def process_item(self, item, spider):
        """Проверка на дубликаты."""
        adapter = ItemAdapter(item)
        
        if isinstance(item, JobItem):
            url = adapter['job_url']
            url_hash = hashlib.sha256(url.encode()).hexdigest()
            
            if url_hash in self.seen_urls:
                raise DropItem(f"Дубликат вакансии: {url}")
            
            self.seen_urls.add(url_hash)
            adapter['job_url_hash'] = url_hash
        
        elif isinstance(item, CompanyItem):
            company_key = f"{adapter['name']}_{adapter.get('website', '')}"
            company_hash = hashlib.sha256(company_key.encode()).hexdigest()
            
            if company_hash in self.seen_companies:
                raise DropItem(f"Дубликат компании: {adapter['name']}")
            
            self.seen_companies.add(company_hash)
        
        spider.logger.debug(f"Проверка дубликатов пройдена для {type(item).__name__}")
        return item


class DatabasePipeline:
    """Pipeline для сохранения данных в базу данных."""
    
    def __init__(self):
        self.companies_cache = {}  # Кэш компаний для избежания дублирования
    
    def open_spider(self, spider):
        """Инициализация при открытии паука."""
        spider.logger.info("DatabasePipeline инициализирован")
    
    def close_spider(self, spider):
        """Очистка при закрытии паука."""
        self.companies_cache.clear()
        spider.logger.info("DatabasePipeline закрыт")
    
    def process_item(self, item, spider):
        """Сохранение элемента в базу данных."""
        try:
            if isinstance(item, JobItem):
                self._save_job(item, spider)
            elif isinstance(item, CompanyItem):
                self._save_company(item, spider)
            
            spider.logger.debug(f"Элемент сохранен в БД: {type(item).__name__}")
            return item
            
        except Exception as e:
            spider.logger.error(f"Ошибка сохранения в БД: {e}")
            raise DropItem(f"Ошибка сохранения в базу данных: {e}")
    
    def _save_job(self, item: JobItem, spider):
        """Сохранение вакансии."""
        adapter = ItemAdapter(item)
        
        with get_db_session() as session:
            # Получаем или создаем компанию
            company = self._get_or_create_company(
                name=adapter['company'],
                website=adapter.get('company_website'),
                description=adapter.get('company_description'),
                industry=adapter.get('company_industry'),
                size=adapter.get('company_size'),
                logo_url=adapter.get('company_logo_url'),
                location=adapter.get('location'),
                source_site=adapter['source_site'],
                session=session
            )
            
            # Создаем вакансию
            job = Job(
                company_id=company.id,
                job_title=adapter['job_title'],
                location=adapter.get('location'),
                posted_date=adapter.get('posted_date'),
                job_url=adapter['job_url'],
                job_url_hash=adapter.get('job_url_hash'),
                description=adapter.get('description'),
                salary=adapter.get('salary'),
                employment_type=adapter.get('employment_type'),
                experience_level=adapter.get('experience_level'),
                remote_allowed=adapter.get('remote_allowed', False),
                skills=json.dumps(adapter.get('skills', [])) if adapter.get('skills') else None,
                source_site=adapter['source_site']
            )
            
            try:
                session.add(job)
                session.commit()
                spider.logger.debug(f"Вакансия сохранена: {job.job_title} в {company.name}")
            except IntegrityError:
                session.rollback()
                spider.logger.warning(f"Вакансия уже существует: {adapter['job_url']}")
    
    def _save_company(self, item: CompanyItem, spider):
        """Сохранение компании."""
        adapter = ItemAdapter(item)
        
        with get_db_session() as session:
            company = self._get_or_create_company(
                name=adapter['name'],
                website=adapter.get('website'),
                description=adapter.get('description'),
                industry=adapter.get('industry'),
                size=adapter.get('size'),
                logo_url=adapter.get('logo_url'),
                location=adapter.get('location'),
                source_site=adapter['source_site'],
                session=session
            )
            
            spider.logger.debug(f"Компания сохранена: {company.name}")
    
    def _get_or_create_company(self, name: str, session, **kwargs) -> Company:
        """Получить существующую или создать новую компанию."""
        # Проверяем кэш
        cache_key = f"{name}_{kwargs.get('website', '')}"
        if cache_key in self.companies_cache:
            return session.get(Company, self.companies_cache[cache_key])
        
        # Ищем в базе данных
        company = session.query(Company).filter(Company.name == name).first()
        
        if not company:
            # Создаем новую компанию
            company = Company(
                name=name,
                website=kwargs.get('website'),
                description=kwargs.get('description'),
                location=kwargs.get('location'),
                industry=kwargs.get('industry'),
                size=kwargs.get('size'),
                logo_url=kwargs.get('logo_url')
            )
            session.add(company)
            session.flush()  # Получаем ID без коммита
        
        # Добавляем в кэш
        self.companies_cache[cache_key] = company.id
        
        return company


class ElasticsearchPipeline:
    """Pipeline для индексации данных в Elasticsearch."""
    
    def __init__(self, elasticsearch_url: str, index_name: str):
        self.elasticsearch_url = elasticsearch_url
        self.index_name = index_name
        self.es = None
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            elasticsearch_url=crawler.settings.get('ELASTICSEARCH_URL'),
            index_name=crawler.settings.get('ELASTICSEARCH_INDEX', 'jobs')
        )
    
    def open_spider(self, spider):
        """Инициализация Elasticsearch при открытии паука."""
        try:
            self.es = Elasticsearch([self.elasticsearch_url])
            
            # Создаем индекс если его нет
            if not self.es.indices.exists(index=self.index_name):
                self._create_index()
            
            spider.logger.info(f"ElasticsearchPipeline подключен к {self.elasticsearch_url}")
        except Exception as e:
            spider.logger.error(f"Ошибка подключения к Elasticsearch: {e}")
            self.es = None
    
    def close_spider(self, spider):
        """Закрытие соединения с Elasticsearch."""
        if self.es:
            spider.logger.info("ElasticsearchPipeline закрыт")
    
    def process_item(self, item, spider):
        """Индексация элемента в Elasticsearch."""
        if not self.es:
            return item
        
        try:
            if isinstance(item, JobItem):
                self._index_job(item, spider)
            elif isinstance(item, CompanyItem):
                self._index_company(item, spider)
            
            spider.logger.debug(f"Элемент проиндексирован в ES: {type(item).__name__}")
            return item
            
        except ElasticsearchException as e:
            spider.logger.error(f"Ошибка индексации в Elasticsearch: {e}")
            return item  # Не дропаем элемент при ошибке ES
    
    def _index_job(self, item: JobItem, spider):
        """Индексация вакансии."""
        adapter = ItemAdapter(item)
        
        doc = {
            'company': adapter['company'],
            'job_title': adapter['job_title'],
            'location': adapter.get('location'),
            'posted_date': adapter.get('posted_date').isoformat() if adapter.get('posted_date') else None,
            'job_url': adapter['job_url'],
            'description': adapter.get('description'),
            'salary': adapter.get('salary'),
            'employment_type': adapter.get('employment_type'),
            'experience_level': adapter.get('experience_level'),
            'remote_allowed': adapter.get('remote_allowed', False),
            'skills': adapter.get('skills', []),
            'source_site': adapter['source_site'],
            'scraped_at': adapter.get('scraped_at').isoformat() if adapter.get('scraped_at') else datetime.utcnow().isoformat(),
            'doc_type': 'job'
        }
        
        # Используем hash URL как ID документа
        doc_id = adapter.get('job_url_hash') or hashlib.sha256(adapter['job_url'].encode()).hexdigest()
        
        self.es.index(
            index=self.index_name,
            id=doc_id,
            body=doc
        )
    
    def _index_company(self, item: CompanyItem, spider):
        """Индексация компании."""
        adapter = ItemAdapter(item)
        
        doc = {
            'name': adapter['name'],
            'website': adapter.get('website'),
            'description': adapter.get('description'),
            'location': adapter.get('location'),
            'industry': adapter.get('industry'),
            'size': adapter.get('size'),
            'logo_url': adapter.get('logo_url'),
            'source_site': adapter['source_site'],
            'scraped_at': adapter.get('scraped_at').isoformat() if adapter.get('scraped_at') else datetime.utcnow().isoformat(),
            'doc_type': 'company'
        }
        
        # Используем hash имени и сайта как ID документа
        company_key = f"{adapter['name']}_{adapter.get('website', '')}"
        doc_id = hashlib.sha256(company_key.encode()).hexdigest()
        
        self.es.index(
            index=self.index_name,
            id=doc_id,
            body=doc
        )
    
    def _create_index(self):
        """Создание индекса с маппингом."""
        mapping = {
            "mappings": {
                "properties": {
                    "company": {"type": "text", "analyzer": "standard"},
                    "job_title": {"type": "text", "analyzer": "standard"},
                    "location": {"type": "keyword"},
                    "posted_date": {"type": "date"},
                    "job_url": {"type": "keyword"},
                    "description": {"type": "text", "analyzer": "standard"},
                    "salary": {"type": "text"},
                    "employment_type": {"type": "keyword"},
                    "experience_level": {"type": "keyword"},
                    "remote_allowed": {"type": "boolean"},
                    "skills": {"type": "keyword"},
                    "source_site": {"type": "keyword"},
                    "scraped_at": {"type": "date"},
                    "doc_type": {"type": "keyword"},
                    "name": {"type": "text", "analyzer": "standard"},
                    "website": {"type": "keyword"},
                    "industry": {"type": "keyword"},
                    "size": {"type": "keyword"},
                    "logo_url": {"type": "keyword"}
                }
            }
        }
        
        self.es.indices.create(index=self.index_name, body=mapping)


class StatsPipeline:
    """Pipeline для сбора статистики."""
    
    def __init__(self):
        self.stats = {
            'jobs_processed': 0,
            'companies_processed': 0,
            'jobs_dropped': 0,
            'companies_dropped': 0,
            'start_time': None,
            'end_time': None
        }
    
    def open_spider(self, spider):
        """Инициализация статистики."""
        self.stats['start_time'] = datetime.utcnow()
        spider.logger.info("StatsPipeline инициализирован")
    
    def close_spider(self, spider):
        """Финализация статистики."""
        self.stats['end_time'] = datetime.utcnow()
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        spider.logger.info(f"Статистика скрапинга:")
        spider.logger.info(f"  - Обработано вакансий: {self.stats['jobs_processed']}")
        spider.logger.info(f"  - Обработано компаний: {self.stats['companies_processed']}")
        spider.logger.info(f"  - Отброшено вакансий: {self.stats['jobs_dropped']}")
        spider.logger.info(f"  - Отброшено компаний: {self.stats['companies_dropped']}")
        spider.logger.info(f"  - Время выполнения: {duration:.2f} секунд")
    
    def process_item(self, item, spider):
        """Подсчет статистики."""
        if isinstance(item, JobItem):
            self.stats['jobs_processed'] += 1
        elif isinstance(item, CompanyItem):
            self.stats['companies_processed'] += 1
        
        return item
