import csv
import os
import urllib.parse
from datetime import datetime
import trafilatura
import scrapy
from scrapy.linkextractors import LinkExtractor
from ..items import GovSiteItem

SEEDS_FILE = os.getenv("SEEDS_FILE", "seeds.csv")


class GovSpider(scrapy.Spider):
    name = "gov"
    custom_settings = {
        "ITEM_PIPELINES": {"govsearch.pipelines.OpenSearchPipeline": 300}
    }

    def start_requests(self):
        if not os.path.exists(SEEDS_FILE):
            self.logger.error("Seeds file not found: %s", SEEDS_FILE)
            return
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
                    }
                    yield scrapy.Request(
                        url=url,
                        callback=self.parse,
                        meta=meta,
                        errback=self.handle_error,
                    )

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
        item["crawled_at"] = datetime.utcnow().isoformat()
        item["source_name"] = response.meta.get("source_name")

        # Extract GIS-related links
        gis_keywords = [
            "gis",
            "arcgis",
            "map",
            "geoportal",
            "spatial",
            "webmap",
            "mapserver",
            "geodata",
            "geospatial",
            "maps.arcgis.com" "axisgis.com",
            "/arcgis/rest/services",
        ]
        le = LinkExtractor()
        all_links = le.extract_links(response)

        gis_links = []
        for link in all_links:
            link_text = (link.text or "").lower()
            link_url = link.url.lower()

            if any(kw in link_url or kw in link_text for kw in gis_keywords):
                gis_links.append({"url": link.url, "text": link.text})

        item["gis_links"] = gis_links

        osm_relation_id = response.meta.get("osm_relation_id")
        if osm_relation_id:
            item["osm_relation_id"] = osm_relation_id

        yield item

        # Follow internal links to gather site content (depth-limited crawl)
        for href in response.css("a::attr(href)").getall():
            href = response.urljoin(href)
            if self.allowed_domain(href, response):
                yield scrapy.Request(
                    href,
                    callback=self.parse,
                    meta=response.meta,
                    errback=self.handle_error,
                )

    def allowed_domain(self, url, response):
        """Helper to keep crawler on same domain"""
        start_domain = response.meta.get("start_domain")
        if not start_domain:
            return True
        return urllib.parse.urlparse(url).netloc == start_domain

    def handle_error(self, failure):
        """Handle request errors"""
        self.logger.error(
            "Request failed for %s: %s", failure.request.url, failure.value
        )
