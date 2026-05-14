from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class PriceBar:
    symbol: str
    asset_class: str       # crypto | stock | forex
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float]
    source: str
    fetched_at: datetime


class BaseMarketProvider(ABC):
    """All market data providers implement this interface.

    To add a new provider: subclass this, implement fetch_prices(),
    register it in market_data/service.py.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def fetch_prices(self, symbols: list[str]) -> list[PriceBar]:
        """Fetch current price bars for the given symbols.

        Returns only the symbols this provider can handle.
        Raises ProviderError on unrecoverable failures.
        """
        ...
