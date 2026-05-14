from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.signals.models import TradingSignal
from app.signals.generator import generate_signal
from app.impact.service import get_asset_impact
from app.analysis.service import analyse_asset
from app.market_data.service import get_latest_prices
from app.risk.service import assess_signal_risk, filter_signal
from app.impact.rules import TRACKED_SYMBOLS
from app.core import cache
from app.core.logging import get_logger

logger = get_logger(__name__)

CACHE_TTL = 310  # slightly longer than pipeline interval


def run_signal_pipeline(db: Session) -> int:
    """Generate risk-adjusted signals for all tracked assets and persist them.

    Returns number of signals generated.
    """
    impact_map    = get_asset_impact(db, hours=24)
    latest_prices = {p["symbol"]: p["close"] for p in get_latest_prices(db)}
    generated     = 0

    for symbol in TRACKED_SYMBOLS:
        try:
            impact        = impact_map.get(symbol, {"score": 0.0, "direction": "neutral", "strength": 0.0})
            analysis      = analyse_asset(db, symbol)
            current_price = latest_prices.get(symbol)

            signal_data = generate_signal(
                symbol=symbol,
                impact=impact,
                analysis=analysis,
                current_price=current_price,
            )

            if not signal_data:
                continue

            # Risk engine: assess, adjust confidence, and override stops with ATR-based levels
            risk = assess_signal_risk(
                db=db,
                symbol=symbol,
                signal_direction=signal_data["signal"],
                confidence=signal_data["confidence"],
                entry_price=current_price,
                volatility_level=signal_data["risk_level"],
            )

            # Apply risk adjustments
            signal_data["confidence"] = risk["adjusted_confidence"]
            signal_data["risk_level"] = risk["risk_level"]
            signal_data["signal"]     = filter_signal(signal_data["signal"], risk["adjusted_confidence"])
            signal_data["stop_loss"]  = risk["stop_loss"] or signal_data.get("stop_loss")
            signal_data["take_profit"] = risk["take_profit"] or signal_data.get("take_profit")

            # Append risk context to reasoning
            if risk["confidence_adjustment"] < 0:
                signal_data["reasoning"].append(
                    f"Risk adjustment applied: confidence reduced by {abs(risk['confidence_adjustment'])} "
                    f"due to {risk['risk_level']} volatility (ATR-based)"
                )
            if risk.get("market_regime") != "unknown":
                signal_data["reasoning"].append(f"Market regime: {risk['market_regime']}")
            if risk.get("risk_reward"):
                signal_data["reasoning"].append(f"Risk/reward ratio: {risk['risk_reward']}:1")

            signal_data["risk_metadata"] = {
                "risk_score":     risk["risk_score"],
                "market_regime":  risk["market_regime"],
                "risk_reward":    risk.get("risk_reward"),
                "position_sizing": risk["position_sizing"],
                "atr":            risk["atr"],
            }

            _persist_signal(db, signal_data)
            _cache_signal(symbol, signal_data)
            generated += 1

        except Exception as e:
            logger.error(f"Signal pipeline failed for {symbol}: {e}")

    db.commit()
    logger.info(f"Signals: generated {generated} signals")
    return generated


def _persist_signal(db: Session, data: dict) -> None:
    signal = TradingSignal(
        asset=data["asset"],
        signal=data["signal"],
        confidence=data["confidence"],
        time_horizon=data["time_horizon"],
        risk_level=data["risk_level"],
        reasoning=data["reasoning"],
        entry_price=data.get("entry_price"),
        stop_loss=data.get("stop_loss"),
        take_profit=data.get("take_profit"),
        generated_at=data["generated_at"],
        expires_at=data.get("expires_at"),
    )
    db.add(signal)


def _cache_signal(symbol: str, data: dict) -> None:
    serializable = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in data.items()}
    cache.set_json(f"signal:{symbol}", serializable, ttl_seconds=CACHE_TTL)


def get_latest_signals(db: Session) -> list[dict]:
    """Return the most recent signal for each tracked asset."""
    results = []
    for symbol in TRACKED_SYMBOLS:
        cached = cache.get_json(f"signal:{symbol}")
        if cached:
            results.append(cached)
        else:
            row = (
                db.query(TradingSignal)
                .filter(TradingSignal.asset == symbol)
                .order_by(TradingSignal.generated_at.desc())
                .first()
            )
            if row:
                results.append(row.to_dict())

    results.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return results


def get_signals_for_asset(db: Session, symbol: str, limit: int = 10) -> list[dict]:
    rows = (
        db.query(TradingSignal)
        .filter(TradingSignal.asset == symbol.upper())
        .order_by(TradingSignal.generated_at.desc())
        .limit(limit)
        .all()
    )
    return [r.to_dict() for r in rows]
