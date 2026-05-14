import pandas as pd
import numpy as np
from app.core.logging import get_logger

logger = get_logger(__name__)


def compute_atr(prices: list[dict], period: int = 14) -> dict:
    """Average True Range — measures market volatility in price terms."""
    if len(prices) < period + 1:
        return {"available": False, "reason": f"need {period + 1} bars"}

    df = pd.DataFrame(prices).sort_values("fetched_at")
    df["high"]  = df["high"].astype(float)
    df["low"]   = df["low"].astype(float)
    df["close"] = df["close"].astype(float)

    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"]  - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = float(tr.ewm(com=period - 1, min_periods=period).mean().iloc[-1])
    close = float(df["close"].iloc[-1])
    atr_pct = round(atr / close * 100, 4) if close else 0

    return {"available": True, "value": round(atr, 6), "pct": atr_pct}


def score_risk(volatility_level: str, atr: dict, confidence: float) -> dict:
    """Produce an overall risk score (1–10) and confidence adjustment.

    Higher risk score = riskier trade.
    Returns confidence_adjustment (negative means penalty).
    """
    # Base risk from volatility level
    base_risk = {"low": 2, "medium": 5, "high": 8}.get(volatility_level, 5)

    # ATR penalty — if ATR % is very high, increase risk score
    atr_penalty = 0
    if atr.get("available"):
        atr_pct = atr["atr_pct"] if "atr_pct" in atr else atr.get("pct", 0)
        if atr_pct > 5:
            atr_penalty = 2
        elif atr_pct > 2:
            atr_penalty = 1

    risk_score = min(10, base_risk + atr_penalty)

    # Confidence adjustment — high risk reduces confidence
    if risk_score >= 8:
        confidence_adjustment = -10
        risk_label = "high"
    elif risk_score >= 5:
        confidence_adjustment = -4
        risk_label = "medium"
    else:
        confidence_adjustment = 0
        risk_label = "low"

    return {
        "risk_score": risk_score,
        "risk_level": risk_label,
        "confidence_adjustment": confidence_adjustment,
    }


def detect_market_regime(prices: list[dict], window: int = 20) -> dict:
    """Detect whether the market is trending or ranging using ADX-like logic."""
    if len(prices) < window:
        return {"available": False, "regime": "unknown"}

    df = pd.DataFrame(prices).sort_values("fetched_at")
    df["close"] = df["close"].astype(float)

    recent = df["close"].tail(window)
    rolling_std = recent.std()
    rolling_mean = recent.mean()
    coefficient_of_variation = float(rolling_std / rolling_mean) if rolling_mean else 0

    # High CV = trending/volatile, low CV = ranging/sideways
    if coefficient_of_variation > 0.03:
        regime = "trending"
    elif coefficient_of_variation > 0.01:
        regime = "volatile"
    else:
        regime = "ranging"

    return {
        "available": True,
        "regime": regime,
        "cv": round(coefficient_of_variation, 6),
    }
