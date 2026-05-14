from sqlalchemy.orm import Session
from app.market_data.service import get_price_history
from app.analysis.indicators import compute_all
from app.analysis.patterns import detect_breakout, detect_trend
from app.impact.rules import TRACKED_SYMBOLS
from app.core.logging import get_logger

logger = get_logger(__name__)


def analyse_asset(db: Session, symbol: str, limit: int = 100) -> dict:
    """Run full technical analysis for a single asset."""
    prices = get_price_history(db, symbol=symbol, limit=limit)

    if not prices:
        return {"symbol": symbol, "error": "no_price_data"}

    indicators = compute_all(prices)
    breakout   = detect_breakout(prices)
    trend      = detect_trend(prices)

    return {
        "symbol": symbol,
        "indicators": indicators,
        "breakout": breakout,
        "trend": trend,
    }


def analyse_all(db: Session) -> dict[str, dict]:
    """Run technical analysis for every tracked asset."""
    results = {}
    for symbol in TRACKED_SYMBOLS:
        try:
            results[symbol] = analyse_asset(db, symbol)
        except Exception as e:
            logger.error(f"Analysis failed for {symbol}: {e}")
            results[symbol] = {"symbol": symbol, "error": str(e)}
    return results
