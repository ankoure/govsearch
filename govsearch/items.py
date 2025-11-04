# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from scrapy import Item, Field


class GovsearchItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass


class GovSiteItem(Item):
    url = Field()
    domain = Field()
    title = Field()
    text = Field()
    status = Field()
    crawled_at = Field()
    source_name = Field()
    gis_links = Field()  # List of GIS-related links found on page
    # OSM geometry fields
    osm_relation_id = Field()  # OSM relation ID for this domain
    depth = Field()
