"""
Паук для скрапинга вакансий с site2.com (пример).
"""
import scrapy
from scrapy.http import Request
from urllib.parse import urljoin
from datetime import datetime
import re
import json

from ..items import JobItem, create_job_item


class Site2Spider(scrapy.Spider):
    """Паук для скрапинга site2.com."""
    
    name = 'site2'
    allowed_domains = ['site2.com']
    start_urls = [
        'https://site2.com/vacancies',
        'https://site2.com/api/jobs?limit=50&offset=0',  # API endpoint
    ]
    
    # Настройки паука
    custom_settings = {
        'DOWNLOAD_DELAY': 3,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.8,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 3,
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': True,
            'timeout': 45000,
        }
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_site = 'site2.com'
        self.jobs_scraped = 0
        self.max_pages = kwargs.get('max_pages', 15)
        self.api_mode = kwargs.get('api_mode', False)  # Режим работы с API
    
    def start_requests(self):
        """Генерация начальных запросов."""
        for url in self.start_urls:
            if 'api' in url and self.api_mode:
                # API запрос
                yield Request(
                    url=url,
                    callback=self.parse_api,
                    headers={
                        'Accept': 'application/json',
                        'Content-Type': 'application/json',
                        'User-Agent': 'JobScraper/1.0'
                    }
                )
            else:
                # Обычный веб-запрос
                yield Request(
                    url=url,
                    callback=self.parse,
                    meta={
                        'playwright': True,
                        'playwright_include_page': True,
                        'playwright_page_methods': [
                            ('wait_for_selector', '.job-card', {'timeout': 10000}),
                            ('wait_for_load_state', 'networkidle'),
                        ]
                    }
                )
    
    def parse(self, response):
        """Парсинг списка вакансий (веб-версия)."""
        self.logger.info(f"Парсинг страницы: {response.url}")
        
        # Проверяем, есть ли JSON данные в скрипте
        json_data = self.extract_json_data(response)
        if json_data:
            yield from self.parse_json_jobs(json_data)
            return
        
        # Извлекаем ссылки на вакансии
        job_selectors = [
            '.job-card a::attr(href)',
            '.vacancy-item a::attr(href)',
            '.job-listing a::attr(href)',
            '[data-testid="job-link"]::attr(href)'
        ]
        
        job_links = []
        for selector in job_selectors:
            links = response.css(selector).getall()
            if links:
                job_links = links
                break
        
        if not job_links:
            # Fallback XPath
            job_links = response.xpath('//div[contains(@class, "job") or contains(@class, "vacancy")]//a/@href').getall()
        
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
                    'playwright_page_methods': [
                        ('wait_for_selector', 'h1', {'timeout': 10000}),
                    ]
                }
            )
        
        # Пагинация
        next_page = self.get_next_page(response)
        if next_page and self.should_continue_pagination(response):
            yield Request(
                url=next_page,
                callback=self.parse,
                meta=response.meta
            )
    
    def parse_api(self, response):
        """Парсинг API ответа."""
        try:
            data = json.loads(response.text)
            jobs = data.get('jobs', data.get('data', data.get('results', [])))
            
            self.logger.info(f"Получено {len(jobs)} вакансий из API")
            
            for job_data in jobs:
                yield from self.parse_api_job(job_data)
            
            # Пагинация для API
            next_url = self.get_api_next_page(data, response)
            if next_url:
                yield Request(
                    url=next_url,
                    callback=self.parse_api,
                    headers=response.request.headers
                )
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Ошибка парсинга JSON: {e}")
    
    def parse_api_job(self, job_data):
        """Парсинг вакансии из API данных."""
        try:
            # Маппинг полей API на наши поля
            item = create_job_item(
                company=job_data.get('company', {}).get('name', 'Не указано'),
                job_title=job_data.get('title', job_data.get('name', 'Не указано')),
                location=job_data.get('location', job_data.get('city')),
                posted_date=self.parse_api_date(job_data.get('published_at', job_data.get('created_at'))),
                job_url=job_data.get('url', job_data.get('link')),
                description=job_data.get('description', job_data.get('content')),
                salary=self.format_api_salary(job_data.get('salary')),
                employment_type=job_data.get('employment_type', job_data.get('type')),
                experience_level=job_data.get('experience_level', job_data.get('level')),
                remote_allowed=job_data.get('remote', False),
                skills=job_data.get('skills', job_data.get('technologies', [])),
                source_site=self.source_site,
                company_website=job_data.get('company', {}).get('website'),
                company_description=job_data.get('company', {}).get('description'),
                company_industry=job_data.get('company', {}).get('industry'),
                company_size=job_data.get('company', {}).get('size'),
                company_logo_url=job_data.get('company', {}).get('logo')
            )
            
            self.jobs_scraped += 1
            self.logger.debug(f"Извлечена вакансия из API: {item.get('job_title')}")
            
            yield item
            
        except Exception as e:
            self.logger.error(f"Ошибка парсинга API вакансии: {e}")
    
    def parse_job(self, response):
        """Парсинг отдельной вакансии (веб-версия)."""
        self.logger.debug(f"Парсинг вакансии: {response.url}")
        
        try:
            # Проверяем JSON-LD данные
            json_ld = self.extract_json_ld(response)
            if json_ld:
                yield from self.parse_json_ld_job(json_ld, response.url)
                return
            
            # Обычный парсинг HTML
            item = create_job_item(
                company=self.extract_company(response),
                job_title=self.extract_job_title(response),
                location=self.extract_location(response),
                posted_date=self.extract_posted_date(response),
                job_url=response.url,
                description=self.extract_description(response),
                salary=self.extract_salary(response),
                employment_type=self.extract_employment_type(response),
                experience_level=self.extract_experience_level(response),
                remote_allowed=self.extract_remote_allowed(response),
                skills=self.extract_skills(response),
                source_site=self.source_site,
                **self.extract_company_info(response)
            )
            
            self.jobs_scraped += 1
            self.logger.debug(f"Извлечена вакансия: {item.get('job_title')}")
            
            yield item
            
        except Exception as e:
            self.logger.error(f"Ошибка парсинга вакансии {response.url}: {e}")
    
    def extract_json_data(self, response):
        """Извлечение JSON данных из скриптов на странице."""
        scripts = response.css('script[type="application/json"]::text').getall()
        scripts.extend(response.css('script:contains("window.__INITIAL_STATE__")::text').getall())
        scripts.extend(response.css('script:contains("window.__DATA__")::text').getall())
        
        for script in scripts:
            try:
                # Очищаем скрипт от лишнего кода
                json_match = re.search(r'(\{.*\})', script, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                    if 'jobs' in data or 'vacancies' in data:
                        return data
            except:
                continue
        
        return None
    
    def extract_json_ld(self, response):
        """Извлечение JSON-LD данных."""
        json_ld_scripts = response.css('script[type="application/ld+json"]::text').getall()
        
        for script in json_ld_scripts:
            try:
                data = json.loads(script)
                if data.get('@type') == 'JobPosting':
                    return data
            except:
                continue
        
        return None
    
    def parse_json_ld_job(self, json_ld, url):
        """Парсинг вакансии из JSON-LD."""
        try:
            hiring_org = json_ld.get('hiringOrganization', {})
            job_location = json_ld.get('jobLocation', {})
            
            item = create_job_item(
                company=hiring_org.get('name', 'Не указано'),
                job_title=json_ld.get('title', 'Не указано'),
                location=job_location.get('address', {}).get('addressLocality'),
                posted_date=self.parse_date(json_ld.get('datePosted')),
                job_url=url,
                description=json_ld.get('description'),
                salary=self.format_salary_from_json_ld(json_ld.get('baseSalary')),
                employment_type=json_ld.get('employmentType'),
                experience_level=json_ld.get('experienceRequirements'),
                remote_allowed='remote' in json_ld.get('jobLocationType', '').lower(),
                skills=json_ld.get('skills', []),
                source_site=self.source_site,
                company_website=hiring_org.get('sameAs'),
                company_description=hiring_org.get('description'),
                company_logo_url=hiring_org.get('logo')
            )
            
            self.jobs_scraped += 1
            yield item
            
        except Exception as e:
            self.logger.error(f"Ошибка парсинга JSON-LD: {e}")
    
    def parse_json_jobs(self, json_data):
        """Парсинг вакансий из JSON данных."""
        jobs = json_data.get('jobs', json_data.get('vacancies', []))
        
        for job in jobs:
            try:
                item = create_job_item(
                    company=job.get('company', 'Не указано'),
                    job_title=job.get('title', job.get('name', 'Не указано')),
                    location=job.get('location'),
                    posted_date=self.parse_date(job.get('date')),
                    job_url=job.get('url', job.get('link')),
                    description=job.get('description'),
                    salary=job.get('salary'),
                    employment_type=job.get('type'),
                    experience_level=job.get('level'),
                    remote_allowed=job.get('remote', False),
                    skills=job.get('skills', []),
                    source_site=self.source_site
                )
                
                self.jobs_scraped += 1
                yield item
                
            except Exception as e:
                self.logger.error(f"Ошибка парсинга JSON вакансии: {e}")
    
    # Методы извлечения данных (аналогичные site1_spider, но с другими селекторами)
    def extract_job_title(self, response):
        """Извлечение названия вакансии."""
        selectors = [
            'h1.vacancy-title::text',
            '.job-header__title::text',
            'h1[data-testid="job-title"]::text',
            '.position-name::text'
        ]
        
        for selector in selectors:
            title = response.css(selector).get()
            if title:
                return title.strip()
        
        return response.xpath('//h1/text()').get() or "Не указано"
    
    def extract_company(self, response):
        """Извлечение названия компании."""
        selectors = [
            '.company-name a::text',
            '.employer-link::text',
            '[data-testid="company-name"]::text',
            '.company-title::text'
        ]
        
        for selector in selectors:
            company = response.css(selector).get()
            if company:
                return company.strip()
        
        return "Не указано"
    
    def extract_location(self, response):
        """Извлечение местоположения."""
        selectors = [
            '.vacancy-location::text',
            '.job-address::text',
            '[data-testid="location"]::text',
            '.location-name::text'
        ]
        
        for selector in selectors:
            location = response.css(selector).get()
            if location:
                return location.strip()
        
        return None
    
    def extract_description(self, response):
        """Извлечение описания вакансии."""
        selectors = [
            '.vacancy-description',
            '.job-details',
            '.description-content',
            '[data-testid="description"]'
        ]
        
        for selector in selectors:
            desc_element = response.css(selector)
            if desc_element:
                text_parts = desc_element.css('::text').getall()
                if text_parts:
                    return ' '.join(part.strip() for part in text_parts if part.strip())
        
        return None
    
    def extract_salary(self, response):
        """Извлечение зарплаты."""
        selectors = [
            '.salary-value::text',
            '.wage-amount::text',
            '[data-testid="salary"]::text',
            '.compensation-info::text'
        ]
        
        for selector in selectors:
            salary = response.css(selector).get()
            if salary:
                return salary.strip()
        
        # Поиск в тексте
        text = response.text
        salary_patterns = [
            r'от\s+(\d+(?:\s*\d+)*)\s*до\s+(\d+(?:\s*\d+)*)\s*руб',
            r'(\d+(?:\s*\d+)*)\s*[-–—]\s*(\d+(?:\s*\d+)*)\s*руб',
            r'\$\s*(\d+(?:,\d+)*)\s*[-–—]\s*\$?\s*(\d+(?:,\d+)*)'
        ]
        
        for pattern in salary_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group().strip()
        
        return None
    
    def extract_posted_date(self, response):
        """Извлечение даты публикации."""
        selectors = [
            '.publish-date::text',
            '.vacancy-date::text',
            '[data-testid="posted-date"]::text',
            '.date-info::text'
        ]
        
        for selector in selectors:
            date_text = response.css(selector).get()
            if date_text:
                return self.parse_date(date_text.strip())
        
        return None
    
    def extract_employment_type(self, response):
        """Извлечение типа занятости."""
        selectors = [
            '.employment-type::text',
            '.work-type::text',
            '[data-testid="employment"]::text'
        ]
        
        for selector in selectors:
            emp_type = response.css(selector).get()
            if emp_type:
                return emp_type.strip()
        
        return None
    
    def extract_experience_level(self, response):
        """Извлечение уровня опыта."""
        selectors = [
            '.experience-level::text',
            '.exp-requirement::text',
            '[data-testid="experience"]::text'
        ]
        
        for selector in selectors:
            exp_level = response.css(selector).get()
            if exp_level:
                return exp_level.strip()
        
        return None
    
    def extract_remote_allowed(self, response):
        """Проверка возможности удаленной работы."""
        remote_indicators = response.css('.remote-work, .work-remote, [data-remote="true"]')
        if remote_indicators:
            return True
        
        text = response.text.lower()
        return any(keyword in text for keyword in ['удаленно', 'remote', 'дистанционно'])
    
    def extract_skills(self, response):
        """Извлечение навыков."""
        selectors = [
            '.skills-list .skill::text',
            '.tech-stack .tech::text',
            '.requirements .requirement::text'
        ]
        
        skills = []
        for selector in selectors:
            skill_texts = response.css(selector).getall()
            skills.extend([skill.strip() for skill in skill_texts if skill.strip()])
        
        return skills[:15]
    
    def extract_company_info(self, response):
        """Извлечение информации о компании."""
        return {
            'company_website': response.css('.company-website::attr(href)').get(),
            'company_description': response.css('.company-about::text').get(),
            'company_industry': response.css('.company-industry::text').get(),
            'company_size': response.css('.company-size::text').get(),
            'company_logo_url': response.css('.company-logo img::attr(src)').get()
        }
    
    def get_next_page(self, response):
        """Получение следующей страницы."""
        selectors = [
            '.pagination .next::attr(href)',
            '.pager-next::attr(href)',
            'a[rel="next"]::attr(href)'
        ]
        
        for selector in selectors:
            next_url = response.css(selector).get()
            if next_url:
                return urljoin(response.url, next_url)
        
        return None
    
    def get_api_next_page(self, data, response):
        """Получение следующей страницы для API."""
        # Проверяем pagination в ответе
        pagination = data.get('pagination', data.get('meta', {}))
        
        if pagination.get('has_next', False):
            next_offset = pagination.get('next_offset')
            if next_offset:
                base_url = response.url.split('?')[0]
                return f"{base_url}?limit=50&offset={next_offset}"
        
        return None
    
    def should_continue_pagination(self, response):
        """Проверка продолжения пагинации."""
        current_page = self.extract_current_page(response)
        return current_page < self.max_pages
    
    def extract_current_page(self, response):
        """Извлечение номера текущей страницы."""
        page_match = re.search(r'page=(\d+)', response.url)
        if page_match:
            return int(page_match.group(1))
        
        offset_match = re.search(r'offset=(\d+)', response.url)
        if offset_match:
            return int(offset_match.group(1)) // 50 + 1  # Предполагаем 50 элементов на страницу
        
        return 1
    
    def parse_date(self, date_string):
        """Парсинг даты."""
        if not date_string:
            return None
        
        try:
            import dateparser
            return dateparser.parse(date_string)
        except:
            return None
    
    def parse_api_date(self, date_string):
        """Парсинг даты из API."""
        if not date_string:
            return None
        
        try:
            # Пробуем ISO формат
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except:
            return self.parse_date(date_string)
    
    def format_api_salary(self, salary_data):
        """Форматирование зарплаты из API."""
        if not salary_data:
            return None
        
        if isinstance(salary_data, dict):
            min_sal = salary_data.get('min')
            max_sal = salary_data.get('max')
            currency = salary_data.get('currency', 'руб')
            
            if min_sal and max_sal:
                return f"{min_sal} - {max_sal} {currency}"
            elif min_sal:
                return f"от {min_sal} {currency}"
            elif max_sal:
                return f"до {max_sal} {currency}"
        
        return str(salary_data)
    
    def format_salary_from_json_ld(self, salary_data):
        """Форматирование зарплаты из JSON-LD."""
        if not salary_data:
            return None
        
        if isinstance(salary_data, dict):
            value = salary_data.get('value', {})
            currency = salary_data.get('currency', 'USD')
            
            if isinstance(value, dict):
                min_val = value.get('minValue')
                max_val = value.get('maxValue')
                
                if min_val and max_val:
                    return f"{min_val} - {max_val} {currency}"
                elif min_val:
                    return f"от {min_val} {currency}"
        
        return None
    
    def closed(self, reason):
        """Завершение работы паука."""
        self.logger.info(f"Паук {self.name} завершен. Причина: {reason}")
        self.logger.info(f"Всего обработано вакансий: {self.jobs_scraped}")
