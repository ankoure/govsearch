# Scrapy settings for govsearch project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = "govsearch"

SPIDER_MODULES = ["govsearch.spiders"]
NEWSPIDER_MODULE = "govsearch.spiders"

ADDONS = {}


# Crawl responsibly by identifying yourself (and your website) on the
# user-agent
USER_AGENT = "govsearch-bot/1.0"

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Concurrency and throttling settings
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_DELAY = 0.5

# Timeout settings (in seconds)
DOWNLOAD_TIMEOUT = 30
DOWNLOAD_MAXSIZE = 10485760  # 10MB
DOWNLOAD_WARNSIZE = 5242880  # 5MB

# Disable cookies (enabled by default)
# COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
# TELNETCONSOLE_ENABLED = False

# Override the default request headers:
# DEFAULT_REQUEST_HEADERS = {
#    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#    "Accept-Language": "en",
# }

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
# SPIDER_MIDDLEWARES = {
#    "govsearch.middlewares.GovsearchSpiderMiddleware": 543,
# }

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
    "govsearch.middlewares.ResponseValidationMiddleware": 543,
}

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
# EXTENSIONS = {
#    "scrapy.extensions.telnet.TelnetConsole": None,
# }

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
    "govsearch.pipelines.OpenSearchPipeline": 300,
}

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
AUTOTHROTTLE_ENABLED = True
# The initial download delay
AUTOTHROTTLE_START_DELAY = 1
# The maximum download delay to be set in case of high latencies
AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
# AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
# Enable showing throttling stats for every response received:
# AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
# HTTPCACHE_ENABLED = True
# HTTPCACHE_EXPIRATION_SECS = 0
# HTTPCACHE_DIR = "httpcache"
# HTTPCACHE_IGNORE_HTTP_CODES = []
# HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Set settings whose default value is deprecated to a future-proof value
FEED_EXPORT_ENCODING = "utf-8"

# Retry middleware with exponential backoff
RETRY_ENABLED = True
RETRY_TIMES = 5  # Increased for robustness
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429]  # Added common error codes
RETRY_PRIORITY_ADJUST = -1  # Reduce priority of retries


# Custom settings for text extraction
TRAFILATURA_CUTOFF = 100  # minimum length to keep
TEXT_MAX_LENGTH = 50000  # maximum text length to store

# Crawl depth settings
DEPTH_LIMIT = 1  # How deep to follow links from seed URLs
DEPTH_PRIORITY = 1  # Prioritize breadth-first (lower depth first)

# Job persistence for resumable crawls
JOBDIR = "crawls/gov-001"

# URL filtering
URLLENGTH_LIMIT = 2000  # Reject overly long URLs
DUPEFILTER_DEBUG = False  # Set to True to debug duplicate filtering

# URL patterns to exclude from crawling
EXCLUDED_URL_PATTERNS = [
    "mailto:",
    "javascript:",
    "tel:",
    "ftp:",
    "file:",
    "#",
    "void(0)",
]

# DNS timeout
DNS_TIMEOUT = 60  # DNS resolution timeout in seconds

# Redirect settings
REDIRECT_ENABLED = True
REDIRECT_MAX_TIMES = 5

# Media types to ignore
IGNORED_EXTENSIONS = [
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "zip",
    "tar",
    "gz",
    "rar",
    "7z",
    "jpg",
    "jpeg",
    "png",
    "gif",
    "bmp",
    "svg",
    "webp",
    "ico",
    "mp3",
    "mp4",
    "avi",
    "mov",
    "wmv",
    "flv",
    "exe",
    "dmg",
    "pkg",
    "deb",
    "rpm",
    "apk",
]

# Header settings for better compatibility
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

# GIS keywords for identifying geospatial data links
GIS_KEYWORDS = [
    "gis",
    "arcgis",
    "map",
    "geoportal",
    "spatial",
    "webmap",
    "mapserver",
    "geodata",
    "geospatial",
    "maps.arcgis.com",
    "axisgis.com",
    "/arcgis/rest/services",
]
