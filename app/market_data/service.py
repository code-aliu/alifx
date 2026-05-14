from sqlalchemy.orm import Session
from app.market_data.base import BaseMarketProvider, PriceBar as PriceBarDTO
from app.market_data.models import PriceBar
from app.market_data.providers.binance import BinanceProvider
from app.market_data.providers.yahoo_finance import YahooFinanceProvider
from app.market_data.providers.fx_api import FxApiProvider
from app.core import cache
from app.core.logging import get_logger
import json

logger = get_logger(__name__)

# Asset universe — add/remove symbols here without touching provider code
CRYPTO_SYMBOLS  = ["BTC", "ETH"]
STOCK_SYMBOLS   = ["SPY", "QQQ", "NVDA", "AAPL"]
FOREX_SYMBOLS   = ["EUR/USD", "USD/JPY", "GBP/USD"]

CACHE_TTL = 180  # seconds — slightly longer than polling interval


def _build_providers() -> list[tuple[BaseMarketProvider, list[str]]]:
    return [
        (BinanceProvider(),      CRYPTO_SYMBOLS),
        (YahooFinanceProvider(), STOCK_SYMBOLS),
        (FxApiProvider(),        FOREX_SYMBOLS),
    ]


def fetch_and_store_all(db: Session) -> int:
    """Fetch prices from all providers and persist to DB + Redis cache.

    Returns the number of price bars stored.
    """
    stored = 0
    for provider, symbols in _build_providers():
        try:
            bars = provider.fetch_prices(symbols)
            for bar_dto in bars:
                _persist_bar(db, bar_dto)
                _cache_bar(bar_dto)
                stored += 1
            logger.info(f"Market data: fetched {len(bars)} bars from {provider.name}")
        except Exception as e:
            logger.error(f"Market data: provider {provider.name} failed: {e}")
    db.commit()
    return stored


def _persist_bar(db: Session, dto: PriceBarDTO) -> None:
    bar = PriceBar(
        symbol=dto.symbol,
        asset_class=dto.asset_class,
        open=dto.open,
        high=dto.high,
        low=dto.low,
        close=dto.close,
        volume=dto.volume,
        source=dto.source,
        fetched_at=dto.fetched_at,
    )
    db.add(bar)


def _cache_bar(dto: PriceBarDTO) -> None:
    key = f"price:{dto.symbol}"
    cache.set_json(key, {
        "symbol": dto.symbol,
        "asset_class": dto.asset_class,
        "close": dto.close,
        "high": dto.high,
        "low": dto.low,
        "volume": dto.volume,
        "source": dto.source,
        "fetched_at": dto.fetched_at.isoformat(),
    }, ttl_seconds=CACHE_TTL)


def get_latest_prices(db: Session) -> list[dict]:
    """Return latest price for each tracked symbol. Checks Redis first, falls back to DB."""
    all_symbols = (
        [s.upper() for s in CRYPTO_SYMBOLS] +
        STOCK_SYMBOLS +
        [s.replace("/", "").upper() for s in FOREX_SYMBOLS]
    )
    results = []
    for sym in all_symbols:
        cached = cache.get_json(f"price:{sym}")
        if cached:
            results.append(cached)
        else:
            row = (
                db.query(PriceBar)
                .filter(PriceBar.symbol == sym)
                .order_by(PriceBar.fetched_at.desc())
                .first()
            )
            if row:
                results.append(row.to_dict())
    return results


def get_price_history(db: Session, symbol: str, limit: int = 100) -> list[dict]:
    rows = (
        db.query(PriceBar)
        .filter(PriceBar.symbol == symbol.upper())
        .order_by(PriceBar.fetched_at.desc())
        .limit(limit)
        .all()
    )
    return [r.to_dict() for r in reversed(rows)]
