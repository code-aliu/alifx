from sqlalchemy.orm import Session
from app.risk.scorer import compute_atr, score_risk, detect_market_regime
from app.risk.calculator import calculate_stops, suggest_position_size
from app.market_data.service import get_price_history
from app.core.logging import get_logger

logger = get_logger(__name__)

# Minimum confidence required to emit a BUY or SELL signal
SIGNAL_CONFIDENCE_THRESHOLD = 55.0


def assess_signal_risk(
    db: Session,
    symbol: str,
    signal_direction: str,
    confidence: float,
    entry_price: float | None,
    volatility_level: str,
) -> dict:
    """Run the full risk assessment for a signal and return enriched risk data."""
    prices = get_price_history(db, symbol=symbol, limit=50)

    atr     = compute_atr(prices) if prices else {"available": False}
    regime  = detect_market_regime(prices) if prices else {"available": False, "regime": "unknown"}
    risk    = score_risk(volatility_level, atr, confidence)

    atr_value = atr.get("value") if atr.get("available") else None
    stops     = calculate_stops(signal_direction, entry_price, atr_value)
    sizing    = suggest_position_size(confidence, risk["risk_level"])

    # Adjust confidence down for high-risk environments
    adjusted_confidence = max(5.0, min(95.0, confidence + risk["confidence_adjustment"]))

    return {
        "risk_score":           risk["risk_score"],
        "risk_level":           risk["risk_level"],
        "adjusted_confidence":  round(adjusted_confidence, 1),
        "confidence_adjustment": risk["confidence_adjustment"],
        "atr":                  atr,
        "market_regime":        regime.get("regime", "unknown"),
        "stop_loss":            stops["stop_loss"],
        "take_profit":          stops["take_profit"],
        "risk_reward":          stops.get("risk_reward"),
        "position_sizing":      sizing,
    }


def filter_signal(signal_direction: str, adjusted_confidence: float) -> str:
    """Apply confidence threshold — demote weak signals to HOLD."""
    if signal_direction in ("BUY", "SELL") and adjusted_confidence < SIGNAL_CONFIDENCE_THRESHOLD:
        return "HOLD"
    return signal_direction
