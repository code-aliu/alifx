"""
Market regime detection — pure functions, no I/O.

Four independent signals feed into a weighted classifier:
  1. Volatility regime   — ATR% and price std dev
  2. Price trend regime  — coefficient of variation (trending vs ranging)
  3. Event flow regime   — aggregate macro/event impact direction
  4. Cross-asset regime  — consensus across BTC, SPY, EURUSD (risk appetite proxy)

Output: one primary regime from {risk_on, risk_off, trending, ranging,
        high_volatility, low_volatility} plus any secondary regimes.
"""

from collections import defaultdict
from datetime import datetime

import pandas as pd
import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)

# Bellwether assets — used for cross-asset consensus check.
# BTC  → crypto / global risk appetite
# SPY  → US equity risk appetite
# EURUSD → USD strength (weak USD = risk-on globally)
BELLWETHER_ASSETS = ["BTC", "SPY", "EURUSD"]

# Scoring weights for the classifier
_W_VOLATILITY    = 3.0
_W_PRICE_TREND   = 2.0
_W_EVENT_FLOW    = 2.5
_W_CROSS_ASSET   = 1.5

# Flat confidence adjustments applied to signal confidence_score
REGIME_SIGNAL_DELTA: dict[str, float] = {
    "risk_on":         +5.0,
    "risk_off":        -8.0,
    "trending":        +3.0,
    "ranging":         -6.0,
    "high_volatility": -5.0,
    "low_volatility":  +3.0,
}


# ── 1. Volatility regime ─────────────────────────────────────────────────────

def detect_volatility_regime(prices: list[dict]) -> dict:
    """Classify volatility as high, low, or neutral from ATR% and std dev.

    Returns confidence in [0, 1].
    """
    if len(prices) < 15:
        return {"regime": "neutral", "confidence": 0.0, "available": False,
                "reason": f"need 15 bars, have {len(prices)}"}

    df = pd.DataFrame(prices).sort_values("fetched_at")
    df["close"] = df["close"].astype(float)
    df["high"]  = df["high"].astype(float)
    df["low"]   = df["low"].astype(float)

    # ATR (14-period)
    prev = df["close"].shift(1)
    tr   = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev).abs(),
        (df["low"]  - prev).abs(),
    ], axis=1).max(axis=1)
    atr     = float(tr.ewm(com=13, min_periods=14).mean().iloc[-1])
    close   = float(df["close"].iloc[-1])
    atr_pct = (atr / close * 100) if close else 0

    # 10-bar rolling std dev %
    returns      = df["close"].pct_change().dropna()
    vol_std      = float(returns.tail(10).std() * 100)

    if atr_pct > 3.0 or vol_std > 3.0:
        regime     = "high_volatility"
        confidence = min(1.0, max(atr_pct / 6.0, vol_std / 6.0))
    elif atr_pct < 0.6 and vol_std < 0.6:
        regime     = "low_volatility"
        confidence = min(1.0, 1.0 - max(atr_pct, vol_std) / 0.6)
    else:
        regime     = "neutral"
        confidence = 0.3

    return {
        "regime":     regime,
        "confidence": round(confidence, 3),
        "atr_pct":    round(atr_pct, 4),
        "vol_std":    round(vol_std, 4),
        "available":  True,
    }


# ── 2. Price trend regime ────────────────────────────────────────────────────

def detect_price_trend_regime(prices: list[dict], window: int = 20) -> dict:
    """Classify market structure as trending or ranging using coefficient of variation."""
    if len(prices) < window:
        return {"regime": "neutral", "confidence": 0.0, "available": False,
                "reason": f"need {window} bars, have {len(prices)}"}

    df    = pd.DataFrame(prices).sort_values("fetched_at")
    df["close"] = df["close"].astype(float)
    recent = df["close"].tail(window)
    mean   = float(recent.mean())
    cv     = float(recent.std() / mean) if mean else 0

    if cv > 0.03:
        regime     = "trending"
        confidence = min(1.0, cv / 0.06)
    elif cv > 0.008:
        regime     = "trending"
        confidence = min(0.5, cv / 0.03)
    else:
        regime     = "ranging"
        confidence = min(1.0, 1.0 - cv / 0.008)

    # Detect the trend direction (for reasoning)
    short_ma = float(df["close"].tail(5).mean())
    long_ma  = float(df["close"].tail(window).mean())
    direction = "uptrend" if short_ma > long_ma * 1.005 else (
                "downtrend" if short_ma < long_ma * 0.995 else "sideways")

    return {
        "regime":     regime,
        "confidence": round(confidence, 3),
        "cv":         round(cv, 6),
        "direction":  direction,
        "available":  True,
    }


# ── 3. Event flow regime ─────────────────────────────────────────────────────

def detect_event_regime(impact_summary: dict[str, dict]) -> dict:
    """Classify market mood from the aggregate event/macro impact scores.

    Uses the full tracked-asset impact summary (all symbols).
    """
    if not impact_summary:
        return {"regime": "neutral", "confidence": 0.0, "available": False}

    scores    = [v["score"] for v in impact_summary.values()]
    avg_score = sum(scores) / len(scores)
    bullish   = sum(1 for s in scores if s > 0)
    bearish   = sum(1 for s in scores if s < 0)
    total     = len(scores)

    if avg_score >= 1.0 and bullish >= total * 0.5:
        regime     = "risk_on"
        confidence = min(1.0, avg_score / 4.0)
    elif avg_score <= -1.0 and bearish >= total * 0.5:
        regime     = "risk_off"
        confidence = min(1.0, abs(avg_score) / 4.0)
    else:
        regime     = "neutral"
        confidence = max(0.0, 1.0 - abs(avg_score))

    return {
        "regime":     regime,
        "confidence": round(confidence, 3),
        "avg_score":  round(avg_score, 3),
        "bullish_count": bullish,
        "bearish_count": bearish,
        "available":  True,
    }


