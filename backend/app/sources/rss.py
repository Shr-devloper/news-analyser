"""Generic RSS/Atom connector — powers most configured sources."""

from __future__ import annotations

from datetime import datetime, timezone

import feedparser
import httpx
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from app.sources.base import Connector, FetchedArticle

_USER_AGENT = "AINewsAgent/1.0 (+https://news.ai)"


def _clean_html(text: str | None) -> str | None:
    if not text:
        return None
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)


def _parse_date(entry: dict) -> datetime | None:
    for key in ("published", "updated", "created"):
        value = entry.get(key)
        if value:
            try:
                dt = date_parser.parse(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError, OverflowError):
                continue
    return None


class RSSConnector(Connector):
    kind = "rss"

    def fetch(self) -> list[FetchedArticle]:
        # Fetch with httpx (gives us proper UA + timeout) then hand bytes to feedparser.
        resp = httpx.get(
            self.url,
            headers={"User-Agent": _USER_AGENT},
            timeout=20.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        articles: list[FetchedArticle] = []
        for entry in feed.entries[: self.max_items]:
            link = entry.get("link") or ""
            title = (entry.get("title") or "").strip()
            if not link or not title:
                continue
            summary = _clean_html(entry.get("summary") or entry.get("description"))
            content = None
            if entry.get("content"):
                content = _clean_html(entry["content"][0].get("value"))
            articles.append(
                FetchedArticle(
                    title=title,
                    url=link,
                    summary=summary,
                    content=content or summary,
                    author=entry.get("author"),
                    published_at=_parse_date(entry),
                )
            )
        return articles
