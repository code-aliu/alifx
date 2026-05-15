"""
Regime service — orchestrates DB queries, runs detection, caches result.
"""
from sqlalchemy.orm import Session

from app.regime.detector import detect_regime
from app.impact.service import get_asset_impact
from app.market_data.service import get_price_history
from app.core import cache
from app.core.logging import get_logger

logger = get_logger(__name__)

CACHE_TTL = 300  # 5 minutes — matches pipeline interval


def get_current_regime(db: Session, hours: int = 6) -> dict:
    """Compute the global market regime across all tracked assets.

    Uses BTC price bars as the reference for price-based signals (most liquid,
    24/7 market). Falls back to SPY if BTC has no data.
    Result is cached in Redis for 5 minutes.
    """
    cached = cache.get_json("regime:global")
    if cached:
        return cached

    impact_summary = get_asset_impact(db, hours=hours)

    # BTC is the most liquid 24/7 reference for volatility + trend regime
    prices = get_price_history(db, "BTC", limit=60)
    if not prices:
        prices = get_price_history(db, "SPY", limit=60)

    result = detect_regime(prices or [], impact_summary)
    result["scope"] = "global"

    cache.set_json("regime:global", result, ttl_seconds=CACHE_TTL)
    logger.info(f"Regime: global={result['primary_regime']} confidence={result['confidence']}")
    return result


def get_asset_regime(db: Session, symbol: str, hours: int = 6) -> dict:
    """Compute regime for a specific asset using its own price bars.

    Volatility and trend signals are asset-specific; event/cross-asset
    signals are still global (they reflect macro conditions).
    """
    sym = symbol.upper()
    cached = cache.get_json(f"regime:{sym}")
    if cached:
        return cached

    impact_summary = get_asset_impact(db, hours=hours)
    prices         = get_price_history(db, sym, limit=60)

    result = detect_regime(prices or [], impact_summary)
    result["scope"]  = "asset"
    result["symbol"] = sym

    cache.set_json(f"regime:{sym}", result, ttl_seconds=CACHE_TTL)
    logger.info(f"Regime: {sym}={result['primary_regime']} confidence={result['confidence']}")
    return result
