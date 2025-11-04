# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


import os
from datetime import datetime, timezone
from opensearchpy import OpenSearch, RequestsHttpConnection


OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", 9200))
INDEX_NAME = os.getenv("OPENSEARCH_INDEX", "govsites")


class OpenSearchPipeline:
    def open_spider(self, spider):
        self.client = OpenSearch(
            hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            connection_class=RequestsHttpConnection,
        )
        # create index with a simple mapping if it doesn't exist
        if not self.client.indices.exists(INDEX_NAME):
            mapping = {
                "settings": {"number_of_shards": 1},
                "mappings": {
                    "properties": {
                        "url": {"type": "keyword"},
                        "domain": {"type": "keyword"},
                        "title": {"type": "text"},
                        "text": {"type": "text"},
                        "status": {"type": "keyword"},
                        "crawled_at": {"type": "date"},
                        "source_name": {"type": "keyword"},
                        "gis_links": {
                            "type": "nested",
                            "properties": {
                                "url": {"type": "keyword"},
                                "text": {"type": "text"},
                            },
                        },
                        "osm_relation_id": {"type": "keyword"},
                    }
                },
            }
            self.client.indices.create(index=INDEX_NAME, body=mapping)

    def process_item(self, item, spider):
        doc = dict(item)
        # ensure crawled_at
        doc.setdefault("crawled_at", datetime.now(timezone.utc).isoformat())
        # index document
        self.client.index(index=INDEX_NAME, body=doc)
        return item

    def close_spider(self, spider):
        try:
            self.client.close()
        except Exception:
            pass
