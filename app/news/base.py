from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Article:
    external_id: Optional[str]
    title: str
    description: Optional[str]
    content: Optional[str]
    url: Optional[str]
    source_name: Optional[str]
    provider: str
    published_at: Optional[datetime]


class BaseNewsProvider(ABC):
    """All news providers implement this interface.

    To add a new source: subclass this, implement fetch_articles(),
    register it in news/service.py.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def fetch_articles(self) -> list[Article]:
        """Fetch recent articles from this source.

        Should not raise — log and return [] on failure.
        """
        ...
