from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    scheduler: str
    version: str = "0.1.0"


class PriceBarResponse(BaseModel):
    symbol: str
    asset_class: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float]
    source: str
    fetched_at: str


class MarketDataResponse(BaseModel):
    prices: list[PriceBarResponse]
    count: int


class PriceHistoryResponse(BaseModel):
    symbol: str
    bars: list[PriceBarResponse]
    count: int


class MarketEventResponse(BaseModel):
    id: int
    headline: str
    category: str
    sentiment: str
    importance: str
    affected_assets: list[str]
    keywords: Optional[list[str]]
    extraction_method: str
    extracted_at: str


class EventsResponse(BaseModel):
    events: list[MarketEventResponse]
    count: int


class NewsArticleResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    source_name: Optional[str]
    provider: str
    published_at: Optional[str]
    fetched_at: str


class NewsResponse(BaseModel):
    articles: list[NewsArticleResponse]
    count: int


class ApiResponse(BaseModel):
    success: bool
    data: Any
    message: Optional[str] = None
