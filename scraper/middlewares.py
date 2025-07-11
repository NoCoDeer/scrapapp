"""
Middleware для Scrapy проекта.
"""
import random
import time
import logging
from typing import Optional, Union
from urllib.parse import urlparse

import scrapy
from scrapy import signals
from scrapy.http import HtmlResponse, Request
from scrapy.downloadermiddlewares.retry import RetryMiddleware as BaseRetryMiddleware
from scrapy.utils.response import response_status_message
from scrapy.exceptions import NotConfigured, IgnoreRequest

from shared.config import settings

logger = logging.getLogger(__name__)


class ProxyMiddleware:
    """Middleware для ротации прокси."""
    
    def __init__(self, proxies: list):
        self.proxies = proxies
        self.proxy_index = 0
        
        if not self.proxies:
            raise NotConfigured("Список прокси пуст")
        
        logger.info(f"Инициализирован ProxyMiddleware с {len(self.proxies)} прокси")
    
    @classmethod
    def from_crawler(cls, crawler):
        proxies = crawler.settings.get('PROXIES', [])
        return cls(proxies)
    
    def process_request(self, request: Request, spider) -> Optional[Request]:
        """Обработка запроса - установка прокси."""
        if not self.proxies:
            return None
        
        # Выбираем следующий прокси по кругу
        proxy = self.proxies[self.proxy_index]
        self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        
        # Устанавливаем прокси
        request.meta['proxy'] = proxy
        
        # Логируем использование прокси
        spider.logger.debug(f"Используется прокси: {proxy} для {request.url}")
        
        return None
    
    def process_exception(self, request: Request, exception, spider):
        """Обработка исключений - смена прокси при ошибке."""
        proxy = request.meta.get('proxy')
        if proxy:
            spider.logger.warning(f"Ошибка с прокси {proxy}: {exception}")
            
            # Помечаем прокси как проблемный (можно добавить логику блэклиста)
            # Пока просто логируем
        
        return None


class UserAgentMiddleware:
    """Middleware для ротации User-Agent."""
    
    def __init__(self, user_agents: list):
        self.user_agents = user_agents
        
        if not self.user_agents:
            # Используем дефолтные User-Agent'ы если список пуст
            self.user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0"
            ]
        
        logger.info(f"Инициализирован UserAgentMiddleware с {len(self.user_agents)} User-Agent'ами")
    
    @classmethod
    def from_crawler(cls, crawler):
        user_agents = crawler.settings.get('USER_AGENTS', [])
        return cls(user_agents)
    
    def process_request(self, request: Request, spider) -> Optional[Request]:
        """Обработка запроса - установка случайного User-Agent."""
        user_agent = random.choice(self.user_agents)
        request.headers['User-Agent'] = user_agent
        
        spider.logger.debug(f"Установлен User-Agent: {user_agent[:50]}...")
        
        return None


class DelayMiddleware:
    """Middleware для случайной задержки между запросами."""
    
    def __init__(self, delay_min: int, delay_max: int):
        self.delay_min = delay_min
        self.delay_max = delay_max
        
        logger.info(f"Инициализирован DelayMiddleware с задержкой {delay_min}-{delay_max} секунд")
    
    @classmethod
    def from_crawler(cls, crawler):
        delay_min = crawler.settings.get('DELAY_MIN', 1)
        delay_max = crawler.settings.get('DELAY_MAX', 5)
        return cls(delay_min, delay_max)
    
    def process_request(self, request: Request, spider) -> Optional[Request]:
        """Обработка запроса - добавление случайной задержки."""
        delay = random.uniform(self.delay_min, self.delay_max)
        
        spider.logger.debug(f"Задержка {delay:.2f} секунд перед запросом к {request.url}")
        
        time.sleep(delay)
        
        return None


