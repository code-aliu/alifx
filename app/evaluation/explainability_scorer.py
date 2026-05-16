"""
Rule-based explainability scoring for signal reasoning chains.

Four dimensions (each 0–100):

  coherence         — reasoning steps are quantitative, non-contradictory,
                      and direction-consistent with confidence
  actionability     — concrete trade levels (entry, SL, TP) and time horizon provided
  conciseness       — 3–5 steps is optimal; too few or too many is penalised
  financial_meaning — contains market-relevant quantitative context
                      (RSI, %, EMA, MACD, ATR, regime, event catalyst)

composite = mean of the four dimensions
"""
from __future__ import annotations
import re
import statistics
from sqlalchemy.orm import Session

from app.signals.models import TradingSignal
from app.core.logging import get_logger

logger = get_logger(__name__)

_NUM_RE  = re.compile(r'\d+\.?\d*')
_PCT_RE  = re.compile(r'\d+\.?\d*%')
_CONTRADICTION_PAIRS = [
    ("bullish", "bearish"),
    ("uptrend", "downtrend"),
]
_TA_KEYWORDS = ("rsi", "ema", "macd", "atr", "bollinger", "vwap")
_EVENT_KEYWORDS = ("event", "news", "catalyst", "headline", "impact", "macro")


def score_signal_explanation(signal: TradingSignal) -> dict:
    reasoning = signal.reasoning or []
    text = " ".join(reasoning).lower()

    coherence    = _coherence(signal, text, reasoning)
    actionable   = _actionability(signal)
    conciseness  = _conciseness(reasoning)
    fin_meaning  = _financial_meaning(text)
    composite    = round(statistics.mean([coherence, actionable, conciseness, fin_meaning]))

    return {
        "signal_id":       signal.id,
        "asset":           signal.asset,
        "coherence":       coherence,
        "actionability":   actionable,
        "conciseness":     conciseness,
        "financial_meaning": fin_meaning,
        "composite":       composite,
        "reasoning_steps": len(reasoning),
    }


def compute_explainability_summary(db: Session, limit: int = 200) -> dict:
    signals = (
        db.query(TradingSignal)
        .order_by(TradingSignal.generated_at.desc())
        .limit(limit)
        .all()
    )
    if not signals:
        return _empty_summary()

    scores = [score_signal_explanation(s) for s in signals]

    def avg(key: str) -> float:
        vals = [s[key] for s in scores]
        return round(statistics.mean(vals), 1) if vals else 0.0

    # Per-asset breakdown
    by_asset: dict[str, list[int]] = {}
    for s in scores:
        by_asset.setdefault(s["asset"], []).append(s["composite"])

    asset_avgs = {a: round(statistics.mean(v), 1) for a, v in by_asset.items()}
    ranked = sorted(asset_avgs.items(), key=lambda x: x[1], reverse=True)

    return {
        "avg_coherence":       avg("coherence"),
        "avg_actionability":   avg("actionability"),
        "avg_conciseness":     avg("conciseness"),
        "avg_financial_meaning": avg("financial_meaning"),
        "avg_composite":       avg("composite"),
        "signals_evaluated":   len(scores),
        "top_assets":    [{"asset": a, "score": s} for a, s in ranked[:3]],
        "weakest_assets":[{"asset": a, "score": s} for a, s in ranked[-3:][::-1]],
        "score_distribution":  _distribution(scores),
    }


# ── Scoring helpers ───────────────────────────────────────────────────────────

def _coherence(signal: TradingSignal, text: str, reasoning: list[str]) -> int:
    score = 50
    for w1, w2 in _CONTRADICTION_PAIRS:
        if w1 in text and w2 in text:
            score -= 15
    if _NUM_RE.search(text):
        score += 15
    if "regime" in text:
        score += 10
    if signal.signal in ("BUY", "SELL") and ("bullish" in text or "bearish" in text):
        score += 10
    # Direction ↔ confidence alignment
    if signal.signal == "HOLD" and 38 <= signal.confidence <= 62:
        score += 10
    elif signal.signal in ("BUY", "SELL") and signal.confidence >= 60:
        score += 10
    # Layer diversity: reward reasoning that covers event + TA + regime
    layers = sum([
        any(w in text for w in _EVENT_KEYWORDS),
        any(w in text for w in _TA_KEYWORDS),
        "regime" in text,
    ])
    score += layers * 5
    return max(0, min(100, score))


def _actionability(signal: TradingSignal) -> int:
    score = 10
    if signal.entry_price:  score += 25
    if signal.stop_loss:    score += 25
    if signal.take_profit:  score += 25
    if signal.time_horizon: score += 15
    return min(100, score)


def _conciseness(reasoning: list[str]) -> int:
    n = len(reasoning)
    if n == 0:    return 0
    if 3 <= n <= 5: return 100
    if n in (2, 6): return 75
    if n in (1, 7): return 55
    return 35


def _financial_meaning(text: str) -> int:
    score = 0
    if any(kw in text for kw in _TA_KEYWORDS):     score += 25
    if _PCT_RE.search(text):                         score += 25
    if "regime" in text:                             score += 25
    if any(kw in text for kw in _EVENT_KEYWORDS):   score += 25
    return min(100, score)


def _distribution(scores: list[dict]) -> dict[str, int]:
    dist = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
    for s in scores:
        c = s["composite"]
        if c >= 80:   dist["excellent"] += 1
        elif c >= 65: dist["good"]      += 1
        elif c >= 50: dist["fair"]      += 1
        else:         dist["poor"]      += 1
    return dist


def _empty_summary() -> dict:
    return {
        "avg_coherence":         0.0,
        "avg_actionability":     0.0,
        "avg_conciseness":       0.0,
        "avg_financial_meaning": 0.0,
        "avg_composite":         0.0,
        "signals_evaluated":     0,
        "top_assets":            [],
        "weakest_assets":        [],
        "score_distribution":    {"excellent": 0, "good": 0, "fair": 0, "poor": 0},
    }
