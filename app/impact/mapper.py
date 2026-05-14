from app.impact.rules import compute_impact_score, resolve_asset_code, TRACKED_SYMBOLS
from app.events.models import MarketEvent


def map_events_to_impact(events: list[MarketEvent]) -> dict[str, float]:
    """Aggregate impact scores across multiple events per tracked asset.

    Returns {symbol: cumulative_impact_score}
    Scores are unbounded floats — positive = bullish, negative = bearish.
    """
    scores: dict[str, float] = {sym: 0.0 for sym in TRACKED_SYMBOLS}

    for event in events:
        score = compute_impact_score(event.sentiment, event.importance)
        if score == 0:
            continue
        for asset_code in (event.affected_assets or []):
            symbol = resolve_asset_code(asset_code)
            if symbol:
                scores[symbol] += score

    return scores


def summarize_impact(scores: dict[str, float]) -> dict[str, dict]:
    """Convert raw scores into human-readable impact summaries."""
    result = {}
    for symbol, score in scores.items():
        if score > 0:
            direction = "bullish"
        elif score < 0:
            direction = "bearish"
        else:
            direction = "neutral"

        strength = min(abs(score) / 6.0, 1.0)  # normalize 0–1 (max realistic score ~6)

        result[symbol] = {
            "score": round(score, 2),
            "direction": direction,
            "strength": round(strength, 2),
        }
    return result
