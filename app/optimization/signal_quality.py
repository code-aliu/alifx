"""
Signal quality score — computed at generation time, before outcome is known.

Composite 0–100 score from five independently measurable components:

  confidence_component  (20%) — raw confidence, normalized to 0–100
  regime_alignment      (25%) — does the signal direction match the regime tendency?
  event_strength        (20%) — quality and strength of triggering event
  asset_track_record    (20%) — historical quality for this specific asset
  calibration_status    (15%) — how well-calibrated is the system at this confidence level?

The score is stored in SignalOutcome.performance_score at creation time.
At resolution, the signal_tracking service overwrites it with the actual outcome score.

This allows comparing pre-resolution quality predictions against post-resolution
actual outcomes — a useful meta-metric for the optimizer's own accuracy.
"""
from __future__ import annotations

_REGIME_BULLISH_KEYWORDS = {"risk_on", "bullish", "recovery", "expansion"}
_REGIME_BEARISH_KEYWORDS = {"risk_off", "bearish", "contraction", "recession"}

_WEIGHTS = {
    "confidence":  0.20,
    "regime":      0.25,
    "event":       0.20,
    "asset":       0.20,
    "calibration": 0.15,
}


def compute_quality_score(
    signal_data: dict,
    regime: dict | None,
    asset_track_record_adj: float,
    calibration_factor: float,
) -> float:
    """
    Returns a 0–100 quality score for a signal before its outcome is known.

    Parameters:
      signal_data           — the generated signal dict (must have signal, confidence, reasoning)
      regime                — current regime dict from regime.service.get_current_regime()
      asset_track_record_adj — asset adjustment from asset_weights.get_asset_adjustment()
      calibration_factor     — calibration factor from calibrator.get_calibration_adjustments()
    """
    confidence  = float(signal_data.get("confidence", 50.0))
    direction   = signal_data.get("signal", "HOLD")
    reasoning   = signal_data.get("reasoning", [])
    impact_str  = signal_data.get("event_impact_strength", None)

    scores: dict[str, float] = {
        "confidence":  _confidence_score(confidence),
        "regime":      _regime_alignment_score(direction, regime),
        "event":       _event_strength_score(reasoning, impact_str),
        "asset":       _asset_track_record_score(asset_track_record_adj),
        "calibration": _calibration_status_score(calibration_factor),
    }

    weighted = sum(scores[k] * _WEIGHTS[k] for k in scores)
    return round(min(100.0, max(0.0, weighted)), 1)


def quality_score_components(
    signal_data: dict,
    regime: dict | None,
    asset_track_record_adj: float,
    calibration_factor: float,
) -> dict:
    """Returns the component breakdown for inspection."""
    confidence  = float(signal_data.get("confidence", 50.0))
    direction   = signal_data.get("signal", "HOLD")
    reasoning   = signal_data.get("reasoning", [])
    impact_str  = signal_data.get("event_impact_strength", None)

    return {
        "confidence":  round(_confidence_score(confidence), 1),
        "regime":      round(_regime_alignment_score(direction, regime), 1),
        "event":       round(_event_strength_score(reasoning, impact_str), 1),
        "asset":       round(_asset_track_record_score(asset_track_record_adj), 1),
        "calibration": round(_calibration_status_score(calibration_factor), 1),
        "weights":     _WEIGHTS,
    }


# ── Component scorers ─────────────────────────────────────────────────────────

def _confidence_score(confidence: float) -> float:
    """Normalize confidence to 0-100. Higher confidence = higher quality proxy."""
    return min(100.0, max(0.0, confidence))


def _regime_alignment_score(direction: str, regime: dict | None) -> float:
    """Does the signal direction align with the current regime tendency?"""
    if not regime or direction == "HOLD":
        return 50.0

    primary = (regime.get("primary_regime") or "").lower()
    regime_confidence = regime.get("confidence", 0.5)

    is_bullish_regime = any(kw in primary for kw in _REGIME_BULLISH_KEYWORDS)
    is_bearish_regime = any(kw in primary for kw in _REGIME_BEARISH_KEYWORDS)

    aligned = (direction == "BUY" and is_bullish_regime) or (direction == "SELL" and is_bearish_regime)
    misaligned = (direction == "BUY" and is_bearish_regime) or (direction == "SELL" and is_bullish_regime)

    if aligned:
        return round(60.0 + (regime_confidence * 40.0), 1)  # 60–100
    if misaligned:
        return round(60.0 - (regime_confidence * 50.0), 1)  # 10–60
    return 50.0  # regime is neutral/unknown


def _event_strength_score(reasoning: list[str], impact_str) -> float:
    """Approximate event strength from reasoning content and impact metadata."""
    if impact_str is not None:
        try:
            strength = float(impact_str)
            return round(min(100.0, 40.0 + strength * 60.0), 1)
        except (TypeError, ValueError):
            pass

    # Heuristic: count positive signal indicators in reasoning text
    positive_indicators = [
        "bullish", "bearish", "oversold", "overbought", "golden cross",
        "death cross", "breakout", "strong", "high impact", "significant",
    ]
    reasoning_text = " ".join(reasoning).lower()
    hits = sum(1 for kw in positive_indicators if kw in reasoning_text)
    return round(min(100.0, 30.0 + hits * 14.0), 1)


def _asset_track_record_score(asset_adj: float) -> float:
    """Convert asset adjustment (-10 to +5) to 0-100 quality score component."""
    # asset_adj range: -10 to +5 → map to 0-100
    return round(min(100.0, max(0.0, 60.0 + (asset_adj / 10.0) * 40.0)), 1)


def _calibration_status_score(calibration_factor: float) -> float:
    """
    Positive calibration factor = system is underconfident (boosting) = OK quality signal.
    Negative calibration factor = system is overconfident (reducing) = lower quality.
    """
    return round(min(100.0, max(0.0, 50.0 + calibration_factor * 2.0)), 1)
