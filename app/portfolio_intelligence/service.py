"""
Portfolio intelligence layer.

Analyses open paper-trading positions for:
  - Concentration risk (% of total notional per asset)
  - Directional exposure (risk-on vs. risk-off balance)
  - Correlation exposure (highly-correlated position pairs)
  - Conflicting positions (correlated assets with opposing directions)
  - Automated risk warnings
"""
from __future__ import annotations
from sqlalchemy.orm import Session

from app.paper_trading.models import PaperTrade
from app.core.logging import get_logger

logger = get_logger(__name__)

_HIGH_CORR_THRESHOLD      = 0.70   # pairs above this are flagged
_CONCENTRATION_WARNING    = 0.40   # single asset > 40% of portfolio
_DIRECTIONAL_SKEW_WARNING = 0.80   # >80% one-way is over-committed


# ── Public API ────────────────────────────────────────────────────────────────

def compute_portfolio_intelligence(db: Session) -> dict:
    """Full portfolio intelligence snapshot."""
    open_trades = (
        db.query(PaperTrade)
        .filter(PaperTrade.status == "open")
        .all()
    )

    if not open_trades:
        return {
            "open_positions":     0,
            "total_open_notional": 0.0,
            "concentration":      {},
            "directional_exposure": {
                "risk_on_pct": 0.0, "risk_off_pct": 0.0,
                "risk_on_notional": 0.0, "risk_off_notional": 0.0,
            },
            "correlation_exposure":  [],
            "conflicting_positions": [],
            "risk_warnings":         [],
            "status":               "no_open_positions",
        }

    total_notional = sum(t.notional for t in open_trades)
    concentration  = _concentration(open_trades, total_notional)
    directional    = _directional_exposure(open_trades, total_notional)
    corr_data      = _safe_correlations(db)
    corr_exposure, conflicting = _correlation_analysis(open_trades, corr_data)
    warnings       = _build_warnings(
        concentration, directional, conflicting, total_notional
    )

    return {
        "open_positions":         len(open_trades),
        "total_open_notional":    round(total_notional, 2),
        "concentration":          concentration,
        "directional_exposure":   directional,
        "correlation_exposure":   corr_exposure,
        "conflicting_positions":  conflicting,
        "risk_warnings":          warnings,
        "status":                 "ok" if not warnings else "warnings",
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _concentration(
    trades: list[PaperTrade], total: float
) -> dict[str, dict]:
    by_asset: dict[str, dict] = {}
    for t in trades:
        if t.symbol not in by_asset:
            by_asset[t.symbol] = {
                "notional":  0.0,
                "direction": t.direction,
            }
        by_asset[t.symbol]["notional"] += t.notional

    for sym, data in by_asset.items():
        data["notional"]         = round(data["notional"], 2)
        data["pct_of_portfolio"] = round(data["notional"] / total * 100, 1) if total else 0.0
    return by_asset


def _directional_exposure(
    trades: list[PaperTrade], total: float
) -> dict:
    risk_on  = sum(t.notional for t in trades if t.direction == "BUY")
    risk_off = sum(t.notional for t in trades if t.direction == "SELL")
    return {
        "risk_on_notional":  round(risk_on, 2),
        "risk_off_notional": round(risk_off, 2),
        "risk_on_pct":       round(risk_on  / total * 100, 1) if total else 0.0,
        "risk_off_pct":      round(risk_off / total * 100, 1) if total else 0.0,
    }


def _correlation_analysis(
    trades: list[PaperTrade],
    corr_data: dict | None,
) -> tuple[list[dict], list[dict]]:
    if not corr_data:
        return [], []

    matrix  = corr_data.get("matrix", {})
    symbols = [t.symbol for t in trades]
    trade_map = {t.symbol: t for t in trades}

    high_corr:    list[dict] = []
    conflicting:  list[dict] = []

    seen = set()
    for i, sym_a in enumerate(symbols):
        for sym_b in symbols[i + 1:]:
            pair_key = tuple(sorted([sym_a, sym_b]))
            if pair_key in seen:
                continue
            seen.add(pair_key)

            corr = matrix.get(sym_a, {}).get(sym_b)
            if corr is None:
                corr = matrix.get(sym_b, {}).get(sym_a)
            if corr is None or abs(corr) < _HIGH_CORR_THRESHOLD:
                continue

            t_a = trade_map[sym_a]
            t_b = trade_map[sym_b]

            entry = {
                "asset_a":          sym_a,
                "asset_b":          sym_b,
                "correlation":      round(corr, 3),
                "direction_a":      t_a.direction,
                "direction_b":      t_b.direction,
                "combined_notional": round(t_a.notional + t_b.notional, 2),
            }
            high_corr.append(entry)

            # Conflicting: strongly correlated but opposite directions
            if corr >= _HIGH_CORR_THRESHOLD and t_a.direction != t_b.direction:
                conflicting.append({
                    **entry,
                    "explanation": (
                        f"{sym_a} ({t_a.direction}) and {sym_b} ({t_b.direction}) "
                        f"are highly correlated ({corr:.2f}) but positioned in "
                        f"opposite directions — positions likely offset each other"
                    ),
                })

    return high_corr, conflicting


def _build_warnings(
    concentration: dict,
    directional: dict,
    conflicting: list,
    total: float,
) -> list[str]:
    warnings: list[str] = []

    for sym, data in concentration.items():
        pct = data["pct_of_portfolio"] / 100
        if pct > _CONCENTRATION_WARNING:
            warnings.append(
                f"High concentration: {sym} is {data['pct_of_portfolio']}% "
                f"of open notional (>${data['notional']:.0f})"
            )

    risk_on_pct  = directional["risk_on_pct"]  / 100
    risk_off_pct = directional["risk_off_pct"] / 100

    if risk_on_pct > _DIRECTIONAL_SKEW_WARNING:
        warnings.append(
            f"Portfolio heavily skewed risk-on: {directional['risk_on_pct']}% "
            f"in BUY positions — limited downside hedge"
        )
    elif risk_off_pct > _DIRECTIONAL_SKEW_WARNING:
        warnings.append(
            f"Portfolio heavily skewed risk-off: {directional['risk_off_pct']}% "
            f"in SELL positions — limited upside participation"
        )

    if conflicting:
        warnings.append(
            f"{len(conflicting)} conflicting position pair(s): correlated assets "
            f"held in opposing directions"
        )

    return warnings


def _safe_correlations(db: Session) -> dict | None:
    try:
        from app.analysis.service import compute_correlations
        return compute_correlations(db)
    except Exception as e:
        logger.debug(f"Correlation data unavailable for portfolio intelligence: {e}")
        return None
