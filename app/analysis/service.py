from datetime import datetime
import numpy as np
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


def compute_correlations(db: Session, limit: int = 60) -> dict:
    """What assets are correlated?

    Computes Pearson correlation of log returns across all tracked assets.
    Returns the full correlation matrix and the top pairs ranked by |r|.
    """
    returns: dict[str, list[float]] = {}
    for symbol in TRACKED_SYMBOLS:
        prices = get_price_history(db, symbol=symbol, limit=limit)
        if len(prices) >= 2:
            closes = [p["close"] for p in prices]
            rets = [np.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
            returns[symbol] = rets

    symbols  = list(returns.keys())
    min_len  = min((len(v) for v in returns.values()), default=0)
    aligned  = {s: returns[s][-min_len:] for s in symbols} if min_len >= 5 else {}

    matrix: dict[str, dict[str, float | None]] = {s: {s: 1.0} for s in symbols}
    pairs: list[dict] = []

    for i, s1 in enumerate(symbols):
        for j in range(i + 1, len(symbols)):
            s2 = symbols[j]
            if min_len < 5:
                corr = None
            else:
                r1   = np.array(aligned[s1])
                r2   = np.array(aligned[s2])
                corr = round(float(np.corrcoef(r1, r2)[0, 1]), 4)

            matrix[s1][s2] = corr
            matrix[s2][s1] = corr
            if corr is not None:
                pairs.append({
                    "asset_a":      s1,
                    "asset_b":      s2,
                    "correlation":  corr,
                    "relationship": _correlation_label(corr),
                })

    pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

    return {
        "computed_at":   datetime.utcnow().isoformat(),
        "lookback_bars": min_len,
        "assets":        symbols,
        "matrix":        matrix,
        "top_pairs":     pairs[:10],
    }


def _correlation_label(corr: float) -> str:
    if corr >= 0.7:
        return "strongly_positive"
    elif corr >= 0.3:
        return "moderately_positive"
    elif corr >= -0.3:
        return "uncorrelated"
    elif corr >= -0.7:
        return "moderately_negative"
    return "strongly_negative"