# ── 4. Cross-asset regime ────────────────────────────────────────────────────

def detect_cross_asset_regime(impact_summary: dict[str, dict]) -> dict:
    """Check whether bellwether assets (BTC, SPY, EURUSD) agree on risk direction.

    Majority agreement → risk_on / risk_off. Divergence → mixed.
    """
    directions = {}
    for asset in BELLWETHER_ASSETS:
        data = impact_summary.get(asset)
        if data:
            directions[asset] = data["direction"]

    if not directions:
        return {"regime": "mixed", "confidence": 0.0, "available": False,
                "directions": {}}

    bullish = sum(1 for d in directions.values() if d == "bullish")
    bearish = sum(1 for d in directions.values() if d == "bearish")
    n       = len(directions)

    if bullish >= max(2, n * 0.6):
        regime     = "risk_on"
        confidence = round(bullish / n, 3)
    elif bearish >= max(2, n * 0.6):
        regime     = "risk_off"
        confidence = round(bearish / n, 3)
    else:
        regime     = "mixed"
        confidence = 0.3

    return {
        "regime":     regime,
        "confidence": confidence,
        "directions": directions,
        "bullish":    bullish,
        "bearish":    bearish,
        "available":  True,
    }


# ── 5. Classifier ────────────────────────────────────────────────────────────

def classify_regime(
    vol:         dict,
    price_trend: dict,
    event:       dict,
    cross_asset: dict,
) -> dict:
    """Combine the four signals into a single primary regime + secondaries.

    Each signal votes for candidate regimes with weighted confidence scores.
    The highest total score wins as primary regime.
    """
    scores: dict[str, float] = defaultdict(float)
    reasoning: list[str] = []

    # Volatility vote
    if vol.get("available"):
        vr = vol["regime"]
        vc = vol["confidence"]
        if vr in ("high_volatility", "low_volatility"):
            scores[vr] += vc * _W_VOLATILITY
            label = "elevated" if vr == "high_volatility" else "suppressed"
            reasoning.append(
                f"Volatility {label}: ATR {vol.get('atr_pct', 0):.2f}%, "
                f"std {vol.get('vol_std', 0):.2f}%"
            )

    # Price trend vote
    if price_trend.get("available"):
        pr = price_trend["regime"]
        pc = price_trend["confidence"]
        if pr in ("trending", "ranging"):
            scores[pr] += pc * _W_PRICE_TREND
            direction = price_trend.get("direction", "")
            reasoning.append(
                f"Price structure: {pr} ({direction}), CV={price_trend.get('cv', 0):.4f}"
            )

    # Event flow vote
    if event.get("available") and event["regime"] != "neutral":
        er = event["regime"]
        ec = event["confidence"]
        scores[er] += ec * _W_EVENT_FLOW
        reasoning.append(
            f"Event flow: {er} — avg impact score {event.get('avg_score', 0):+.2f} "
            f"({event.get('bullish_count', 0)} bullish, {event.get('bearish_count', 0)} bearish assets)"
        )

    # Cross-asset vote
    if cross_asset.get("available") and cross_asset["regime"] != "mixed":
        cr = cross_asset["regime"]
        cc = cross_asset["confidence"]
        scores[cr] += cc * _W_CROSS_ASSET
        dirs = cross_asset.get("directions", {})
        dir_str = ", ".join(f"{k}={v}" for k, v in dirs.items())
        reasoning.append(f"Cross-asset consensus: {cr} ({dir_str})")

    if not scores:
        primary    = "ranging"
        confidence = 0.2
        reasoning.append("Insufficient data — defaulting to ranging regime")
    else:
        primary    = max(scores, key=scores.get)
        top_score  = scores[primary]
        total      = sum(scores.values()) or 1.0
        confidence = round(min(1.0, top_score / total), 3)

    secondary = [r for r, s in scores.items() if r != primary and s > 0]

    return {
        "primary_regime":    primary,
        "secondary_regimes": secondary,
        "confidence":        confidence,
        "reasoning":         reasoning,
        "components": {
            "volatility":   vol,
            "price_trend":  price_trend,
            "event_flow":   event,
            "cross_asset":  cross_asset,
        },
        "signal_delta": REGIME_SIGNAL_DELTA.get(primary, 0.0),
        "computed_at":  datetime.utcnow().isoformat(),
    }


# ── Public entry point ───────────────────────────────────────────────────────

def detect_regime(
    prices: list[dict],
    impact_summary: dict[str, dict],
) -> dict:
    """Full regime detection from price bars + impact summary."""
    vol         = detect_volatility_regime(prices)
    price_trend = detect_price_trend_regime(prices)
    event       = detect_event_regime(impact_summary)
    cross_asset = detect_cross_asset_regime(impact_summary)
    return classify_regime(vol, price_trend, event, cross_asset)
