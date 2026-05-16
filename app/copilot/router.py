"""
Intent router — deterministic, keyword-based.

Classifies incoming questions into one of seven intents and optionally
extracts an asset name. No LLM used here: this layer must be fast and
predictable so the retriever always pulls the right context.
"""
from __future__ import annotations
import re

# ── Intent keyword maps ────────────────────────────────────────────────────────

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "performance": [
        "win rate", "accuracy", "success rate", "failed", "loss", "drawdown",
        "sharpe", "best performing", "worst performing", "track record",
        "how accurate", "how well", "historical performance",
    ],
    "portfolio": [
        "portfolio", "positions", "exposure", "concentration", "hedge",
        "open trade", "my trade", "risk in portfolio", "portfolio risk",
        "conflicting", "correlated position",
    ],
    "event": [
        "macro event", "news event", "cpi", "fed", "fomc", "inflation",
        "interest rate", "rate cut", "rate hike", "earnings", "geopolitical",
        "announcement", "what happened", "macro driver", "major event",
    ],
    "regime": [
        "regime", "risk-on", "risk-off", "market condition", "macro environment",
        "market climate", "overall market", "market state",
    ],
    "signal": [
        "signal", "why is", "why did", "bullish", "bearish", "buy signal",
        "sell signal", "should i buy", "should i sell", "why bearish", "why bullish",
        "last signal", "signal fail",
    ],
    "narrative": [
        "summary", "overview", "what's happening", "what is happening",
        "market today", "daily brief", "what do you see", "tell me about",
        "market update", "volatility", "strongest", "weakest",
    ],
    "asset": [
        # asset names by themselves indicate an asset-centric query
        "btc", "bitcoin", "spy", "eurusd", "eur/usd", "gold", "xauusd",
        "eth", "ethereum", "nasdaq", "qqq",
    ],
}

# Asset name → tracked symbol
_ASSET_MAP: dict[str, str] = {
    "btc":      "BTC",
    "bitcoin":  "BTC",
    "eth":      "ETH",
    "ethereum": "ETH",
    "spy":      "SPY",
    "s&p":      "SPY",
    "s&p 500":  "SPY",
    "sp500":    "SPY",
    "eurusd":   "EURUSD",
    "eur/usd":  "EURUSD",
    "euro":     "EURUSD",
    "gold":     "XAUUSD",
    "xauusd":   "XAUUSD",
    "qqq":      "QQQ",
    "nasdaq":   "QQQ",
}

# Intent priority order (first match wins when multiple intents hit)
_PRIORITY = ["performance", "portfolio", "event", "regime", "signal", "narrative", "asset"]


# ── Public API ────────────────────────────────────────────────────────────────

def classify(question: str) -> dict:
    """Return {intent, asset} for a natural-language question.

    Intent is always set (defaults to "narrative" if nothing matches).
    Asset is None unless a known symbol is mentioned.
    """
    lower = question.lower()

    detected_intent = _detect_intent(lower)
    detected_asset  = _detect_asset(lower)

    # If the question mentions a specific asset but maps to a generic intent,
    # promote to "signal" (most useful context for asset-specific queries)
    if detected_asset and detected_intent in ("narrative", "asset"):
        detected_intent = "signal"

    return {
        "intent": detected_intent,
        "asset":  detected_asset,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _detect_intent(lower: str) -> str:
    for intent in _PRIORITY:
        keywords = _INTENT_KEYWORDS[intent]
        if any(kw in lower for kw in keywords):
            return intent
    return "narrative"


def _detect_asset(lower: str) -> str | None:
    # Longest match first to avoid "eth" matching inside "ethereum"
    for phrase in sorted(_ASSET_MAP.keys(), key=len, reverse=True):
        # Word-boundary match so "spy" doesn't fire inside "spotify"
        if re.search(rf"\b{re.escape(phrase)}\b", lower):
            return _ASSET_MAP[phrase]
    return None
