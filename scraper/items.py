"""
Модели данных (Items) для Scrapy.
"""
import scrapy
from itemloaders.processors import TakeFirst, MapCompose, Join
from w3lib.html import remove_tags
import re
from datetime import datetime
from typing import Optional


def clean_text(value: str) -> str:
    """Очистить текст от лишних символов и пробелов."""
    if not value:
        return ""
    
    # Удаляем HTML теги
    value = remove_tags(value)
    
    # Удаляем лишние пробелы и переносы строк
    value = re.sub(r'\s+', ' ', value)
    
    # Убираем пробелы в начале и конце
    return value.strip()


def clean_salary(value: str) -> Optional[str]:
    """Очистить и нормализовать зарплату."""
    if not value:
        return None
    
    value = clean_text(value)
    
    # Удаляем лишние символы, оставляем только цифры, валюты и разделители
    value = re.sub(r'[^\d\s\-–—$€£₽руб\.,kK]', '', value)
    
    return value.strip() if value.strip() else None


def parse_date(value: str) -> Optional[datetime]:
    """Парсинг даты из строки."""
    if not value:
        return None
    
    try:
        import dateparser
        parsed_date = dateparser.parse(value)
        return parsed_date
    except:
        return None


def normalize_location(value: str) -> Optional[str]:
    """Нормализация местоположения."""
    if not value:
        return None
    
    value = clean_text(value)
    
    # Удаляем лишние слова
    value = re.sub(r'\b(город|г\.|city|remote|удаленно|удаленная работа)\b', '', value, flags=re.IGNORECASE)
    
    return value.strip() if value.strip() else None


class JobItem(scrapy.Item):
    """Модель вакансии."""
    
    # Основные поля
    company = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    job_title = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    location = scrapy.Field(
        input_processor=MapCompose(normalize_location),
        output_processor=TakeFirst()
    )
    
    posted_date = scrapy.Field(
        input_processor=MapCompose(clean_text, parse_date),
        output_processor=TakeFirst()
    )
    
    job_url = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    description = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=Join('\n')
    )
    
    salary = scrapy.Field(
        input_processor=MapCompose(clean_salary),
        output_processor=TakeFirst()
    )
    
    # Дополнительные поля
    employment_type = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    experience_level = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    remote_allowed = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    skills = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=lambda x: [skill.strip() for skill in x if skill.strip()]
    )
    
    # Метаданные
    source_site = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    scraped_at = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # Информация о компании
    company_website = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    company_description = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    company_industry = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    company_size = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    company_logo_url = scrapy.Field(
        output_processor=TakeFirst()
    )


class CompanyItem(scrapy.Item):
    """Модель компании."""
    
    name = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    website = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    description = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    location = scrapy.Field(
        input_processor=MapCompose(normalize_location),
        output_processor=TakeFirst()
    )
    
    industry = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    size = scrapy.Field(
        input_processor=MapCompose(clean_text),
        output_processor=TakeFirst()
    )
    
    logo_url = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # Метаданные
    source_site = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    scraped_at = scrapy.Field(
        output_processor=TakeFirst()
    )


def create_job_item(**kwargs) -> JobItem:
    """Создать экземпляр JobItem с базовыми значениями."""
    item = JobItem()
    
    # Устанавливаем время скрапинга
    item['scraped_at'] = datetime.utcnow()
    
    # Устанавливаем переданные значения
    for key, value in kwargs.items():
        if key in item.fields:
            item[key] = value
    
    return item


def create_company_item(**kwargs) -> CompanyItem:
    """Создать экземпляр CompanyItem с базовыми значениями."""
    item = CompanyItem()
    
    # Устанавливаем время скрапинга
    item['scraped_at'] = datetime.utcnow()
    
    # Устанавливаем переданные значения
    for key, value in kwargs.items():
        if key in item.fields:
            item[key] = value
    
    return item
