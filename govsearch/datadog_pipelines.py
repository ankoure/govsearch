"""
Datadog-instrumented pipelines for monitoring data processing performance.
"""

import logging
import time
from typing import Any
from datadog.dogstatsd.base import statsd
from scrapy import Spider
from govsearch.pipelines import OpenSearchPipeline

logger = logging.getLogger(__name__)


class DatadogPipelineMetrics:
    """
    Wrapper for existing pipelines to add Datadog metrics.
    Tracks processing time, success/failure rates, and item types.
    """

    def __init__(
        self, dd_enabled=True, dd_statsd_host="datadog-agent", dd_statsd_port=8125
    ):
        """Initialize Datadog pipeline metrics."""
        self.dd_enabled = dd_enabled

        if self.dd_enabled:
            statsd.host = dd_statsd_host
            statsd.port = dd_statsd_port
            logger.info("Datadog pipeline metrics enabled")
        else:
            logger.info("Datadog pipeline metrics disabled")

    @classmethod
    def from_crawler(cls, crawler):
        """Create instance from Scrapy crawler."""
        dd_enabled = crawler.settings.getbool("DATADOG_ENABLED", True)
        dd_statsd_host = crawler.settings.get("DATADOG_STATSD_HOST", "datadog-agent")
        dd_statsd_port = crawler.settings.getint("DATADOG_STATSD_PORT", 8125)

        return cls(
            dd_enabled=dd_enabled,
            dd_statsd_host=dd_statsd_host,
            dd_statsd_port=dd_statsd_port,
        )

    def process_item(self, item: Any, spider: Spider):
        """
        Process items and track metrics.
        This should be added to the pipeline list.
        """
        if self.dd_enabled:
            start_time = time.time()

            # Track item processing
            item_type = type(item).__name__
            statsd.increment(
                "scrapy.pipeline.item.processed",
                tags=[f"spider:{spider.name}", f"item_type:{item_type}"],
            )

            # Track specific item types for GovSearch
            if item_type == "GovSiteItem":
                # Track government site metrics
                if "osm_relation_id" in item and item["osm_relation_id"]:
                    statsd.increment(
                        "govsearch.item.with_osm_id", tags=[f"spider:{spider.name}"]
                    )

                if "gis_links" in item:
                    gis_link_count = len(item.get("gis_links", []))
                    statsd.histogram(
                        "govsearch.gis_links.count",
                        gis_link_count,
                        tags=[f"spider:{spider.name}"],
                    )

                if "sitemap_urls" in item:
                    sitemap_count = len(item.get("sitemap_urls", []))
                    statsd.histogram(
                        "govsearch.sitemaps.count",
                        sitemap_count,
                        tags=[f"spider:{spider.name}"],
                    )

            elif item_type == "CrawlErrorItem":
                # Track errors
                error_type = item.get("error_type", "unknown")
                statsd.increment(
                    "govsearch.crawl.error",
                    tags=[f"spider:{spider.name}", f"error_type:{error_type}"],
                )

            # Track processing time
            processing_time = (time.time() - start_time) * 1000  # Convert to ms
            statsd.histogram(
                "scrapy.pipeline.processing_time",
                processing_time,
                tags=[f"spider:{spider.name}", f"item_type:{item_type}"],
            )

        return item

    def open_spider(self, spider: Spider):
        """Called when spider opens."""
        if self.dd_enabled:
            statsd.increment("scrapy.pipeline.opened", tags=[f"spider:{spider.name}"])
            logger.info(f"Datadog pipeline metrics active for spider {spider.name}")

    def close_spider(self, spider: Spider):
        """Called when spider closes."""
        if self.dd_enabled:
            statsd.increment("scrapy.pipeline.closed", tags=[f"spider:{spider.name}"])


class DatadogOpenSearchMetrics:
    """
    Decorator/wrapper for OpenSearchPipeline to add indexing metrics.
    """

    def __init__(self, dd_enabled=True):
        """
        Initialize the wrapper.

        Args:
            dd_enabled: Whether Datadog is enabled
        """
        self.dd_enabled = dd_enabled
        self.pipeline = None

    @classmethod
    def from_crawler(cls, crawler):
        """Create wrapped pipeline from crawler."""
        dd_enabled = crawler.settings.getbool("DATADOG_ENABLED", True)
        return cls(dd_enabled=dd_enabled)

    def open_spider(self, spider: Spider):
        """Initialize OpenSearch pipeline."""
        # Import here to avoid circular dependency

        # Create the actual OpenSearch pipeline
        self.pipeline = OpenSearchPipeline()
        if hasattr(self.pipeline, "open_spider"):
            self.pipeline.open_spider(spider)

    def close_spider(self, spider: Spider):
        """Close OpenSearch pipeline."""
        if self.pipeline and hasattr(self.pipeline, "close_spider"):
            self.pipeline.close_spider(spider)

    def process_item(self, item: Any, spider: Spider):
        """
        Process item through OpenSearch pipeline with metrics.
        """
        start_time = time.time()

        try:
            # Process through original pipeline
            result = self.pipeline.process_item(item, spider)

            # Track successful indexing
            if self.dd_enabled:
                indexing_time = (time.time() - start_time) * 1000
                statsd.histogram(
                    "opensearch.indexing.latency",
                    indexing_time,
                    tags=[
                        f"spider:{spider.name}",
                        f"item_type:{type(item).__name__}",
                        "status:success",
                    ],
                )
                statsd.increment(
                    "opensearch.document.indexed",
                    tags=[f"spider:{spider.name}", f"item_type:{type(item).__name__}"],
                )

            return result

        except Exception as e:
            # Track indexing failures
            if self.dd_enabled:
                indexing_time = (time.time() - start_time) * 1000
                statsd.histogram(
                    "opensearch.indexing.latency",
                    indexing_time,
                    tags=[
                        f"spider:{spider.name}",
                        f"item_type:{type(item).__name__}",
                        "status:error",
                    ],
                )
                statsd.increment(
                    "opensearch.indexing.error",
                    tags=[f"spider:{spider.name}", f"error:{type(e).__name__}"],
                )

            # Re-raise the exception
            raise
