def calculate_stops(
    direction: str,
    entry_price: float,
    atr_value: float | None,
    atr_multiplier: float = 2.0,
) -> dict:
    """Calculate ATR-based stop-loss and take-profit levels.

    Uses 2× ATR for stop-loss and 3× ATR for take-profit (1:1.5 R:R minimum).
    Falls back to fixed percentage if ATR is unavailable.
    """
    if not entry_price:
        return {"stop_loss": None, "take_profit": None, "risk_reward": None}

    if atr_value:
        stop_distance   = atr_value * atr_multiplier
        target_distance = atr_value * (atr_multiplier * 1.5)
    else:
        # Fixed fallback: 3% stop, 5% target
        stop_distance   = entry_price * 0.03
        target_distance = entry_price * 0.05

    if direction == "BUY":
        stop_loss   = entry_price - stop_distance
        take_profit = entry_price + target_distance
    elif direction == "SELL":
        stop_loss   = entry_price + stop_distance
        take_profit = entry_price - target_distance
    else:
        return {"stop_loss": None, "take_profit": None, "risk_reward": None}

    risk_reward = round(target_distance / stop_distance, 2) if stop_distance else None

    return {
        "stop_loss":   round(stop_loss, 6),
        "take_profit": round(take_profit, 6),
        "risk_reward": risk_reward,
        "stop_distance": round(stop_distance, 6),
    }


def suggest_position_size(
    confidence: float,
    risk_level: str,
    portfolio_pct: float = 1.0,
) -> dict:
    """Suggest position size as a % of portfolio based on confidence and risk.

    This is a Kelly-inspired heuristic, not full Kelly criterion.
    Max allocation is capped to avoid overexposure on any single trade.
    """
    # Base allocation from confidence band
    if confidence >= 80:
        base_pct = portfolio_pct * 0.10
    elif confidence >= 70:
        base_pct = portfolio_pct * 0.07
    elif confidence >= 62:
        base_pct = portfolio_pct * 0.05
    else:
        base_pct = portfolio_pct * 0.02

    # Risk level reduces allocation
    risk_multiplier = {"low": 1.0, "medium": 0.75, "high": 0.5}.get(risk_level, 0.75)
    suggested_pct = round(base_pct * risk_multiplier, 2)

    return {
        "suggested_portfolio_pct": suggested_pct,
        "note": "Suggested sizing only — always apply your own risk management rules",
    }
