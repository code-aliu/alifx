"""
Market narrative generation.

Produces structured summaries from DB data:
  - daily_market_summary()   → full daily overview
  - top_signals_report()     → highest confidence signals with explanations
  - portfolio_risk_summary() → risk-focused portfolio narrative
  - signal_explanation()     → deep explanation for a single signal

All functions return dicts with both machine-readable fields and
a human-readable `narrative` string — the narrative is generated
via the copilot generator (LLM or template).
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session

from app.copilot.retriever import retrieve_context
from app.copilot.assembler import assemble
from app.copilot.generator import generate_response
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────

def daily_market_summary(db: Session, api_key: str = "") -> dict:
    """Full daily market overview: regime, signals, events, portfolio, performance."""
    ctx       = retrieve_context(db, intent="narrative")
    assembled = assemble(ctx)
    question  = "Give me a complete daily market summary covering regime, key signals, macro events, and portfolio risks."
    narrative, generated_by = generate_response(question, assembled, "narrative", None, api_key)

    regime        = ctx.get("regime") or {}
    signals       = ctx.get("signals") or []
    events        = ctx.get("events") or []
    portfolio     = ctx.get("portfolio") or {}
    performance   = ctx.get("performance") or {}
    perf_summary  = performance.get("summary", {})

    buy_signals  = [s for s in signals if s.get("signal") == "BUY"]
    sell_signals = [s for s in signals if s.get("signal") == "SELL"]
    hold_signals = [s for s in signals if s.get("signal") == "HOLD"]

    top_signals = sorted(signals, key=lambda s: s.get("confidence", 0), reverse=True)[:3]
    high_events = [e for e in events if e.get("importance") == "high"]

    return {
        "narrative":        narrative,
        "generated_by":     generated_by,
        "regime": {
            "primary":    regime.get("primary_regime", "unknown"),
            "confidence": regime.get("confidence", 0),
            "reasoning":  regime.get("reasoning", [])[:3],
        },
        "signal_consensus": {
            "buy_count":  len(buy_signals),
            "sell_count": len(sell_signals),
            "hold_count": len(hold_signals),
            "consensus":  _consensus(buy_signals, sell_signals, hold_signals),
            "top_signals": top_signals,
        },
        "key_events":       high_events[:3],
        "portfolio_status": {
            "open_positions":       portfolio.get("open_positions", 0),
            "total_open_notional":  portfolio.get("total_open_notional", 0),
            "risk_warnings":        portfolio.get("risk_warnings", []),
        },
        "performance_snapshot": {
            "win_rate_pct":   perf_summary.get("win_rate_pct"),
            "total_resolved": perf_summary.get("total_resolved", 0),
        },
        "generated_at": datetime.utcnow().isoformat(),
    }


def top_signals_report(db: Session, limit: int = 5, api_key: str = "") -> dict:
    """Highest confidence signals with brief reasoning for each."""
    ctx       = retrieve_context(db, intent="narrative")
    signals   = ctx.get("signals") or []
    regime    = ctx.get("regime") or {}

    actionable  = [s for s in signals if s.get("signal") in ("BUY", "SELL")]
    top         = sorted(actionable, key=lambda s: s.get("confidence", 0), reverse=True)[:limit]

    assembled = assemble(ctx)
    question  = f"Summarise the top {limit} highest-confidence trading signals and their key drivers."
    narrative, generated_by = generate_response(question, assembled, "signal", None, api_key)

    return {
        "narrative":    narrative,
        "generated_by": generated_by,
        "signals": [
            {
                "asset":       s.get("asset"),
                "signal":      s.get("signal"),
                "confidence":  s.get("confidence"),
                "time_horizon":s.get("time_horizon"),
                "risk_level":  s.get("risk_level"),
                "top_reasons": (s.get("reasoning") or [])[:3],
                "entry_price": s.get("entry_price"),
                "stop_loss":   s.get("stop_loss"),
                "take_profit": s.get("take_profit"),
            }
            for s in top
        ],
        "current_regime": regime.get("primary_regime", "unknown"),
        "total_signals":  len(signals),
        "actionable":     len(actionable),
        "generated_at":   datetime.utcnow().isoformat(),
    }


def portfolio_risk_summary(db: Session, api_key: str = "") -> dict:
    """Narrative risk report for the current paper trading portfolio."""
    ctx       = retrieve_context(db, intent="portfolio")
    assembled = assemble(ctx)
    question  = "Explain the current portfolio risks, directional exposure, and any warnings in plain language."
    narrative, generated_by = generate_response(question, assembled, "portfolio", None, api_key)

    portfolio   = ctx.get("portfolio") or {}
    performance = ctx.get("performance") or {}
    risk_metrics= performance.get("risk_metrics", {})

    return {
        "narrative":    narrative,
        "generated_by": generated_by,
        "open_positions":          portfolio.get("open_positions", 0),
        "total_open_notional":     portfolio.get("total_open_notional", 0),
        "directional_exposure":    portfolio.get("directional_exposure", {}),
        "concentration":           portfolio.get("concentration", {}),
        "correlated_pairs":        portfolio.get("correlation_exposure", []),
        "conflicting_positions":   portfolio.get("conflicting_positions", []),
        "risk_warnings":           portfolio.get("risk_warnings", []),
        "max_drawdown_pct":        risk_metrics.get("max_drawdown_pct"),
        "confidence_correlation":  risk_metrics.get("confidence_accuracy_correlation"),
        "portfolio_status":        portfolio.get("status", "unknown"),
        "generated_at":            datetime.utcnow().isoformat(),
    }


def signal_explanation(db: Session, signal_id: int, api_key: str = "") -> dict:
    """Deep explanation for a single signal by ID."""
    from app.signals.models import TradingSignal
    from app.explainability.service import explain_signal

    signal_row = db.query(TradingSignal).filter(TradingSignal.id == signal_id).first()
    if not signal_row:
        return {"error": "signal_not_found", "signal_id": signal_id}

    asset     = signal_row.asset
    ctx       = retrieve_context(db, intent="signal", asset=asset)
    explanation = _safe_explain(db, asset)

    assembled = assemble(ctx)
    question  = (
        f"Explain why the {asset} signal ({signal_row.signal}, "
        f"confidence {signal_row.confidence:.0f}) was generated, "
        f"what drove it, and whether it has confirmation."
    )
    narrative, generated_by = generate_response(question, assembled, "signal", asset, api_key)

    return {
        "signal_id":       signal_id,
        "asset":           asset,
        "signal":          signal_row.signal,
        "confidence":      signal_row.confidence,
        "time_horizon":    signal_row.time_horizon,
        "risk_level":      signal_row.risk_level,
        "generated_at":    signal_row.generated_at.isoformat(),
        "narrative":       narrative,
        "generated_by":    generated_by,
        "full_explanation":explanation,
        "reasoning":       signal_row.reasoning or [],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _consensus(buys: list, sells: list, holds: list) -> str:
    b, s, h = len(buys), len(sells), len(holds)
    if b > s and b > h:
        return "bullish"
    if s > b and s > h:
        return "bearish"
    return "mixed"


def _safe_explain(db: Session, asset: str) -> dict | None:
    try:
        from app.explainability.service import explain_signal
        return explain_signal(db, asset)
    except Exception as e:
        logger.debug(f"Signal explanation unavailable: {e}")
        return None
