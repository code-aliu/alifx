"""
Enhanced portfolio exposure analysis.

Extends the existing portfolio_intelligence service with:
  - Volatility clustering: multiple high-vol assets in same direction = compounded drawdown
  - Regime sensitivity score: what % of portfolio is in regime-sensitive assets
  - Max theoretical drawdown: if all stops hit simultaneously
  - Sector/asset class concentration
  - Explainable risk summary with educational context
"""
from __future__ import annotations
from sqlalchemy.orm import Session

from app.paper_trading.models   import PaperTrade, PaperPortfolio
from app.portfolio_intelligence.service import compute_portfolio_intelligence
from app.risk.scorer            import compute_atr
from app.market_data.service    import get_price_history
from app.core.logging           import get_logger

logger = get_logger(__name__)

# Asset class groupings for concentration analysis
_ASSET_CLASSES: dict[str, str] = {
    "BTC/USD": "crypto",   "ETH/USD": "crypto",   "BNB/USD": "crypto",
    "XRP/USD": "crypto",   "SOL/USD": "crypto",   "ADA/USD": "crypto",
    "EUR/USD": "forex",    "GBP/USD": "forex",    "USD/JPY": "forex",
    "AUD/USD": "forex",    "USD/CAD": "forex",    "USD/CHF": "forex",
    "XAU/USD": "commodity", "XAG/USD": "commodity", "WTI":    "commodity",
    "SPX":     "equity",   "NAS100":  "equity",   "DJI":    "equity",
}

_CRYPTO_ASSETS = {"BTC/USD", "ETH/USD", "BNB/USD", "XRP/USD", "SOL/USD", "ADA/USD"}
_REGIME_SENSITIVE = {"BTC/USD", "ETH/USD", "XRP/USD", "SOL/USD", "SPX", "NAS100"}


def analyze_portfolio_risk(db: Session) -> dict:
    """
    Full portfolio risk analysis — combines existing intelligence with
    volatility clustering, drawdown projection, and regime sensitivity.
    """
    base    = compute_portfolio_intelligence(db)
    trades  = db.query(PaperTrade).filter(PaperTrade.status == "open").all()
    port    = db.query(PaperPortfolio).filter(PaperPortfolio.id == 1).first()
    balance = port.current_balance if port else 10_000.0

    if not trades:
        return {**base, "volatility_clustering": [], "drawdown_projection": None,
                "regime_sensitivity": None, "asset_class_concentration": {},
                "risk_summary": _empty_summary()}

    volatility_data  = _compute_per_asset_volatility(db, trades)
    clustering       = _volatility_clustering(trades, volatility_data)
    drawdown_proj    = _max_drawdown_projection(trades, balance)
    regime_sens      = _regime_sensitivity(trades, base.get("total_open_notional", 0))
    class_conc       = _asset_class_concentration(trades, base.get("total_open_notional", 0))
    risk_summary     = _build_risk_summary(base, clustering, drawdown_proj, regime_sens)

    return {
        **base,
        "volatility_clustering":    clustering,
        "drawdown_projection":       drawdown_proj,
        "regime_sensitivity":        regime_sens,
        "asset_class_concentration": class_conc,
        "risk_summary":              risk_summary,
        "account_balance":           balance,
    }


# ── Volatility clustering ─────────────────────────────────────────────────────

