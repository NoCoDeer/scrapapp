"""
Настройки Scrapy для проекта скрапинга вакансий.
"""
import os
import sys
from pathlib import Path

# Добавляем путь к shared модулям
sys.path.append(str(Path(__file__).parent.parent))

from shared.config import scraper_settings

# Scrapy settings for jobscraper project
BOT_NAME = 'jobscraper'

SPIDER_MODULES = ['scraper.spiders']
NEWSPIDER_MODULE = 'scraper.spiders'

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests performed by Scrapy (default: 16)
CONCURRENT_REQUESTS = scraper_settings.concurrent_requests

# Configure a delay for requests for the same website (default: 0)
DOWNLOAD_DELAY = scraper_settings.delay_min
RANDOMIZE_DOWNLOAD_DELAY = 0.5

# The download delay setting will honor only one of:
CONCURRENT_REQUESTS_PER_DOMAIN = 8
CONCURRENT_REQUESTS_PER_IP = 8

# Disable cookies (enabled by default)
COOKIES_ENABLED = True

# Disable Telnet Console (enabled by default)
TELNETCONSOLE_ENABLED = False

# Override the default request headers:
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Enable or disable spider middlewares
SPIDER_MIDDLEWARES = {
    'scraper.middlewares.SpiderStatsMiddleware': 543,
}

# Enable or disable downloader middlewares
DOWNLOADER_MIDDLEWARES = {
    'scraper.middlewares.ProxyMiddleware': 350,
    'scraper.middlewares.UserAgentMiddleware': 400,
    'scraper.middlewares.RetryMiddleware': 500,
    'scrapy_playwright.middleware.ScrapyPlaywrightDownloadHandler': 585,
}

# Enable or disable extensions
EXTENSIONS = {
    'scraper.extensions.StatsExtension': 500,
}

# Configure item pipelines
ITEM_PIPELINES = {
    'scraper.pipelines.ValidationPipeline': 300,
    'scraper.pipelines.DuplicationPipeline': 400,
    'scraper.pipelines.DatabasePipeline': 500,
    'scraper.pipelines.ElasticsearchPipeline': 600,
}

# Enable autothrottling
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 60
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching
HTTPCACHE_ENABLED = False
HTTPCACHE_EXPIRATION_SECS = 0
HTTPCACHE_DIR = 'httpcache'
HTTPCACHE_IGNORE_HTTP_CODES = []
HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# Playwright settings
PLAYWRIGHT_BROWSER_TYPE = 'chromium'
PLAYWRIGHT_LAUNCH_OPTIONS = {
    'headless': True,
    'timeout': 30000,
}

PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000
PLAYWRIGHT_PROCESS_REQUEST_HEADERS = None

# Download handlers
DOWNLOAD_HANDLERS = {
    'http': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
    'https': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
}

# Twisted reactor
TWISTED_REACTOR = 'twisted.internet.asyncioreactor.AsyncioSelectorReactor'

# Request fingerprinting
REQUEST_FINGERPRINTER_IMPLEMENTATION = '2.7'

# Feed exports
FEEDS = {
    'data/%(name)s_%(time)s.json': {
        'format': 'json',
        'encoding': 'utf8',
        'store_empty': False,
        'indent': 2,
    },
}

# Logging
LOG_LEVEL = scraper_settings.log_level
LOG_FILE = 'logs/scrapy.log'

# Custom settings
PROXIES = scraper_settings.proxies
USER_AGENTS = scraper_settings.user_agents
DELAY_MIN = scraper_settings.delay_min
DELAY_MAX = scraper_settings.delay_max
DOWNLOAD_TIMEOUT = scraper_settings.download_timeout

# Database settings
DATABASE_URL = scraper_settings.db_url
REDIS_URL = scraper_settings.redis_url
ELASTICSEARCH_URL = scraper_settings.elasticsearch_url
ELASTICSEARCH_INDEX = scraper_settings.elasticsearch_index

# Monitoring
SENTRY_DSN = scraper_settings.sentry_dsn

# Retry settings
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# DNS settings
DNSCACHE_ENABLED = True
DNSCACHE_SIZE = 10000
DNS_TIMEOUT = 60

# Memory usage
MEMUSAGE_ENABLED = True
MEMUSAGE_LIMIT_MB = 2048
MEMUSAGE_WARNING_MB = 1024

# Stats collection
STATS_CLASS = 'scrapy.statscollectors.MemoryStatsCollector'

# Dupefilter
DUPEFILTER_CLASS = 'scrapy.dupefilters.RFPDupeFilter'
DUPEFILTER_DEBUG = False

# Scheduler
SCHEDULER = 'scrapy.core.scheduler.Scheduler'
SCHEDULER_DISK_QUEUE = 'scrapy.squeues.PickleFifoDiskQueue'
SCHEDULER_MEMORY_QUEUE = 'scrapy.squeues.FifoMemoryQueue'

# Job directory
JOBDIR = 'crawls'
