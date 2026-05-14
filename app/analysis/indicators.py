import pandas as pd
import numpy as np
from app.core.logging import get_logger

logger = get_logger(__name__)

MIN_BARS_RSI  = 15
MIN_BARS_EMA  = 21    # need at least 20+1 for EMA-20
MIN_BARS_EMA50  = 51
MIN_BARS_EMA200 = 201
MIN_BARS_MACD = 35


def compute_all(prices: list[dict]) -> dict:
    """Compute all indicators. Skips gracefully when insufficient bars."""
    if len(prices) < 3:
        return {"error": "insufficient_data", "bars_available": len(prices)}

    df = _to_dataframe(prices)
    result = {
        "bars_available": len(df),
        "latest_close":   float(df["close"].iloc[-1]),
        "rsi":            _compute_rsi(df),
        "ema":            _compute_ema_multi(df),
        "macd":           _compute_macd(df),
        "volatility":     _compute_volatility(df),
    }
    return result


def compute_flat(prices: list[dict]) -> dict:
    """Return a flat, human-readable indicator summary matching the spec output format.

    Example:
      {"asset": "BTC", "trend": "bullish", "rsi": 63,
       "ema_20": 103200, "ema_50": 101500, "macd_signal": "bullish"}
    """
    if len(prices) < 3:
        return {"error": "insufficient_data", "bars_available": len(prices)}

    df   = _to_dataframe(prices)
    rsi  = _compute_rsi(df)
    ema  = _compute_ema_multi(df)
    macd = _compute_macd(df)
    vol  = _compute_volatility(df)

    from app.analysis.patterns import detect_trend
    trend_data = detect_trend(prices)

    return {
        "latest_close":  round(float(df["close"].iloc[-1]), 6),
        "trend":         trend_data.get("trend", "unknown") if trend_data.get("available") else "unknown",
        "rsi":           rsi.get("value") if rsi.get("available") else None,
        "rsi_signal":    rsi.get("signal") if rsi.get("available") else None,
        "ema_20":        ema.get("ema_20") if ema.get("available") else None,
        "ema_50":        ema.get("ema_50") if ema.get("ema_50_available") else None,
        "ema_200":       ema.get("ema_200") if ema.get("ema_200_available") else None,
        "ema_signal":    ema.get("signal") if ema.get("available") else None,
        "macd_signal":   macd.get("trend") if macd.get("available") else None,
        "macd_histogram": macd.get("histogram") if macd.get("available") else None,
        "volatility":    vol.get("level") if vol.get("available") else None,
        "bars_used":     len(df),
    }


def _to_dataframe(prices: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(prices)
    df["close"] = df["close"].astype(float)
    df["high"]  = df["high"].astype(float)
    df["low"]   = df["low"].astype(float)
    df["open"]  = df["open"].astype(float)
    df = df.sort_values("fetched_at").reset_index(drop=True)
    return df


def _compute_rsi(df: pd.DataFrame, period: int = 14) -> dict:
    if len(df) < MIN_BARS_RSI:
        return {"available": False, "reason": f"need {MIN_BARS_RSI} bars, have {len(df)}"}

    delta    = df["close"].diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    rsi      = (100 - (100 / (1 + rs))).iloc[-1]

    value = round(float(rsi), 2)
    if value >= 70:
        signal = "overbought"
    elif value <= 30:
        signal = "oversold"
    else:
        signal = "neutral"

    return {"available": True, "value": value, "signal": signal}


def _compute_ema_multi(df: pd.DataFrame) -> dict:
    """Compute EMA-20, EMA-50, EMA-200 as required by spec."""
    if len(df) < MIN_BARS_EMA:
        return {"available": False, "reason": f"need {MIN_BARS_EMA} bars, have {len(df)}"}

    close   = df["close"]
    ema_20  = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    result  = {
        "available":       True,
        "ema_20":          round(ema_20, 6),
        "ema_50_available":  False,
        "ema_200_available": False,
    }

    if len(df) >= MIN_BARS_EMA50:
        ema_50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
        result["ema_50"]          = round(ema_50, 6)
        result["ema_50_available"] = True

    if len(df) >= MIN_BARS_EMA200:
        ema_200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
        result["ema_200"]          = round(ema_200, 6)
        result["ema_200_available"] = True

    # Signal based on EMA-20 vs EMA-50 when available, else EMA-20 vs price
    current_price = float(df["close"].iloc[-1])
    if result.get("ema_50_available"):
        ema_50_val = result["ema_50"]
        prev_ema_20 = float(close.ewm(span=20, adjust=False).mean().iloc[-2])
        prev_ema_50 = float(close.ewm(span=50, adjust=False).mean().iloc[-2])
        if prev_ema_20 <= prev_ema_50 and ema_20 > ema_50_val:
            signal = "golden_cross"
        elif prev_ema_20 >= prev_ema_50 and ema_20 < ema_50_val:
            signal = "death_cross"
        elif ema_20 > ema_50_val:
            signal = "bullish"
        else:
            signal = "bearish"
    else:
        signal = "bullish" if current_price > ema_20 else "bearish"

    result["signal"] = signal
    return result


def _compute_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal_period: int = 9) -> dict:
    if len(df) < MIN_BARS_MACD:
        return {"available": False, "reason": f"need {MIN_BARS_MACD} bars, have {len(df)}"}

    ema_fast    = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow    = df["close"].ewm(span=slow, adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram   = macd_line - signal_line

    macd_val   = float(macd_line.iloc[-1])
    signal_val = float(signal_line.iloc[-1])
    hist_val   = float(histogram.iloc[-1])
    prev_hist  = float(histogram.iloc[-2])

    if hist_val > 0 and prev_hist <= 0:
        trend = "bullish_crossover"
    elif hist_val < 0 and prev_hist >= 0:
        trend = "bearish_crossover"
    elif hist_val > 0:
        trend = "bullish"
    else:
        trend = "bearish"

    return {
        "available": True,
        "macd":      round(macd_val, 6),
        "signal":    round(signal_val, 6),
        "histogram": round(hist_val, 6),
        "trend":     trend,
    }


def _compute_volatility(df: pd.DataFrame, window: int = 10) -> dict:
    if len(df) < window:
        window = len(df)

    returns = df["close"].pct_change().dropna()
    recent  = returns.tail(window)
    vol     = float(recent.std() * 100)

    if vol > 3.0:
        level = "high"
    elif vol > 1.0:
        level = "medium"
    else:
        level = "low"

    return {"available": True, "value": round(vol, 4), "level": level}
