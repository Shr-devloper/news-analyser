"""Hacker News connector using the official Firebase API."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.sources.base import Connector, FetchedArticle

_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
_HN_URL = "https://news.ycombinator.com/item?id={id}"


class HackerNewsConnector(Connector):
    kind = "hackernews"

    def fetch(self) -> list[FetchedArticle]:
        with httpx.Client(timeout=20.0) as client:
            ids = client.get(_TOP).json()[: self.max_items]
            articles: list[FetchedArticle] = []
            for item_id in ids:
                try:
                    item = client.get(_ITEM.format(id=item_id)).json()
                except (httpx.HTTPError, ValueError):
                    continue
                if not item or item.get("type") != "story" or not item.get("title"):
                    continue
                published = (
                    datetime.fromtimestamp(item["time"], tz=timezone.utc)
                    if item.get("time")
                    else None
                )
                articles.append(
                    FetchedArticle(
                        title=item["title"],
                        url=item.get("url") or _HN_URL.format(id=item_id),
                        summary=item.get("text"),
                        content=item.get("text"),
                        author=item.get("by"),
                        published_at=published,
                        extra={"score": item.get("score", 0), "hn_id": item_id},
                    )
                )
            return articles
