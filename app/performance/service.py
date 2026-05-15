"""
Signal performance analytics.

Reads from signal_outcomes + paper_trades to compute:
  - win rate, average return, average duration
  - max drawdown, simplified Sharpe ratio
  - confidence accuracy correlation
  - breakdowns by asset, regime, and signal direction
"""
from __future__ import annotations
import math
import statistics
from datetime import datetime
from sqlalchemy.orm import Session

from app.signal_tracking.models import SignalOutcome
from app.paper_trading.models import PaperTrade, PaperPortfolio
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────

def get_signal_performance(db: Session) -> dict:
    """Full performance analytics across all resolved signal outcomes."""
    outcomes = db.query(SignalOutcome).all()
    closed   = (
        db.query(PaperTrade)
        .filter(PaperTrade.status == "closed")
        .order_by(PaperTrade.closed_at)
        .all()
    )
    portfolio = db.query(PaperPortfolio).filter(PaperPortfolio.id == 1).first()
    initial   = portfolio.initial_balance if portfolio else 10_000.0

    resolved  = [o for o in outcomes if o.status in ("completed", "expired")]
    wins      = [o for o in resolved if o.outcome == "win"]
    losses    = [o for o in resolved if o.outcome == "loss"]
    completed = wins + losses  # excludes expired and neutral

    # ── Core metrics ──────────────────────────────────────────────────────────
    win_rate = _pct(len(wins), len(completed))

    pnl_pcts = [t.pnl_pct for t in closed if t.pnl_pct is not None]
    avg_return = round(statistics.mean(pnl_pcts), 3) if pnl_pcts else None

    durations = _compute_durations(closed)
    avg_duration_hours = round(statistics.mean(durations), 1) if durations else None

    pnls     = [t.pnl for t in closed if t.pnl is not None]
    max_dd   = _max_drawdown(pnls, initial)
    sharpe   = _sharpe(pnl_pcts)
    conf_corr = _confidence_correlation(resolved)

    # ── Breakdowns ────────────────────────────────────────────────────────────
    by_asset     = _breakdown(resolved, key=lambda o: o.asset)
    by_regime    = _breakdown(resolved, key=lambda o: o.market_regime or "unknown")
    by_direction = _breakdown(resolved, key=lambda o: o.direction)

    return {
        "summary": {
            "total_signals_tracked":    len(outcomes),
            "total_resolved":           len(resolved),
            "total_completed":          len(completed),
            "total_expired":            sum(1 for o in resolved if o.outcome == "expired"),
            "win_count":                len(wins),
            "loss_count":               len(losses),
            "win_rate_pct":             win_rate,
            "avg_return_pct":           avg_return,
            "avg_duration_hours":       avg_duration_hours,
        },
        "risk_metrics": {
            "max_drawdown_usd":         max_dd["max_drawdown_usd"],
            "max_drawdown_pct":         max_dd["max_drawdown_pct"],
            "sharpe_ratio":             sharpe,
            "confidence_accuracy_correlation": conf_corr,
        },
        "by_asset":     by_asset,
        "by_regime":    by_regime,
        "by_direction": by_direction,
        "computed_at":  datetime.utcnow().isoformat(),
    }


def get_performance_timeseries(db: Session, limit: int = 50) -> dict:
    """Cumulative PnL curve from closed paper trades, for charting."""
    closed = (
        db.query(PaperTrade)
        .filter(PaperTrade.status == "closed")
        .order_by(PaperTrade.closed_at)
        .limit(limit)
        .all()
    )
    portfolio = db.query(PaperPortfolio).filter(PaperPortfolio.id == 1).first()
    initial   = portfolio.initial_balance if portfolio else 10_000.0

    cumulative  = 0.0
    series: list[dict] = []
    for t in closed:
        pnl       = t.pnl or 0.0
        cumulative += pnl
        series.append({
            "trade_id":    t.id,
            "asset":       t.symbol,
            "direction":   t.direction,
            "closed_at":   t.closed_at.isoformat() if t.closed_at else None,
            "pnl_usd":     round(pnl, 2),
            "pnl_pct":     t.pnl_pct,
            "cumulative_pnl": round(cumulative, 2),
            "equity":      round(initial + cumulative, 2),
            "exit_reason": t.exit_reason,
        })

    return {
        "initial_balance": initial,
        "series":          series,
        "final_equity":    round(initial + cumulative, 2),
        "total_trades":    len(series),
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _pct(part: int, total: int) -> float:
    return round(part / total * 100, 1) if total > 0 else 0.0


def _compute_durations(trades: list[PaperTrade]) -> list[float]:
    durations = []
    for t in trades:
        if t.opened_at and t.closed_at:
            hours = (t.closed_at - t.opened_at).total_seconds() / 3600
            durations.append(hours)
    return durations


def _max_drawdown(pnls: list[float], initial: float) -> dict:
    if not pnls:
        return {"max_drawdown_usd": 0.0, "max_drawdown_pct": 0.0}

    cumulative = []
    running    = 0.0
    for p in pnls:
        running += p
        cumulative.append(running)

    peak   = 0.0
    max_dd = 0.0
    for val in cumulative:
        if val > peak:
            peak = val
        dd = peak - val
        if dd > max_dd:
            max_dd = dd

    return {
        "max_drawdown_usd": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd / initial * 100, 2) if initial > 0 else 0.0,
    }


def _sharpe(pnl_pcts: list[float]) -> float | None:
    """Simplified Sharpe: mean / std × √n. No risk-free rate (paper account)."""
    if len(pnl_pcts) < 2:
        return None
    mean_r = statistics.mean(pnl_pcts)
    std_r  = statistics.stdev(pnl_pcts)
    if std_r == 0:
        return None
    return round(mean_r / std_r * math.sqrt(len(pnl_pcts)), 3)


def _confidence_correlation(outcomes: list[SignalOutcome]) -> float | None:
    """Pearson correlation between signal confidence and binary win outcome (1=win, 0=loss)."""
    pairs = [
        (o.confidence, 1.0 if o.outcome == "win" else 0.0)
        for o in outcomes
        if o.outcome in ("win", "loss") and o.confidence is not None
    ]
    if len(pairs) < 3:
        return None
    x = [p[0] for p in pairs]
    y = [p[1] for p in pairs]
    return round(_pearson(x, y), 3)


def _pearson(x: list[float], y: list[float]) -> float:
    n      = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    num    = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    den_x  = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    den_y  = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def _breakdown(
    outcomes: list[SignalOutcome],
    key,
) -> dict[str, dict]:
    groups: dict[str, list[SignalOutcome]] = {}
    for o in outcomes:
        k = key(o) or "unknown"
        groups.setdefault(k, []).append(o)

    result = {}
    for k, group in sorted(groups.items()):
        wins   = sum(1 for o in group if o.outcome == "win")
        losses = sum(1 for o in group if o.outcome == "loss")
        total  = wins + losses
        scores = [o.performance_score for o in group if o.performance_score is not None]
        result[k] = {
            "total_signals":   len(group),
            "wins":            wins,
            "losses":          losses,
            "win_rate_pct":    _pct(wins, total),
            "avg_performance_score": round(statistics.mean(scores), 1) if scores else None,
        }
    return result
