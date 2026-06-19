"""Source registry: maps connector kinds to classes and seeds default sources.

To add a brand-new source, append a dict to ``DEFAULT_SOURCES`` (for RSS) or
register a new connector class in ``CONNECTORS`` for a custom protocol.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import NewsSource
from app.sources.base import Connector
from app.sources.hackernews import HackerNewsConnector
from app.sources.rss import RSSConnector

CONNECTORS: dict[str, type[Connector]] = {
    "rss": RSSConnector,
    "hackernews": HackerNewsConnector,
}

# Curated, trusted defaults. ``category_hint`` biases the classifier.
DEFAULT_SOURCES: list[dict] = [
    {"slug": "reuters", "name": "Reuters", "connector": "rss",
     "url": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
     "category_hint": "World", "country": "US"},
    {"slug": "bbc", "name": "BBC News", "connector": "rss",
     "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
     "category_hint": "World", "country": "GB"},
    {"slug": "cnn", "name": "CNN", "connector": "rss",
     "url": "http://rss.cnn.com/rss/edition.rss",
     "category_hint": "World", "country": "US"},
    {"slug": "ap", "name": "Associated Press", "connector": "rss",
     "url": "https://rsshub.app/apnews/topics/apf-topnews",
     "category_hint": "World", "country": "US"},
    {"slug": "npr", "name": "NPR", "connector": "rss",
     "url": "https://feeds.npr.org/1001/rss.xml",
     "category_hint": "World", "country": "US"},
    {"slug": "economic-times", "name": "Economic Times", "connector": "rss",
     "url": "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
     "category_hint": "Business", "country": "IN"},
    {"slug": "the-hindu", "name": "The Hindu", "connector": "rss",
     "url": "https://www.thehindu.com/news/national/feeder/default.rss",
     "category_hint": "India", "country": "IN"},
    {"slug": "times-of-india", "name": "Times of India", "connector": "rss",
     "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
     "category_hint": "India", "country": "IN"},
    {"slug": "techcrunch", "name": "TechCrunch", "connector": "rss",
     "url": "https://techcrunch.com/feed/",
     "category_hint": "Technology", "country": "US"},
    {"slug": "ars-technica", "name": "Ars Technica", "connector": "rss",
     "url": "https://feeds.arstechnica.com/arstechnica/index",
     "category_hint": "Technology", "country": "US"},
    {"slug": "hacker-news", "name": "Hacker News", "connector": "hackernews",
     "url": "https://news.ycombinator.com/",
     "category_hint": "Technology", "country": "US"},
    {"slug": "google-news", "name": "Google News", "connector": "rss",
     "url": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
     "category_hint": "World", "country": "US"},
]


def get_connector(source: NewsSource) -> Connector:
    cls = CONNECTORS.get(source.connector)
    if cls is None:
        raise ValueError(f"Unknown connector kind: {source.connector!r}")
    return cls(name=source.name, url=source.url, max_items=settings.MAX_ARTICLES_PER_SOURCE)


def seed_sources(db: Session) -> int:
    """Insert any missing default sources. Idempotent. Returns count added."""
    added = 0
    existing = {row[0] for row in db.query(NewsSource.slug).all()}
    for spec in DEFAULT_SOURCES:
        if spec["slug"] in existing:
            continue
        db.add(NewsSource(**spec))
        added += 1
    if added:
        db.commit()
    return added
