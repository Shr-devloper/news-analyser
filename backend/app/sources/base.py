"""Source connector contracts.

Adding a new source = implement a ``Connector`` subclass and register it in
``registry.CONNECTORS``. Everything downstream (collector agent, dedup, etc.)
operates on the normalized ``FetchedArticle`` dataclass, so sources stay
fully decoupled from the pipeline.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class FetchedArticle:
    title: str
    url: str
    summary: str | None = None
    content: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    language: str = "en"
    extra: dict = field(default_factory=dict)

    @property
    def url_hash(self) -> str:
        return hashlib.sha256(self.url.strip().lower().encode()).hexdigest()

    def is_valid(self) -> bool:
        return bool(self.title and self.url)


class Connector(ABC):
    """Base class all source connectors implement."""

    #: short identifier used in the ``news_sources.connector`` column
    kind: str = "base"

    def __init__(self, *, name: str, url: str, max_items: int = 40) -> None:
        self.name = name
        self.url = url
        self.max_items = max_items

    @abstractmethod
    def fetch(self) -> list[FetchedArticle]:
        """Return up to ``max_items`` normalized articles. Must raise on failure."""
        raise NotImplementedError
