import pandas as pd


def detect_breakout(prices: list[dict], lookback: int = 20) -> dict:
    """Detect if price is breaking out above resistance or below support."""
    if len(prices) < lookback + 1:
        return {"available": False, "reason": f"need {lookback + 1} bars"}

    df = pd.DataFrame(prices).sort_values("fetched_at")
    df["close"] = df["close"].astype(float)
    df["high"]  = df["high"].astype(float)
    df["low"]   = df["low"].astype(float)

    recent    = df.tail(lookback + 1)
    history   = recent.iloc[:-1]
    current   = recent.iloc[-1]

    resistance = float(history["high"].max())
    support    = float(history["low"].min())
    close      = float(current["close"])

    if close > resistance:
        signal = "breakout_up"
        strength = round((close - resistance) / resistance * 100, 3)
    elif close < support:
        signal = "breakdown"
        strength = round((support - close) / support * 100, 3)
    else:
        signal = "range_bound"
        strength = 0.0

    return {
        "available": True,
        "signal": signal,
        "resistance": round(resistance, 6),
        "support": round(support, 6),
        "current_price": round(close, 6),
        "strength_pct": strength,
    }


def detect_trend(prices: list[dict], short: int = 5, long: int = 15) -> dict:
    """Simple trend detection using short vs long moving average."""
    if len(prices) < long:
        return {"available": False, "reason": f"need {long} bars"}

    df = pd.DataFrame(prices).sort_values("fetched_at")
    df["close"] = df["close"].astype(float)

    short_ma = float(df["close"].tail(short).mean())
    long_ma  = float(df["close"].tail(long).mean())

    if short_ma > long_ma * 1.005:
        trend = "uptrend"
    elif short_ma < long_ma * 0.995:
        trend = "downtrend"
    else:
        trend = "sideways"

    return {
        "available": True,
        "trend": trend,
        "short_ma": round(short_ma, 6),
        "long_ma": round(long_ma, 6),
    }
