from datetime import datetime, timedelta
from app.core.logging import get_logger

logger = get_logger(__name__)

IMPACT_HIGH_WEIGHT   = 15
IMPACT_MEDIUM_WEIGHT = 8
IMPACT_LOW_WEIGHT    = 4
RSI_WEIGHT           = 10
MACD_WEIGHT          = 8
EMA_WEIGHT           = 7
BREAKOUT_WEIGHT      = 9
TREND_WEIGHT         = 6

# Minimum event impact strength required to consider event bias present
EVENT_BIAS_THRESHOLD = 0.1

TIME_HORIZON = "swing"


def generate_signal(
    symbol: str,
    impact: dict,
    analysis: dict,
    current_price: float,
) -> dict | None:
    """Combine event impact + technical analysis into a trading signal.

    Per spec: signals require BOTH event/macro bias AND technical confirmation.
    Without both, signal is HOLD regardless of individual component strength.
    """
    reasoning: list[str] = []
    confidence_score: float = 50.0
    ta_direction: int = 0

    # ── 1. Event Impact ───────────────────────────────────────────────────────
    impact_score    = impact.get("score", 0.0)
    impact_dir      = impact.get("direction", "neutral")
    impact_strength = impact.get("strength", 0.0)

    has_event_bias = impact_strength >= EVENT_BIAS_THRESHOLD and impact_dir != "neutral"

    if impact_dir == "bullish" and has_event_bias:
        confidence_score += _impact_boost(impact_score)
        reasoning.append(f"News/event flow is bullish (impact score: +{impact_score})")
    elif impact_dir == "bearish" and has_event_bias:
        confidence_score -= _impact_boost(abs(impact_score))
        reasoning.append(f"News/event flow is bearish (impact score: {impact_score})")
    else:
        reasoning.append("No significant news-driven impact detected")

    # ── 2. Technical Analysis ─────────────────────────────────────────────────
    indicators = analysis.get("indicators", {})
    breakout   = analysis.get("breakout", {})
    trend      = analysis.get("trend", {})

    rsi = indicators.get("rsi", {})
    if rsi.get("available"):
        rsi_val    = rsi["value"]
        rsi_signal = rsi["signal"]
        if rsi_signal == "oversold":
            confidence_score += RSI_WEIGHT
            ta_direction += 1
            reasoning.append(f"RSI oversold at {rsi_val} — potential reversal upward")
        elif rsi_signal == "overbought":
            confidence_score -= RSI_WEIGHT
            ta_direction -= 1
            reasoning.append(f"RSI overbought at {rsi_val} — caution, may pull back")
        else:
            reasoning.append(f"RSI neutral at {rsi_val}")

    ema = indicators.get("ema", {})
    if ema.get("available"):
        ema_signal = ema["signal"]
        if ema_signal == "golden_cross":
            confidence_score += EMA_WEIGHT + 3
            ta_direction += 1
            reasoning.append("EMA golden cross — bullish momentum crossover")
        elif ema_signal == "death_cross":
            confidence_score -= EMA_WEIGHT + 3
            ta_direction -= 1
            reasoning.append("EMA death cross — bearish momentum crossover")
        elif ema_signal == "bullish":
            confidence_score += EMA_WEIGHT
            ta_direction += 1
            reasoning.append("Price above EMA — bullish structure")
        elif ema_signal == "bearish":
            confidence_score -= EMA_WEIGHT
            ta_direction -= 1
            reasoning.append("Price below EMA — bearish structure")

    macd = indicators.get("macd", {})
    if macd.get("available"):
        macd_trend = macd["trend"]
        if macd_trend == "bullish_crossover":
            confidence_score += MACD_WEIGHT + 3
            ta_direction += 1
            reasoning.append("MACD bullish crossover — momentum shifting upward")
        elif macd_trend == "bearish_crossover":
            confidence_score -= MACD_WEIGHT + 3
            ta_direction -= 1
            reasoning.append("MACD bearish crossover — momentum shifting downward")
        elif macd_trend == "bullish":
            confidence_score += MACD_WEIGHT
            ta_direction += 1
            reasoning.append("MACD positive — upward momentum")
        elif macd_trend == "bearish":
            confidence_score -= MACD_WEIGHT
            ta_direction -= 1
            reasoning.append("MACD negative — downward momentum")

    if breakout.get("available"):
        b_signal = breakout["signal"]
        if b_signal == "breakout_up":
            confidence_score += BREAKOUT_WEIGHT
            ta_direction += 1
            reasoning.append(f"Price breaking above resistance ({breakout['resistance']}) — bullish breakout")
        elif b_signal == "breakdown":
            confidence_score -= BREAKOUT_WEIGHT
            ta_direction -= 1
            reasoning.append(f"Price breaking below support ({breakout['support']}) — bearish breakdown")

    if trend.get("available"):
        t = trend["trend"]
        if t == "uptrend":
            confidence_score += TREND_WEIGHT
            ta_direction += 1
            reasoning.append("Price in established uptrend")
        elif t == "downtrend":
            confidence_score -= TREND_WEIGHT
            ta_direction -= 1
            reasoning.append("Price in established downtrend")

    has_ta_confirmation = ta_direction != 0

    # ── 3. Dual requirement check ─────────────────────────────────────────────
    # Per spec: BUY or SELL requires BOTH event bias AND technical confirmation.
    # If either is missing, signal is HOLD.
    if not has_event_bias:
        reasoning.append("Signal held: no macro/event bias present — awaiting catalyst")
    if not has_ta_confirmation:
        reasoning.append("Signal held: no clear technical confirmation")

    # ── 4. Conflict check ─────────────────────────────────────────────────────
    event_bullish = impact_dir == "bullish"
    ta_bullish    = ta_direction > 0
    event_bearish = impact_dir == "bearish"
    ta_bearish    = ta_direction < 0
    conflicting   = (event_bullish and ta_bearish) or (event_bearish and ta_bullish)

    if conflicting:
        confidence_score = min(confidence_score, 58.0)
        reasoning.append("Event and technical signals are conflicting — confidence capped")

    # ── 5. Determine direction ────────────────────────────────────────────────
    confidence_score = max(5.0, min(95.0, confidence_score))

    both_present = has_event_bias and has_ta_confirmation

    if both_present and confidence_score >= 62:
        direction = "BUY"
    elif both_present and confidence_score <= 38:
        direction = "SELL"
    else:
        direction = "HOLD"

    # ── 6. Risk level ─────────────────────────────────────────────────────────
    vol = indicators.get("volatility", {})
    risk_level = vol.get("level", "medium") if vol.get("available") else "medium"

    # ── 7. Stop-loss / take-profit (ATR-based in risk engine, placeholders here)
    stop_loss   = None
    take_profit = None
    if current_price and direction == "BUY":
        stop_loss   = round(current_price * 0.97, 6)
        take_profit = round(current_price * 1.06, 6)
    elif current_price and direction == "SELL":
        stop_loss   = round(current_price * 1.03, 6)
        take_profit = round(current_price * 0.94, 6)

    return {
        "asset":        symbol,
        "signal":       direction,
        "confidence":   round(confidence_score, 1),
        "time_horizon": TIME_HORIZON,
        "risk_level":   risk_level,
        "reasoning":    reasoning,
        "entry_price":  current_price,
        "stop_loss":    stop_loss,
        "take_profit":  take_profit,
        "generated_at": datetime.utcnow(),
        "expires_at":   datetime.utcnow() + timedelta(hours=24),
    }


def _impact_boost(score: float) -> float:
    if score >= 3:
        return IMPACT_HIGH_WEIGHT
    elif score >= 2:
        return IMPACT_MEDIUM_WEIGHT
    return IMPACT_LOW_WEIGHT
