"""
Asset volatility analysis.

Computes ATR-based volatility context for one or multiple assets:
  - Current ATR and ATR %
  - Volatility tier: low / normal / elevated / extreme
  - Historical percentile (how high is current vol vs recent history?)
  - Implications for position sizing
  - Regime context

Used by /volatility-analysis and the position sizing calculator.
"""
from __future__ import annotations
import statistics
from sqlalchemy.orm import Session

from app.risk.scorer         import compute_atr
from app.market_data.service import get_price_history
from app.impact.rules        import TRACKED_SYMBOLS
from app.core.logging        import get_logger

logger = get_logger(__name__)


def _vol_tier(atr_pct: float) -> tuple[str, str]:
    if atr_pct > 5.0:
        return "extreme", "Extreme volatility — position sizes should be significantly reduced"
    if atr_pct > 2.0:
        return "elevated", "Elevated volatility — position sizes should be reduced"
    if atr_pct > 0.5:
        return "normal", "Normal volatility — standard position sizing applies"
    return "low", "Low volatility — potentially tight ranges; watch for breakout risk"


def analyze_asset_volatility(db: Session, symbol: str) -> dict:
    """Full volatility analysis for a single asset."""
    prices = get_price_history(db, symbol=symbol, limit=60)

    if len(prices) < 15:
        return {
            "symbol":    symbol,
            "available": False,
            "reason":    f"Insufficient price history ({len(prices)} bars)",
        }

    atr = compute_atr(prices, period=14)
    if not atr.get("available"):
        return {"symbol": symbol, "available": False, "reason": "ATR computation failed"}

    atr_pct  = atr["pct"]
    tier, tier_msg = _vol_tier(atr_pct)

    # Historical percentile: compare ATR% to rolling window of daily ATR%s
    percentile = _vol_percentile(prices, current_atr_pct=atr_pct)

    return {
        "symbol":       symbol,
        "available":    True,
        "atr_value":    atr["value"],
        "atr_pct":      atr_pct,
        "tier":         tier,
        "tier_message": tier_msg,
        "percentile":   percentile,
        "size_multiplier": _atr_multiplier(atr_pct),
        "education": {
            "atr_explanation": (
                f"The Average True Range (ATR) for {symbol} is currently {atr_pct:.2f}% of price. "
                "ATR measures the average daily price range — a higher ATR means the asset "
                "moves more in a typical day, requiring a wider stop-loss to avoid noise."
            ),
            "tier_context": tier_msg,
            "percentile_context": (
                f"Current volatility is in the {percentile}th percentile of recent history "
                "— meaning volatility is " +
                ("above average" if percentile > 60 else "below average" if percentile < 40 else "near average")
                + " compared to recent periods."
            ) if percentile is not None else None,
        },
    }


def analyze_portfolio_volatility(db: Session) -> dict:
    """Volatility analysis across all tracked assets."""
    results: dict[str, dict] = {}
    for symbol in TRACKED_SYMBOLS:
        try:
            results[symbol] = analyze_asset_volatility(db, symbol)
        except Exception as e:
            results[symbol] = {"symbol": symbol, "available": False, "reason": str(e)}

    available = {s: d for s, d in results.items() if d.get("available")}

    if not available:
        return {"assets": results, "summary": None}

    tiers: dict[str, list[str]] = {"extreme": [], "elevated": [], "normal": [], "low": []}
    for sym, d in available.items():
        tiers[d["tier"]].append(sym)

    avg_atr_pct = statistics.mean(d["atr_pct"] for d in available.values())

    return {
        "assets":  results,
        "summary": {
            "avg_atr_pct":       round(avg_atr_pct, 3),
            "overall_tier":      _vol_tier(avg_atr_pct)[0],
            "by_tier":           {k: v for k, v in tiers.items() if v},
            "high_vol_assets":   tiers["extreme"] + tiers["elevated"],
            "market_assessment": _market_vol_assessment(avg_atr_pct, tiers),
        },
    }


def _vol_percentile(prices: list[dict], current_atr_pct: float, lookback: int = 30) -> int | None:
    """
    Estimate the percentile of current ATR% vs a rolling window of ATR%s.
    Simplified: uses daily range % as a volatility proxy for the history.
    """
    try:
        recent = sorted(prices, key=lambda p: p.get("fetched_at", ""))[-lookback:]
        if len(recent) < 10:
            return None
        daily_ranges = []
        for p in recent:
            try:
                high  = float(p.get("high", 0) or 0)
                low   = float(p.get("low", 0) or 0)
                close = float(p.get("close", 1) or 1)
                if high > 0 and low > 0 and close > 0:
                    daily_ranges.append((high - low) / close * 100)
            except (TypeError, ZeroDivisionError):
                continue
        if len(daily_ranges) < 5:
            return None
        below = sum(1 for r in daily_ranges if r < current_atr_pct)
        return round(below / len(daily_ranges) * 100)
    except Exception:
        return None


def _atr_multiplier(atr_pct: float) -> float:
    if atr_pct > 5.0:   return 0.60
    if atr_pct > 2.0:   return 0.80
    return 1.0


def _market_vol_assessment(avg_atr_pct: float, tiers: dict) -> str:
    extreme_count  = len(tiers.get("extreme", []))
    elevated_count = len(tiers.get("elevated", []))

    if extreme_count >= 3:
        return "Market in extreme volatility — significantly reduce position sizes across the board"
    if extreme_count >= 1 or elevated_count >= 3:
        return "Elevated market volatility — reduce position sizes and widen stop-loss buffers"
    if elevated_count >= 1:
        return "Some assets showing elevated volatility — apply asset-specific size reductions"
    return "Overall market volatility is within normal range — standard sizing applies"
