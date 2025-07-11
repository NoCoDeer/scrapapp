"""
Паук для скрапинга вакансий с site1.com (пример).
"""
import scrapy
from scrapy.http import Request
from urllib.parse import urljoin
from datetime import datetime
import re

from ..items import JobItem, create_job_item


class Site1Spider(scrapy.Spider):
    """Паук для скрапинга site1.com."""
    
    name = 'site1'
    allowed_domains = ['site1.com']
    start_urls = [
        'https://site1.com/jobs',
        'https://site1.com/jobs?page=1',
    ]
    
    # Настройки паука
    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_site = 'site1.com'
        self.jobs_scraped = 0
        self.max_pages = kwargs.get('max_pages', 10)  # Максимум страниц для скрапинга
    
    def start_requests(self):
        """Генерация начальных запросов."""
        for url in self.start_urls:
            yield Request(
                url=url,
                callback=self.parse,
                meta={
                    'playwright': True,  # Используем Playwright для JS-сайтов
                    'playwright_include_page': True,
                }
            )
    
    def parse(self, response):
        """Парсинг списка вакансий."""
        self.logger.info(f"Парсинг страницы: {response.url}")
        
        # Извлекаем ссылки на вакансии
        job_links = response.css('.job-item a::attr(href)').getall()
        
        if not job_links:
            # Альтернативные селекторы
            job_links = response.css('.job-listing-item a::attr(href)').getall()
            
        if not job_links:
            job_links = response.xpath('//div[contains(@class, "job")]//a/@href').getall()
        
        self.logger.info(f"Найдено {len(job_links)} ссылок на вакансии")
        
        # Обрабатываем каждую вакансию
        for link in job_links:
            job_url = urljoin(response.url, link)
            yield Request(
                url=job_url,
                callback=self.parse_job,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                }
            )
        
        # Переходим на следующую страницу
        next_page = self.get_next_page(response)
        if next_page and self.should_continue_pagination(response):
            yield Request(
                url=next_page,
                callback=self.parse,
                meta={
                    'playwright': True,
                    'playwright_include_page': True,
                }
            )
    
    def parse_job(self, response):
        """Парсинг отдельной вакансии."""
        self.logger.debug(f"Парсинг вакансии: {response.url}")
        
        try:
            # Извлекаем основные данные
            job_title = self.extract_job_title(response)
            company = self.extract_company(response)
            location = self.extract_location(response)
            description = self.extract_description(response)
            salary = self.extract_salary(response)
            posted_date = self.extract_posted_date(response)
            
            # Дополнительные данные
            employment_type = self.extract_employment_type(response)
            experience_level = self.extract_experience_level(response)
            remote_allowed = self.extract_remote_allowed(response)
            skills = self.extract_skills(response)
            
            # Информация о компании
            company_info = self.extract_company_info(response)
            
            # Создаем элемент вакансии
            item = create_job_item(
                company=company,
                job_title=job_title,
                location=location,
                posted_date=posted_date,
                job_url=response.url,
                description=description,
                salary=salary,
                employment_type=employment_type,
                experience_level=experience_level,
                remote_allowed=remote_allowed,
                skills=skills,
                source_site=self.source_site,
                **company_info
            )
            
            self.jobs_scraped += 1
            self.logger.debug(f"Извлечена вакансия: {job_title} в {company}")
            
            yield item
            
        except Exception as e:
            self.logger.error(f"Ошибка парсинга вакансии {response.url}: {e}")
    
    def extract_job_title(self, response):
        """Извлечение названия вакансии."""
        # Пробуем разные селекторы
        selectors = [
            'h1.job-title::text',
            '.job-header h1::text',
            'h1::text',
            '.title::text',
            '[data-testid="job-title"]::text'
        ]
        
        for selector in selectors:
            title = response.css(selector).get()
            if title:
                return title.strip()
        
        # Fallback через XPath
        title = response.xpath('//h1/text()').get()
        return title.strip() if title else "Не указано"
    
    def extract_company(self, response):
        """Извлечение названия компании."""
        selectors = [
            '.company-name::text',
            '.employer-name::text',
            '[data-testid="company-name"]::text',
            '.job-company::text'
        ]
        
        for selector in selectors:
            company = response.css(selector).get()
            if company:
                return company.strip()
        
        # Fallback
        company = response.xpath('//span[contains(@class, "company")]/text()').get()
        return company.strip() if company else "Не указано"
    
    def extract_location(self, response):
        """Извлечение местоположения."""
        selectors = [
            '.job-location::text',
            '.location::text',
            '[data-testid="job-location"]::text',
            '.address::text'
        ]
        
        for selector in selectors:
            location = response.css(selector).get()
            if location:
                return location.strip()
        
        return None
    
    def extract_description(self, response):
        """Извлечение описания вакансии."""
        selectors = [
            '.job-description',
            '.description',
            '.job-content',
            '[data-testid="job-description"]'
        ]
        
        for selector in selectors:
            description_element = response.css(selector)
            if description_element:
                # Извлекаем весь текст из элемента
                text_parts = description_element.css('::text').getall()
                if text_parts:
                    return ' '.join(part.strip() for part in text_parts if part.strip())
        
        return None
    
    def extract_salary(self, response):
        """Извлечение зарплаты."""
        selectors = [
            '.salary::text',
            '.wage::text',
            '.compensation::text',
            '[data-testid="salary"]::text'
        ]
        
        for selector in selectors:
            salary = response.css(selector).get()
            if salary:
                return salary.strip()
        
        # Поиск по тексту
        salary_pattern = r'[\$€£₽]\s*\d+[,\d]*(?:\s*[-–—]\s*[\$€£₽]?\s*\d+[,\d]*)?'
        text = response.text
        salary_match = re.search(salary_pattern, text)
        if salary_match:
            return salary_match.group().strip()
        
        return None
    
    def extract_posted_date(self, response):
        """Извлечение даты публикации."""
        selectors = [
            '.posted-date::text',
            '.date-posted::text',
            '.publish-date::text',
            '[data-testid="posted-date"]::text'
        ]
        
        for selector in selectors:
            date_text = response.css(selector).get()
            if date_text:
                return self.parse_date(date_text.strip())
        
        # Поиск по паттернам в тексте
        date_patterns = [
            r'(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})',
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
            r'(\d{4})-(\d{1,2})-(\d{1,2})'
        ]
        
        text = response.text
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                return self.parse_date(match.group())
        
        return None
    
    def extract_employment_type(self, response):
        """Извлечение типа занятости."""
        selectors = [
            '.employment-type::text',
            '.job-type::text',
            '[data-testid="employment-type"]::text'
        ]
        
        for selector in selectors:
            emp_type = response.css(selector).get()
            if emp_type:
                return emp_type.strip()
        
        # Поиск ключевых слов
        text = response.text.lower()
        if 'полная занятость' in text or 'full-time' in text:
            return 'Полная занятость'
        elif 'частичная занятость' in text or 'part-time' in text:
            return 'Частичная занятость'
        elif 'контракт' in text or 'contract' in text:
            return 'Контракт'
        
        return None
    
    def extract_experience_level(self, response):
        """Извлечение уровня опыта."""
        text = response.text.lower()
        
        if any(word in text for word in ['junior', 'джуниор', 'начинающий']):
            return 'Junior'
        elif any(word in text for word in ['senior', 'сеньор', 'старший']):
            return 'Senior'
        elif any(word in text for word in ['middle', 'мидл', 'средний']):
            return 'Middle'
        elif any(word in text for word in ['lead', 'лид', 'ведущий']):
            return 'Lead'
        
        return None
    
    def extract_remote_allowed(self, response):
        """Проверка возможности удаленной работы."""
        text = response.text.lower()
        remote_keywords = [
            'удаленно', 'remote', 'удаленная работа', 'работа из дома',
            'home office', 'дистанционно', 'онлайн'
        ]
        
        return any(keyword in text for keyword in remote_keywords)
    
    def extract_skills(self, response):
        """Извлечение навыков."""
        selectors = [
            '.skills .skill::text',
            '.technologies .tech::text',
            '.requirements li::text'
        ]
        
        skills = []
        for selector in selectors:
            skill_texts = response.css(selector).getall()
            skills.extend([skill.strip() for skill in skill_texts if skill.strip()])
        
        # Поиск популярных технологий в тексте
        tech_keywords = [
            'Python', 'JavaScript', 'Java', 'C++', 'React', 'Vue', 'Angular',
            'Django', 'Flask', 'FastAPI', 'PostgreSQL', 'MySQL', 'MongoDB',
            'Docker', 'Kubernetes', 'AWS', 'Git', 'Linux'
        ]
        
        text = response.text
        for keyword in tech_keywords:
            if keyword in text and keyword not in skills:
                skills.append(keyword)
        
        return skills[:10]  # Ограничиваем количество навыков
    
    def extract_company_info(self, response):
        """Извлечение дополнительной информации о компании."""
        return {
            'company_website': self.extract_company_website(response),
            'company_description': self.extract_company_description(response),
            'company_industry': self.extract_company_industry(response),
            'company_size': self.extract_company_size(response),
            'company_logo_url': self.extract_company_logo(response)
        }
    
    def extract_company_website(self, response):
        """Извлечение сайта компании."""
        selectors = [
            '.company-website::attr(href)',
            '.company-link::attr(href)',
            'a[href*="company"]::attr(href)'
        ]
        
        for selector in selectors:
            website = response.css(selector).get()
            if website:
                return website
        
        return None
    
    def extract_company_description(self, response):
        """Извлечение описания компании."""
        selectors = [
            '.company-description::text',
            '.about-company::text',
            '.company-info::text'
        ]
        
        for selector in selectors:
            description = response.css(selector).get()
            if description:
                return description.strip()
        
        return None
    
    def extract_company_industry(self, response):
        """Извлечение отрасли компании."""
        selectors = [
            '.company-industry::text',
            '.industry::text',
            '.sector::text'
        ]
        
        for selector in selectors:
            industry = response.css(selector).get()
            if industry:
                return industry.strip()
        
        return None
    
    def extract_company_size(self, response):
        """Извлечение размера компании."""
        selectors = [
            '.company-size::text',
            '.employees::text',
            '.team-size::text'
        ]
        
        for selector in selectors:
            size = response.css(selector).get()
            if size:
                return size.strip()
        
        # Поиск по паттернам
        text = response.text
        size_pattern = r'(\d+)\s*[-–—]\s*(\d+)\s*сотрудник'
        match = re.search(size_pattern, text)
        if match:
            return f"{match.group(1)}-{match.group(2)}"
        
        return None
    
    def extract_company_logo(self, response):
        """Извлечение логотипа компании."""
        selectors = [
            '.company-logo img::attr(src)',
            '.logo img::attr(src)',
            'img[alt*="logo"]::attr(src)'
        ]
        
        for selector in selectors:
            logo = response.css(selector).get()
            if logo:
                return urljoin(response.url, logo)
        
        return None
    
    def get_next_page(self, response):
        """Получение ссылки на следующую страницу."""
        selectors = [
            '.pagination .next::attr(href)',
            '.pager .next::attr(href)',
            'a[rel="next"]::attr(href)',
            '.pagination a:contains("Следующая")::attr(href)'
        ]
        
        for selector in selectors:
            next_url = response.css(selector).get()
            if next_url:
                return urljoin(response.url, next_url)
        
        # Попробуем найти по номеру страницы
        current_page = self.extract_current_page(response)
        if current_page:
            next_page_url = response.url.replace(f'page={current_page}', f'page={current_page + 1}')
            if next_page_url != response.url:
                return next_page_url
        
        return None
    
    def extract_current_page(self, response):
        """Извлечение номера текущей страницы."""
        # Из URL
        import re
        page_match = re.search(r'page=(\d+)', response.url)
        if page_match:
            return int(page_match.group(1))
        
        # Из элементов страницы
        current_page = response.css('.pagination .current::text').get()
        if current_page and current_page.isdigit():
            return int(current_page)
        
        return 1
    
    def should_continue_pagination(self, response):
        """Проверка, нужно ли продолжать пагинацию."""
        current_page = self.extract_current_page(response)
        return current_page < self.max_pages
    
    def parse_date(self, date_string):
        """Парсинг даты из строки."""
        try:
            import dateparser
            return dateparser.parse(date_string)
        except:
            return None
    
    def closed(self, reason):
        """Вызывается при закрытии паука."""
        self.logger.info(f"Паук {self.name} завершен. Причина: {reason}")
        self.logger.info(f"Всего обработано вакансий: {self.jobs_scraped}")
