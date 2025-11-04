# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
from scrapy.exceptions import IgnoreRequest
from scrapy.http import HtmlResponse
import logging

# useful for handling different item types with a single interface
from itemadapter import ItemAdapter

logger = logging.getLogger(__name__)


class GovsearchSpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, or item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request or item objects.
        pass

    async def process_start(self, start):
        # Called with an async iterator over the spider start() method or the
        # maching method of an earlier spider middleware.
        async for item_or_request in start:
            yield item_or_request

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class GovsearchDownloaderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class ResponseValidationMiddleware:
    """Validates responses before processing"""

    def __init__(self, stats):
        self.stats = stats

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.stats)

    def process_response(self, request, response, spider):
        # Validate content type
        content_type = (
            response.headers.get(b"Content-Type", b"")
            .decode("utf-8", errors="ignore")
            .lower()
        )

        # Only process HTML/XML content
        if not any(ct in content_type for ct in ["html", "xml", "text/plain", ""]):
            logger.debug(
                f"Ignoring non-HTML response from {response.url}: {content_type}"
            )
            self.stats.inc_value("validation/non_html_ignored")
            raise IgnoreRequest(f"Non-HTML content type: {content_type}")

        # Check for empty responses
        if len(response.body) == 0:
            logger.warning(f"Empty response from {response.url}")
            self.stats.inc_value("validation/empty_response")
            raise IgnoreRequest("Empty response body")

        # Check for minimum content length
        if isinstance(response, HtmlResponse) and len(response.text) < 100:
            logger.warning(
                f"Response too short from {response.url}: {len(response.text)} chars"
            )
            self.stats.inc_value("validation/too_short")
            raise IgnoreRequest("Response too short")

        return response

    def process_exception(self, request, exception, spider):
        # Log exceptions for analysis
        logger.error(f"Exception processing {request.url}: {exception}")
        self.stats.inc_value("validation/exceptions")
        return None
