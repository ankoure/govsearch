# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


import os
from datetime import datetime, timezone
from opensearchpy import OpenSearch, RequestsHttpConnection
import string
import spacy
from sentence_transformers import SentenceTransformer

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
                        "keywords": {"type": "keyword"},
                        "chunks": {
                            "type": "nested",
                            "properties": {
                                "text": {"type": "text"},
                                "keywords": {"type": "keyword"},
                                "vector": {"type": "dense_vector", "dims": 384},
                            },
                        },
                        "gis_links": {
                            "type": "nested",
                            "properties": {
                                "url": {"type": "keyword"},
                                "text": {"type": "text"},
                            },
                        },
                        "osm_relation_id": {"type": "keyword"},
                    },
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


class KeywordVectorChunkPipeline:
    def __init__(
        self, top_n=15, chunk_size=300, chunk_overlap=50, model_name="all-MiniLM-L6-v2"
    ):
        # spaCy NLP
        self.nlp = spacy.load("en_core_web_sm")
        self.top_n = top_n
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        # Sentence transformer
        self.model = SentenceTransformer(model_name)

    def normalize_keyword(self, kw):
        kw = kw.lower().translate(str.maketrans("", "", string.punctuation)).strip()
        return kw

    def extract_keywords(self, text):
        doc = self.nlp(text)

        # Extract candidates: noun chunks, named entities, and important nouns/proper nouns
        candidates = []

        # Named entities (high value keywords)
        candidates.extend([ent.text for ent in doc.ents])

        # Noun chunks
        candidates.extend([chunk.text for chunk in doc.noun_chunks])

        # Individual proper nouns and important nouns
        candidates.extend(
            [
                token.text
                for token in doc
                if token.pos_ in ("PROPN", "NOUN") and not token.is_stop
            ]
        )

        # Normalize and filter using spaCy's built-in stopwords
        normalized_keywords = set()
        for kw in candidates:
            normalized = self.normalize_keyword(kw)
            if normalized and len(normalized) > 2:  # Filter short terms
                # Check if it's not a stopword by processing with spaCy
                kw_doc = self.nlp(normalized)
                if not all(token.is_stop for token in kw_doc):
                    normalized_keywords.add(normalized)

        # Rank by frequency (most common first)
        keyword_freq = {}
        for kw in normalized_keywords:
            keyword_freq[kw] = sum(
                1 for c in candidates if self.normalize_keyword(c) == kw
            )

        sorted_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)
        return [kw for kw, _ in sorted_keywords][: self.top_n]

    def chunk_text(self, text):
        """
        Split text into overlapping chunks
        """
        words = text.split()
        chunks = []
        start = 0
        while start < len(words):
            end = min(start + self.chunk_size, len(words))
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            if end == len(words):
                break
            start = end - self.chunk_overlap  # overlap
        return chunks

    def process_item(self, item, spider):
        text = item.get("text", "")
        if not text:
            item["keywords"] = []
            item["chunks"] = []
            return item

        # Top-level keywords
        item["keywords"] = self.extract_keywords(text)

        # Split text into chunks
        chunks = self.chunk_text(text)
        chunk_data = []
        for chunk in chunks:
            chunk_keywords = self.extract_keywords(chunk)
            chunk_vector = self.model.encode(chunk).tolist()
            chunk_data.append(
                {"text": chunk, "keywords": chunk_keywords, "vector": chunk_vector}
            )

        item["chunks"] = chunk_data
        return item
