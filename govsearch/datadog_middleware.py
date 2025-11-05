"""
Datadog monitoring middleware for Scrapy spider.
Collects custom metrics and traces for observability.
"""

import logging
from scrapy import Spider, Request, signals
from scrapy.http import Response
from scrapy.exceptions import NotConfigured
from ddtrace.trace import tracer
from ddtrace import patch
from datadog.dogstatsd.base import statsd


logger = logging.getLogger(__name__)


class DatadogStatsMiddleware:
    """
    Scrapy middleware for collecting custom metrics and sending to Datadog.

    Tracks:
    - Request/response counts and rates
    - HTTP status codes distribution
    - Response times
    - Error rates and types
    - Spider lifecycle events
    """

    def __init__(
        self,
        stats,
        dd_enabled=True,
        dd_statsd_host="datadog-agent",
        dd_statsd_port=8125,
    ):
        """
        Initialize Datadog middleware.

        Args:
            stats: Scrapy stats collector
            dd_enabled: Whether Datadog monitoring is enabled
            dd_statsd_host: Datadog agent hostname
            dd_statsd_port: Datadog DogStatsD port
        """
        self.stats = stats
        self.dd_enabled = dd_enabled

        if self.dd_enabled:
            # Configure DogStatsD connection
            statsd.host = dd_statsd_host
            statsd.port = dd_statsd_port
            logger.info(
                f"Datadog metrics enabled - sending to {dd_statsd_host}:{dd_statsd_port}"
            )
        else:
            logger.info("Datadog metrics disabled via configuration")

    @classmethod
    def from_crawler(cls, crawler):
        """Create middleware instance from Scrapy crawler."""
        # Check if Datadog is enabled in settings
        dd_enabled = crawler.settings.getbool("DATADOG_ENABLED", True)
        dd_statsd_host = crawler.settings.get("DATADOG_STATSD_HOST", "datadog-agent")
        dd_statsd_port = crawler.settings.getint("DATADOG_STATSD_PORT", 8125)

        if not dd_enabled:
            raise NotConfigured("Datadog monitoring is disabled")

        middleware = cls(
            stats=crawler.stats,
            dd_enabled=dd_enabled,
            dd_statsd_host=dd_statsd_host,
            dd_statsd_port=dd_statsd_port,
        )

        # Connect to Scrapy signals
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(middleware.item_scraped, signal=signals.item_scraped)
        crawler.signals.connect(middleware.item_dropped, signal=signals.item_dropped)

        return middleware

    def spider_opened(self, spider):
        """Called when spider opens."""
        if self.dd_enabled:
            statsd.increment("scrapy.spider.opened", tags=[f"spider:{spider.name}"])
            logger.info(f"Spider {spider.name} opened - Datadog monitoring active")

    def spider_closed(self, spider, reason):
        """Called when spider closes."""
        if self.dd_enabled:
            statsd.increment(
                "scrapy.spider.closed",
                tags=[f"spider:{spider.name}", f"reason:{reason}"],
            )

            # Send final stats
            stats_dict = self.stats.get_stats()
            if "item_scraped_count" in stats_dict:
                statsd.gauge(
                    "scrapy.items.total",
                    stats_dict["item_scraped_count"],
                    tags=[f"spider:{spider.name}"],
                )
            if "response_received_count" in stats_dict:
                statsd.gauge(
                    "scrapy.responses.total",
                    stats_dict["response_received_count"],
                    tags=[f"spider:{spider.name}"],
                )

            logger.info(f"Spider {spider.name} closed - final metrics sent to Datadog")

    def item_scraped(self, item, response, spider):
        """Called when an item is scraped."""
        if self.dd_enabled:
            statsd.increment(
                "scrapy.item.scraped",
                tags=[f"spider:{spider.name}", f"item_type:{type(item).__name__}"],
            )

    def item_dropped(self, item, response, exception, spider):
        """Called when an item is dropped."""
        if self.dd_enabled:
            statsd.increment(
                "scrapy.item.dropped",
                tags=[
                    f"spider:{spider.name}",
                    f"item_type:{type(item).__name__}",
                    f"reason:{type(exception).__name__}",
                ],
            )

    def process_request(self, request: Request, spider: Spider):
        """Process outgoing requests."""
        if self.dd_enabled:
            statsd.increment(
                "scrapy.request.sent",
                tags=[f"spider:{spider.name}", f"method:{request.method}"],
            )
        return None

    def process_response(self, request: Request, response: Response, spider: Spider):
        """Process incoming responses."""
        if self.dd_enabled:
            # Track response metrics
            statsd.increment(
                "scrapy.response.received",
                tags=[
                    f"spider:{spider.name}",
                    f"status:{response.status}",
                    f"status_class:{response.status // 100}xx",
                ],
            )

            # Track response size
            statsd.histogram(
                "scrapy.response.size",
                len(response.body),
                tags=[f"spider:{spider.name}", f"status:{response.status}"],
            )

            # Track response time if available
            if hasattr(request, "meta") and "download_latency" in request.meta:
                latency_ms = request.meta["download_latency"] * 1000
                statsd.histogram(
                    "scrapy.response.latency",
                    latency_ms,
                    tags=[f"spider:{spider.name}", f"status:{response.status}"],
                )

        return response

    def process_exception(self, request: Request, exception: Exception, spider: Spider):
        """Process exceptions."""
        if self.dd_enabled:
            statsd.increment(
                "scrapy.request.exception",
                tags=[f"spider:{spider.name}", f"exception:{type(exception).__name__}"],
            )
        return None