def _compute_per_asset_volatility(db: Session, trades: list[PaperTrade]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for t in trades:
        try:
            prices = get_price_history(db, symbol=t.symbol, limit=30)
            atr    = compute_atr(prices) if len(prices) >= 15 else {"available": False}
            result[t.symbol] = atr
        except Exception:
            result[t.symbol] = {"available": False}
    return result


def _volatility_clustering(
    trades: list[PaperTrade], vol_data: dict[str, dict]
) -> list[dict]:
    """
    Identify groups of highly volatile assets held in the same direction.
    These amplify drawdown because they tend to move together.
    """
    high_vol = [
        t for t in trades
        if vol_data.get(t.symbol, {}).get("available")
        and vol_data[t.symbol].get("pct", 0) > 2.0
    ]

    by_direction: dict[str, list] = {}
    for t in high_vol:
        by_direction.setdefault(t.direction, []).append(t)

    clusters = []
    for direction, group in by_direction.items():
        if len(group) >= 2:
            assets = [t.symbol for t in group]
            combined_notional = sum(t.notional for t in group)
            avg_atr = sum(vol_data[t.symbol].get("pct", 0) for t in group) / len(group)
            clusters.append({
                "direction":          direction,
                "assets":             assets,
                "combined_notional":  round(combined_notional, 2),
                "avg_atr_pct":        round(avg_atr, 2),
                "explanation": (
                    f"{len(assets)} {direction} positions ({', '.join(assets)}) each have "
                    f">2% ATR. In a sharp move against you, all could hit stops simultaneously — "
                    f"combined exposure ${combined_notional:,.0f}"
                ),
            })
    return clusters


# ── Drawdown projection ───────────────────────────────────────────────────────

def _max_drawdown_projection(trades: list[PaperTrade], balance: float) -> dict:
    """
    Worst-case drawdown if all open positions hit their stop-losses simultaneously.
    """
    total_stop_loss_risk = 0.0
    positions = []

    for t in trades:
        if t.stop_loss and t.entry_price:
            stop_dist  = abs(t.entry_price - t.stop_loss)
            dollar_risk = stop_dist * t.quantity
        else:
            dollar_risk = t.notional * 0.03  # assume 3% if no stop set

        total_stop_loss_risk += dollar_risk
        positions.append({
            "asset":         t.symbol,
            "direction":     t.direction,
            "dollar_risk":   round(dollar_risk, 2),
            "pct_of_account": round(dollar_risk / balance * 100, 2) if balance else 0,
        })

    worst_case_pct = round(total_stop_loss_risk / balance * 100, 2) if balance else 0

    return {
        "total_stop_loss_risk_usd": round(total_stop_loss_risk, 2),
        "worst_case_drawdown_pct":  worst_case_pct,
        "per_position":             positions,
        "assessment": (
            "critical" if worst_case_pct > 20
            else "high"     if worst_case_pct > 10
            else "moderate" if worst_case_pct > 5
            else "low"
        ),
        "explanation": (
            f"If all {len(trades)} open positions hit their stop-losses simultaneously, "
            f"total account drawdown would be {worst_case_pct}% (${total_stop_loss_risk:,.0f}). "
            "This is a worst-case theoretical scenario, not a prediction."
        ),
    }


# ── Regime sensitivity ────────────────────────────────────────────────────────

def _regime_sensitivity(trades: list[PaperTrade], total_notional: float) -> dict:
    sensitive      = [t for t in trades if t.symbol in _REGIME_SENSITIVE]
    sensitive_notional = sum(t.notional for t in sensitive)
    pct            = round(sensitive_notional / total_notional * 100, 1) if total_notional else 0.0

    return {
        "regime_sensitive_notional": round(sensitive_notional, 2),
        "regime_sensitive_pct":      pct,
        "sensitive_assets":          list({t.symbol for t in sensitive}),
        "rating":                    "high" if pct > 60 else "medium" if pct > 30 else "low",
        "explanation": (
            f"{pct}% of your open notional (${sensitive_notional:,.0f}) is in assets that are "
            "sensitive to market regime shifts (crypto, equities). "
            "A sudden risk-off move could impact all of these simultaneously."
        ),
    }


# ── Asset class concentration ─────────────────────────────────────────────────

def _asset_class_concentration(trades: list[PaperTrade], total_notional: float) -> dict[str, dict]:
    classes: dict[str, float] = {}
    for t in trades:
        cls = _ASSET_CLASSES.get(t.symbol, "other")
        classes[cls] = classes.get(cls, 0.0) + t.notional

    return {
        cls: {
            "notional": round(val, 2),
            "pct":      round(val / total_notional * 100, 1) if total_notional else 0.0,
        }
        for cls, val in sorted(classes.items(), key=lambda x: -x[1])
    }


# ── Risk summary ──────────────────────────────────────────────────────────────

def _build_risk_summary(
    base: dict, clustering: list, drawdown: dict, regime_sens: dict
) -> dict:
    issues:  list[str] = list(base.get("risk_warnings", []))
    actions: list[str] = []

    if clustering:
        for c in clustering:
            issues.append(c["explanation"])
        actions.append("Consider reducing overlapping volatile positions to limit simultaneous stop-outs")

    dd_pct = drawdown.get("worst_case_drawdown_pct", 0) if drawdown else 0
    if dd_pct > 15:
        issues.append(f"Worst-case drawdown projection: {dd_pct}% — consider tightening stops or reducing size")
        actions.append("Review stop-loss placement; worst-case scenario exceeds 15% of account")
    elif dd_pct > 8:
        actions.append(f"Worst-case drawdown {dd_pct}% — within acceptable range but worth monitoring")

    if regime_sens and regime_sens.get("rating") == "high":
        actions.append("High regime sensitivity — consider adding non-correlated assets or hedges")

    return {
        "issues":  issues,
        "actions": actions,
        "overall": "critical" if len(issues) >= 3 else "elevated" if len(issues) >= 1 else "healthy",
    }


def _empty_summary() -> dict:
    return {"issues": [], "actions": [], "overall": "healthy"}