class RetryMiddleware(BaseRetryMiddleware):
    """Расширенный middleware для повторных попыток."""
    
    def __init__(self, settings):
        super().__init__(settings)
        self.retry_http_codes = set(int(x) for x in settings.getlist("RETRY_HTTP_CODES"))
        self.retry_exceptions = settings.getlist("RETRY_EXCEPTIONS")
        
        logger.info(f"Инициализирован RetryMiddleware с кодами: {self.retry_http_codes}")
    
    def process_response(self, request: Request, response: HtmlResponse, spider):
        """Обработка ответа - проверка на необходимость повтора."""
        if request.meta.get('dont_retry', False):
            return response
        
        if response.status in self.retry_http_codes:
            reason = response_status_message(response.status)
            spider.logger.warning(f"Повтор запроса {request.url} из-за статуса {response.status}: {reason}")
            return self._retry(request, reason, spider) or response
        
        return response
    
    def process_exception(self, request: Request, exception, spider):
        """Обработка исключений - повтор при определенных ошибках."""
        if isinstance(exception, self.EXCEPTIONS_TO_RETRY) and not request.meta.get('dont_retry', False):
            spider.logger.warning(f"Повтор запроса {request.url} из-за исключения: {exception}")
            return self._retry(request, exception, spider)
        
        return None


class SpiderStatsMiddleware:
    """Middleware для сбора статистики паука."""
    
    def __init__(self, stats):
        self.stats = stats
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.stats)
    
    def process_spider_input(self, response: HtmlResponse, spider):
        """Обработка входящего ответа."""
        self.stats.inc_value('spider_stats/responses_received')
        self.stats.inc_value(f'spider_stats/responses_received_{response.status}')
        
        # Записываем размер ответа
        content_length = len(response.body)
        self.stats.inc_value('spider_stats/response_bytes_received', content_length)
        
        return None
    
    def process_spider_output(self, response: HtmlResponse, result, spider):
        """Обработка выходных данных паука."""
        for item in result:
            if isinstance(item, scrapy.Item):
                self.stats.inc_value('spider_stats/items_scraped')
                self.stats.inc_value(f'spider_stats/items_scraped_{item.__class__.__name__}')
            elif isinstance(item, Request):
                self.stats.inc_value('spider_stats/requests_generated')
            
            yield item
    
    def process_spider_exception(self, response: HtmlResponse, exception, spider):
        """Обработка исключений паука."""
        self.stats.inc_value('spider_stats/spider_exceptions')
        self.stats.inc_value(f'spider_stats/spider_exceptions_{exception.__class__.__name__}')
        
        spider.logger.error(f"Исключение в пауке: {exception}")
        
        return None


class HeadersMiddleware:
    """Middleware для установки дополнительных заголовков."""
    
    def __init__(self):
        self.default_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }
    
    def process_request(self, request: Request, spider) -> Optional[Request]:
        """Обработка запроса - установка заголовков."""
        for header, value in self.default_headers.items():
            if header not in request.headers:
                request.headers[header] = value
        
        # Добавляем Referer для последующих запросов
        if 'Referer' not in request.headers and hasattr(spider, 'start_urls'):
            if spider.start_urls:
                parsed_url = urlparse(spider.start_urls[0])
                request.headers['Referer'] = f"{parsed_url.scheme}://{parsed_url.netloc}/"
        
        return None


class RobotsTxtMiddleware:
    """Middleware для обхода robots.txt (если необходимо)."""
    
    def __init__(self, respect_robots_txt: bool = False):
        self.respect_robots_txt = respect_robots_txt
        
        if not respect_robots_txt:
            logger.info("RobotsTxtMiddleware: robots.txt игнорируется")
    
    @classmethod
    def from_crawler(cls, crawler):
        respect_robots_txt = crawler.settings.getbool('ROBOTSTXT_OBEY', False)
        return cls(respect_robots_txt)
    
    def process_request(self, request: Request, spider) -> Optional[Request]:
        """Обработка запроса - проверка robots.txt."""
        if not self.respect_robots_txt:
            # Добавляем заголовок, указывающий что мы не бот
            request.headers['X-Robots-Tag'] = 'noindex, nofollow'
        
        return None
