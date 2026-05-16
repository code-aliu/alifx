"""
Shared fixtures for AliFx integration tests.

Uses SQLite in-memory so tests run without PostgreSQL or Redis.
"""
import math
import random
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.news.models import NewsArticle
from app.events.models import MarketEvent
# Ensure all models are registered with Base before any db fixture calls create_all
from app.signals.models import TradingSignal  # noqa: F401
from app.market_data.models import PriceBar  # noqa: F401
from app.paper_trading.models import PaperTrade, PaperPortfolio  # noqa: F401
from app.signal_tracking.models import SignalOutcome  # noqa: F401


# ── Database fixture ──────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


# ── Price bar factory ─────────────────────────────────────────────────────────

def make_price_bars(
    symbol: str,
    start_price: float,
    end_price: float,
    n: int = 60,
    volatility_pct: float = 0.8,
    seed: int = 42,
) -> list[dict]:
    """Generate synthetic OHLC bars along a linear drift with Gaussian noise.

    All bars use sequential minute timestamps so ordering is deterministic.
    """
    rng = random.Random(seed)
    bars = []
    base_time = datetime(2026, 5, 14, 9, 0, 0)

    for i in range(n):
        # linear interpolation from start to end price
        progress = i / max(n - 1, 1)
        mid = start_price + (end_price - start_price) * progress

        noise = rng.gauss(0, mid * volatility_pct / 100)
        close = round(mid + noise, 6)
        high  = round(close * (1 + rng.uniform(0.001, 0.005)), 6)
        low   = round(close * (1 - rng.uniform(0.001, 0.005)), 6)
        open_ = round(close * (1 + rng.gauss(0, 0.002)), 6)
        volume = round(rng.uniform(500, 5000), 2)

        bars.append({
            "symbol":     symbol,
            "open":       open_,
            "high":       high,
            "low":        low,
            "close":      close,
            "volume":     volume,
            "fetched_at": base_time + timedelta(minutes=i),
        })

    return bars


# ── Standard price-bar fixtures ───────────────────────────────────────────────

@pytest.fixture
def btc_uptrend_bars():
    """BTC: 60-bar uptrend from $88,000 → $95,200. Represents post-ETF rally."""
    return make_price_bars("BTC", 88_000, 95_200, n=60, volatility_pct=1.2)


@pytest.fixture
def spy_bullish_bars():
    """SPY: 60-bar bullish run from $565 → $582. Follows dovish Fed pivot."""
    return make_price_bars("SPY", 565, 582, n=60, volatility_pct=0.4)


@pytest.fixture
def eurusd_recovery_bars():
    """EUR/USD: 60-bar recovery from 1.0750 → 1.0870 after USD weakens."""
    return make_price_bars("EURUSD", 1.0750, 1.0870, n=60, volatility_pct=0.3)


@pytest.fixture
def btc_downtrend_bars():
    """BTC: 60-bar downtrend from $95,000 → $82,000. Crypto regulation fears."""
    return make_price_bars("BTC", 95_000, 82_000, n=60, volatility_pct=1.5, seed=99)


# ── NewsArticle factory ───────────────────────────────────────────────────────

def make_linear_bars(
    symbol: str,
    start_price: float,
    end_price: float,
    n: int = 60,
) -> list[dict]:
    """Generate a perfectly linear OHLC series with no noise.

    Produces deterministic, trend-consistent MACD/RSI signals every run.
    Use this when a test needs a specific TA signal direction guaranteed.
    """
    bars = []
    base_time = datetime(2026, 5, 14, 9, 0, 0)
    for i in range(n):
        p = start_price + (end_price - start_price) * i / max(n - 1, 1)
        p = round(p, 6)
        bars.append({
            "symbol":     symbol,
            "open":       p,
            "high":       round(p * 1.0005, 6),
            "low":        round(p * 0.9995, 6),
            "close":      p,
            "volume":     1000.0,
            "fetched_at": base_time + timedelta(minutes=i),
        })
    return bars


def make_article(
    db,
    title: str,
    description: str = "",
    provider: str = "newsapi",
    external_id: str = None,
    published_at: datetime = None,
    fetched_at: datetime = None,
    processed: bool = False,
) -> NewsArticle:
    """Persist and return a NewsArticle ORM row."""
    article = NewsArticle(
        external_id=external_id or f"test-{hash(title) & 0xFFFFFFFF}",
        title=title,
        description=description,
        content=None,
        url="https://example.com",
        source_name="Test Source",
        provider=provider,
        published_at=published_at or datetime.utcnow(),
        fetched_at=fetched_at or datetime.utcnow(),
        processed=processed,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def make_market_event(
    db,
    article_id: int,
    headline: str,
    category: str,
    sentiment: str,
    importance: str,
    affected_assets: list[str],
) -> MarketEvent:
    """Persist and return a MarketEvent ORM row."""
    event = MarketEvent(
        news_article_id=article_id,
        headline=headline,
        category=category,
        sentiment=sentiment,
        importance=importance,
        affected_assets=affected_assets,
        keywords=[],
        llm_enriched=False,
        extraction_method="rule",
        extracted_at=datetime.utcnow(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
