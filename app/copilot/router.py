"""
Intent router — deterministic, keyword-based.

Classifies incoming questions into one of ten intents and optionally
extracts an asset name. No LLM used here: this layer must be fast and
predictable so the retriever always pulls the right context.

Intents:
  performance  — track record, win rate, accuracy
  portfolio    — positions, exposure, concentration
  event        — macro events, CPI, Fed, earnings
  regime       — market conditions, risk-on/off
  signal       — specific asset signals, why bullish/bearish
  narrative    — general summary, market overview
  asset        — asset-centric queries without a specific signal question
  education    — "what is X?", "explain X", "how does X work?"
  guidance     — "why is X happening?", "what affects X?", "should I worry about?"
  macro        — macroeconomic analysis, sector sensitivity, rate impacts
"""
from __future__ import annotations
import re

# ── Intent keyword maps ────────────────────────────────────────────────────────

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "education": [
        "what is", "what are", "explain", "how does", "how do", "define",
        "what does", "mean", "meaning of", "tell me what", "help me understand",
        "i don't understand", "what's a", "what's an",
    ],
    "guidance": [
        "why is", "why are", "why did", "why does", "why do",
        "what's causing", "what caused", "what's driving", "what drives",
        "should i worry", "is it risky", "what should i do", "what happens if",
        "what affects", "what influences", "how does this affect",
        "why are markets", "why is the market",
    ],
    "macro": [
        "macro", "macroeconomic", "economy", "gdp", "recession", "rate hike",
        "rate cut", "interest rate", "central bank", "monetary policy",
        "fiscal policy", "sectors", "sector rotation", "which sectors",
        "sensitive to", "benefit from", "hurt by",
    ],
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
        "earnings", "geopolitical", "announcement", "what happened",
        "macro driver", "major event",
    ],
    "regime": [
        "regime", "risk-on", "risk-off", "market condition", "macro environment",
        "market climate", "overall market", "market state",
    ],
    "signal": [
        "signal", "bullish", "bearish", "buy signal", "sell signal",
        "should i buy", "should i sell", "why bearish", "why bullish",
        "last signal", "signal fail",
    ],
    "narrative": [
        "summary", "overview", "what's happening", "what is happening",
        "market today", "daily brief", "what do you see", "tell me about",
        "market update", "volatility", "strongest", "weakest", "this week",
        "changed in the market",
    ],
    "asset": [
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

# Intent priority (first match wins)
_PRIORITY = [
    "education", "guidance", "macro",
    "performance", "portfolio", "event", "regime",
    "signal", "narrative", "asset",
]


# ── Public API ────────────────────────────────────────────────────────────────

def classify(question: str) -> dict:
    """Return {intent, asset} for a natural-language question."""
    lower = question.lower()

    detected_intent = _detect_intent(lower)
    detected_asset  = _detect_asset(lower)

    # Asset-specific query without a clear intent → promote to signal context
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
    for phrase in sorted(_ASSET_MAP.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(phrase)}\b", lower):
            return _ASSET_MAP[phrase]
    return None
