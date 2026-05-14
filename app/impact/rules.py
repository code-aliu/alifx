"""
Impact scoring rules.

Maps (sentiment, importance) → numeric impact score per asset.
Positive = bullish pressure, negative = bearish pressure.
"""

IMPORTANCE_WEIGHT = {
    "high":   3,
    "medium": 2,
    "low":    1,
}

SENTIMENT_DIRECTION = {
    "risk_on":  1,
    "risk_off": -1,
    "neutral":  0,
}

# Assets in event rules that map to tracked price symbols
# Event asset codes → canonical price symbol
ASSET_CODE_MAP = {
    "BTC":    "BTC",
    "ETH":    "ETH",
    "SPY":    "SPY",
    "QQQ":    "QQQ",
    "NASDAQ": "QQQ",   # QQQ is the NASDAQ proxy
    "NVDA":   "NVDA",
    "AAPL":   "AAPL",
    "EURUSD": "EURUSD",
    "EUR":    "EURUSD",
    "GBPUSD": "GBPUSD",
    "GBP":    "GBPUSD",
    "USDJPY": "USDJPY",
    "JPY":    "USDJPY",
    # The following are not in our price universe — skip them
    # USD, GOLD, OIL → ignored
}

TRACKED_SYMBOLS = {"BTC", "ETH", "SPY", "QQQ", "NVDA", "AAPL", "EURUSD", "GBPUSD", "USDJPY"}


def compute_impact_score(sentiment: str, importance: str) -> float:
    direction = SENTIMENT_DIRECTION.get(sentiment, 0)
    weight = IMPORTANCE_WEIGHT.get(importance, 1)
    return float(direction * weight)


def resolve_asset_code(code: str) -> str | None:
    """Return the tracked price symbol for an event asset code, or None if not tracked."""
    return ASSET_CODE_MAP.get(code.upper())
