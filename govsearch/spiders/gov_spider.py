import csv
import os
import urllib.parse
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import trafilatura
import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import SitemapSpider
from ..items import GovSiteItem, CrawlErrorItem

SEEDS_FILE = os.getenv("SEEDS_FILE", "seeds.csv")


class GovSpider(SitemapSpider):
    name = "gov"

    def __init__(self, *args, **kwargs):
        super(GovSpider, self).__init__(*args, **kwargs)
        self.sitemap_urls = []
        self.sitemap_found = {}  # Track which domains have sitemaps
        self.sitemap_attempted = set()  # Track which domains we've tried sitemaps for

    def start_requests(self):
        if not os.path.exists(SEEDS_FILE):
            self.logger.error("Seeds file not found: %s", SEEDS_FILE)
            return

        sitemap_enabled = self.settings.getbool("SITEMAP_ENABLED", True)

        with open(SEEDS_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get("website")
                if url:
                    # normalize
                    if not urllib.parse.urlparse(url).scheme:
                        url = "https://" + url
                    meta = {
                        "source_name": row.get("source_name"),
                        "start_domain": urllib.parse.urlparse(url).netloc,
                        "osm_relation_id": row.get("@id"),
                        "is_seed": True,
                    }

                    parsed = urllib.parse.urlparse(url)
                    base_url = f"{parsed.scheme}://{parsed.netloc}"

                    # Try to fetch sitemap first if enabled
                    if sitemap_enabled and parsed.netloc not in self.sitemap_attempted:
                        self.sitemap_attempted.add(parsed.netloc)

                        # Get sitemap URL patterns from settings
                        sitemap_patterns = self.settings.getlist(
                            "SITEMAP_URLS_PATTERN",
                            [
                                "/sitemap.xml",
                                "/sitemap_index.xml",
                                "/sitemap-index.xml",
                            ],
                        )

                        sitemap_urls = [
                            f"{base_url}{pattern}" for pattern in sitemap_patterns
                        ]

                        # Also check robots.txt for sitemap references
                        yield scrapy.Request(
                            url=f"{base_url}/robots.txt",
                            callback=self.parse_robots_for_sitemap,
                            meta={
                                **meta,
                                "seed_url": url,
                                "base_url": base_url,
                                "default_sitemaps": sitemap_urls,
                            },
                            errback=self.robots_not_found,
                            dont_filter=True,
                            priority=10,  # High priority for discovery
                        )
                    else:
                        # Sitemap disabled or already tried, start regular crawl
                        yield scrapy.Request(
                            url=url,
                            callback=self.parse,
                            meta=meta,
                            errback=self.handle_error,
                        )

    def robots_not_found(self, failure):
        """Handle robots.txt not found - try default sitemap locations"""
        request = failure.request
        meta = request.meta
        seed_url = meta.get("seed_url")
        base_url = meta.get("base_url")
        default_sitemaps = meta.get("default_sitemaps", [])

        self.logger.info(
            f"robots.txt not found for {base_url}, trying default sitemap locations"
        )
        yield from self.try_default_sitemaps(meta, seed_url, base_url, default_sitemaps)

    def parse_robots_for_sitemap(self, response):
        """Parse robots.txt to find sitemap references"""
        meta = response.meta
        base_url = meta.get("base_url")
        seed_url = meta.get("seed_url")

        # Extract sitemap URLs from robots.txt
        sitemap_urls = []
        if response.status == 200:
            for line in response.text.split("\n"):
                line = line.strip()
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    sitemap_urls.append(sitemap_url)
                    self.logger.info(f"Found sitemap in robots.txt: {sitemap_url}")

        # If sitemaps found in robots.txt, try them
        if sitemap_urls:
            for sitemap_url in sitemap_urls:
                yield scrapy.Request(
                    url=sitemap_url,
                    callback=self.parse_sitemap_check,
                    meta={**meta, "seed_url": seed_url},
                    errback=self.sitemap_not_found,
                    dont_filter=True,
                    priority=9,
                )
        else:
            # No sitemaps in robots.txt, try default locations
            default_sitemaps = meta.get("default_sitemaps", [])
            yield from self.try_default_sitemaps(
                meta, seed_url, base_url, default_sitemaps
            )

    def try_default_sitemaps(self, meta, seed_url, base_url, sitemap_urls):
        """Try default sitemap locations"""
        for sitemap_url in sitemap_urls:
            yield scrapy.Request(
                url=sitemap_url,
                callback=self.parse_sitemap_check,
                meta={**meta, "seed_url": seed_url, "base_url": base_url},
                errback=self.sitemap_not_found,
                dont_filter=True,
                priority=9,
            )

    def sitemap_not_found(self, failure):
        """Handle sitemap not found - fall back to regular crawling"""
        request = failure.request
        meta = request.meta
        start_domain = meta.get("start_domain")

        # Mark that we tried and failed to find sitemap
        if start_domain and start_domain not in self.sitemap_found:
            self.sitemap_found[start_domain] = False
            self.logger.info(
                f"No sitemap found, falling back to regular crawl for {start_domain}"
            )

            # Start regular crawl from seed URL
            seed_url = meta.get("seed_url")
            if seed_url:
                yield scrapy.Request(
                    url=seed_url,
                    callback=self.parse,
                    meta=meta,
                    errback=self.handle_error,
                )

    def parse_sitemap_check(self, response):
        """Check if sitemap exists and parse it"""
        meta = response.meta
        start_domain = meta.get("start_domain")

        # Check if this is a valid sitemap
        if response.status == 200 and (
            b"<urlset" in response.body or b"<sitemapindex" in response.body
        ):
            self.logger.info(f"Found sitemap at {response.url}")
            self.sitemap_found[start_domain] = True

            # Parse the sitemap using Scrapy's built-in sitemap parser
            for request_or_item in self._parse_sitemap(response):
                if isinstance(request_or_item, scrapy.Request):
                    # Add our metadata to sitemap-generated requests
                    request_or_item.meta.update(meta)
                    request_or_item.callback = self.parse
                    request_or_item.errback = self.handle_error
                yield request_or_item

            # Also crawl the seed URL to supplement sitemap
            seed_url = meta.get("seed_url")
            if seed_url:
                yield scrapy.Request(
                    url=seed_url,
                    callback=self.parse,
                    meta=meta,
                    errback=self.handle_error,
                )
        else:
            # Not a valid sitemap, try next location or fall back
            pass

    def parse(self, response):
        item = GovSiteItem()
        item["url"] = response.url
        item["domain"] = urllib.parse.urlparse(response.url).netloc
        item["title"] = response.xpath("//title/text()").get(default="").strip()
        item["depth"] = response.meta.get("depth", 0)

        raw = "\n".join(response.css("body *::text").getall()).strip()
        # use trafilatura to extract readable text if available
        try:
            extracted = trafilatura.extract(response.text)
        except Exception:
            extracted = None
        text = extracted or raw
        text_max_length = int(self.settings.get("TEXT_MAX_LENGTH", 50000))
        if text and len(text) >= int(self.settings.get("TRAFILATURA_CUTOFF", 100)):
            item["text"] = text[:text_max_length]
        else:
            item["text"] = raw[:text_max_length]
        item["status"] = str(response.status)
        item["crawled_at"] = datetime.now(timezone.utc).isoformat()
        item["source_name"] = response.meta.get("source_name")

        # Extract GIS-related links using keywords from settings
        gis_keywords = self.settings.getlist("GIS_KEYWORDS", [])
        le = LinkExtractor()
        all_links = le.extract_links(response)

        gis_links = []
        for link in all_links:
            link_text = (link.text or "").lower()
            link_url = link.url.lower()

            if any(
                kw.lower() in link_url or kw.lower() in link_text for kw in gis_keywords
            ):
                gis_links.append({"url": link.url, "text": link.text})

        item["gis_links"] = gis_links

        osm_relation_id = response.meta.get("osm_relation_id")
        if osm_relation_id:
            item["osm_relation_id"] = osm_relation_id

        yield item

        # Follow internal links to gather site content (depth-limited crawl)
        for href in response.css("a::attr(href)").getall():
            href = response.urljoin(href)

            # Apply filtering
            if not self.should_follow_link(href):
                continue

            if not self.allowed_domain(href, response):
                continue

            # Normalize URL to avoid duplicates
            normalized_href = self.normalize_url(href)

            yield scrapy.Request(
                normalized_href,
                callback=self.parse,
                meta=response.meta,
                errback=self.handle_error,
            )

    def normalize_url(self, url):
        """Normalize URL by removing unnecessary query parameters and fragments"""
        try:
            parsed = urlparse(url)
            # Sort query parameters for consistency
            query_dict = parse_qs(parsed.query, keep_blank_values=True)
            sorted_query = urlencode(sorted(query_dict.items()), doseq=True)
            # Rebuild URL without fragment
            normalized = urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    sorted_query,
                    "",  # Remove fragment
                )
            )
            return normalized
        except Exception as e:
            self.logger.warning(f"Failed to normalize URL {url}: {e}")
            return url

    def should_follow_link(self, url):
        """Check if a link should be followed"""
        url_lower = url.lower()

        # Check for excluded patterns from settings
        excluded_patterns = self.settings.getlist("EXCLUDED_URL_PATTERNS", [])
        for pattern in excluded_patterns:
            if pattern.lower() in url_lower:
                return False

        # Check for excluded file extensions from settings
        ignored_extensions = self.settings.getlist("IGNORED_EXTENSIONS", [])
        for ext in ignored_extensions:
            # Add leading dot if not present in settings
            ext_with_dot = ext if ext.startswith(".") else f".{ext}"
            if url_lower.endswith(ext_with_dot.lower()):
                return False

        return True

    def allowed_domain(self, url, response):
        """Helper to keep crawler on same domain"""
        start_domain = response.meta.get("start_domain")
        if not start_domain:
            return True
        return urllib.parse.urlparse(url).netloc == start_domain

    def handle_error(self, failure):
        """Handle request errors and create error items for tracking"""
        from twisted.internet.error import (
            DNSLookupError,
            TimeoutError,
            TCPTimedOutError,
        )
        from scrapy.spidermiddlewares.httperror import HttpError

        request = failure.request

        # Create error item for tracking
        error_item = CrawlErrorItem()
        error_item["url"] = request.url
        error_item["timestamp"] = datetime.now(timezone.utc).isoformat()
        error_item["source_name"] = request.meta.get("source_name", "unknown")
        error_item["retry_count"] = request.meta.get("retry_times", 0)

        if failure.check(HttpError):
            response = failure.value.response
            error_item["error_type"] = "HttpError"
            error_item["status_code"] = response.status
            error_item["error_message"] = f"HTTP {response.status}"
            self.logger.error(f"HttpError on {request.url}: {response.status}")
        elif failure.check(DNSLookupError):
            error_item["error_type"] = "DNSLookupError"
            error_item["error_message"] = "DNS lookup failed"
            error_item["status_code"] = None
            self.logger.error(f"DNSLookupError on {request.url}")
        elif failure.check(TimeoutError, TCPTimedOutError):
            error_item["error_type"] = "TimeoutError"
            error_item["error_message"] = "Request timed out"
            error_item["status_code"] = None
            self.logger.error(f"TimeoutError on {request.url}")
        else:
            error_item["error_type"] = "UnknownError"
            error_item["error_message"] = str(failure.value)
            error_item["status_code"] = None
            self.logger.error(f"Unknown error on {request.url}: {failure.value}")

        # Yield error item for pipeline processing
        yield error_item