class DatadogTracingMiddleware:
    """
    Scrapy downloader middleware for distributed tracing with Datadog APM.
    Creates spans for each request/response cycle.
    """

    def __init__(self, dd_enabled=True, service_name="govsearch"):
        """Initialize tracing middleware."""
        self.dd_enabled = dd_enabled
        self.service_name = service_name

        if self.dd_enabled and tracer:
            # Patch supported libraries
            patch(requests=True)
            logger.info("Datadog APM tracing enabled")
        else:
            logger.info("Datadog APM tracing disabled")

    @classmethod
    def from_crawler(cls, crawler):
        """Create middleware instance from Scrapy crawler."""
        dd_enabled = crawler.settings.getbool("DATADOG_ENABLED", True)
        service_name = crawler.settings.get("DATADOG_SERVICE_NAME", "govsearch")

        if not dd_enabled:
            raise NotConfigured("Datadog monitoring is disabled")

        return cls(dd_enabled=dd_enabled, service_name=service_name)

    def process_request(self, request: Request, spider: Spider):
        """Create span for outgoing request."""
        if self.dd_enabled and tracer:
            span = tracer.trace(
                "scrapy.request",
                service=self.service_name,
                resource=f"{request.method} {request.url}",
                span_type="http",
            )
            span.set_tag("spider.name", spider.name)
            span.set_tag("http.method", request.method)
            span.set_tag("http.url", request.url)
            span.set_tag("component", "scrapy")

            # Store span in request meta for later access
            request.meta["_dd_span"] = span

        return None

    def process_response(self, request: Request, response: Response, spider: Spider):
        """Finish span for received response."""
        if self.dd_enabled and tracer:
            span = request.meta.get("_dd_span")
            if span:
                span.set_tag("http.status_code", response.status)
                span.set_tag("response.size", len(response.body))

                # Mark as error for 4xx/5xx responses
                if response.status >= 400:
                    span.error = 1

                span.finish()

        return response

    def process_exception(self, request: Request, exception: Exception, spider: Spider):
        """Record exception in span."""
        if self.dd_enabled and tracer:
            span = request.meta.get("_dd_span")
            if span:
                span.set_tag("error.type", type(exception).__name__)
                span.set_tag("error.message", str(exception))
                span.error = 1
                span.finish()

        return None
