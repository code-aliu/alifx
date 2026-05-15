"""
Market Reasoning Validation Service.

Three public functions:
  run_test_scenario(scenario_id, db)      — run a pre-defined scenario end-to-end
  get_reasoning_audit(signal_id, db)      — full audit of a stored signal
  validate_reasoning_from_headline(...)   — ad-hoc headline extraction + scoring
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from sqlalchemy.orm import Session

from app.reasoning.scenarios import get_scenario, list_scenarios
from app.reasoning.validator import (
    score_economic_coherence,
    score_internal_consistency,
    score_confidence_calibration,
    score_ta_confirmation_alignment,
    score_stale_signal_detection,
    build_audit_log,
)
from app.events.extractor import extract_event
from app.impact.rules import compute_impact_score, ASSET_CODE_MAP
from app.validation.service import validate_signal
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Internal mock article ─────────────────────────────────────────────────────

@dataclass
class _MockArticle:
    title: str
    description: str = ""
    id: int | None = None


# ── Public API ────────────────────────────────────────────────────────────────

def run_test_scenario(scenario_id: str, db: Session) -> dict:
    """Run a pre-defined scenario and return extraction + validation scores.

    Scores all 5 metrics:
      1. economic_coherence   — extraction accuracy
      2. internal_consistency — synthetic signal coherence
      3. confidence_calibration
      4. ta_confirmation       — TA confirms event direction
      5. stale_detection       — freshness logic works on new signal
    """
    scenario = get_scenario(scenario_id)
    if not scenario:
        return {"error": "scenario_not_found", "scenario_id": scenario_id}

    article  = _MockArticle(title=scenario["headline"])
    extracted = extract_event(article)
    expected  = scenario["expected"]

    # Metric 1: extraction accuracy
    ec_score = score_economic_coherence(extracted or {}, expected)

    # Impact per tracked asset
    impact_per_asset = _compute_impact_per_asset(extracted)

    # Build a synthetic signal reflecting the extraction result
    synthetic = _build_synthetic_signal(extracted)

    # Validate the synthetic signal (db used only for consistency check — empty is fine)
    validation = validate_signal(synthetic, db)

    ic_score = score_internal_consistency(synthetic)
    cc_score = score_confidence_calibration(synthetic, validation)
    ta_score = score_ta_confirmation_alignment(synthetic)
    sd_score = score_stale_signal_detection(synthetic, validation)

    scores = [ec_score["score"], ic_score["score"], cc_score["score"],
              ta_score["score"], sd_score["score"]]
    overall = round(sum(scores) / len(scores), 2)
    passed  = sum(1 for s in scores if s >= 0.8)

    return {
        "scenario": {
            "id":         scenario["id"],
            "name":       scenario["name"],
            "event_type": scenario["event_type"],
            "headline":   scenario["headline"],
        },
        "extracted_event":   extracted,
        "expected":          expected,
        "impact_per_asset":  impact_per_asset,
        "synthetic_signal":  synthetic,
        "validation_report": {
            "overall_score":  overall,
            "metrics_passed": passed,
            "total_metrics":  len(scores),
            "pass_rate":      f"{passed}/{len(scores)}",
            "metrics": {
                "economic_coherence":     ec_score,
                "internal_consistency":   ic_score,
                "confidence_calibration": cc_score,
                "ta_confirmation":        ta_score,
                "stale_detection":        sd_score,
            },
        },
    }


def get_reasoning_audit(signal_id: int, db: Session) -> dict:
    """Full reasoning audit for a stored signal.

    Returns parsed reasoning layers, confidence journey, and 4 quality metrics
    (economic_coherence is omitted — it requires a reference scenario).
    """
    from app.signals.models import TradingSignal

    row = db.query(TradingSignal).filter(TradingSignal.id == signal_id).first()
    if not row:
        return {"error": "signal_not_found", "signal_id": signal_id}

    signal     = row.to_dict()
    validation = validate_signal(signal, db)
    audit      = build_audit_log(signal)

    ic_score = score_internal_consistency(signal)
    cc_score = score_confidence_calibration(signal, validation)
    ta_score = score_ta_confirmation_alignment(signal)
    sd_score = score_stale_signal_detection(signal, validation)

    scores  = [ic_score["score"], cc_score["score"], ta_score["score"], sd_score["score"]]
    overall = round(sum(scores) / len(scores), 2)
    passed  = sum(1 for s in scores if s >= 0.8)

    return {
        "signal_id":    signal_id,
        "asset":        signal.get("asset"),
        "signal":       signal.get("signal"),
        "confidence":   signal.get("confidence"),
        "generated_at": signal.get("generated_at"),
        "audit_log":    audit,
        "validation":   validation,
        "reasoning_audit": {
            "overall_score":  overall,
            "metrics_passed": passed,
            "total_metrics":  len(scores),
            "pass_rate":      f"{passed}/{len(scores)}",
            "metrics": {
                "internal_consistency":   ic_score,
                "confidence_calibration": cc_score,
                "ta_confirmation":        ta_score,
                "stale_detection":        sd_score,
            },
        },
    }


def validate_reasoning_from_headline(
    headline: str,
    db: Session,
    description: str = "",
    asset: str | None = None,
    scenario_id: str | None = None,
) -> dict:
    """Ad-hoc headline validation.

    Extracts an event from the headline, computes impact scores, and
    optionally compares against a named scenario's expected outcomes.
    """
    article   = _MockArticle(title=headline, description=description)
    extracted = extract_event(article)

    impact_per_asset = _compute_impact_per_asset(extracted)

    asset_impact: dict | None = None
    if asset:
        asset_impact = impact_per_asset.get(asset.upper())

    result: dict = {
        "headline":            headline,
        "extracted_event":     extracted,
        "impact_per_asset":    impact_per_asset,
        "asset_specific_impact": asset_impact,
        "no_event_matched":    extracted is None,
    }

    if scenario_id:
        scenario = get_scenario(scenario_id)
        if scenario:
            coherence = score_economic_coherence(extracted or {}, scenario["expected"])
            result["scenario_comparison"] = {
                "scenario_id":      scenario_id,
                "scenario_name":    scenario["name"],
                "expected":         scenario["expected"],
                "economic_coherence": coherence,
            }
        else:
            result["scenario_comparison"] = {
                "error": f"Scenario {scenario_id!r} not found",
            }

    return result


# ── Internal helpers ──────────────────────────────────────────────────────────

def _compute_impact_per_asset(extracted: dict | None) -> dict[str, dict]:
    """Return per-tracked-asset impact dict from an extracted event."""
    if not extracted:
        return {}
    result: dict[str, dict] = {}
    for asset_code in (extracted.get("affected_assets") or []):
        tracked = ASSET_CODE_MAP.get(asset_code)
        if tracked:
            sc  = compute_impact_score(extracted["sentiment"], extracted["importance"])
            dir = "bullish" if sc > 0 else "bearish" if sc < 0 else "neutral"
            result[tracked] = {
                "score":      sc,
                "direction":  dir,
                "sentiment":  extracted["sentiment"],
                "importance": extracted["importance"],
            }
    return result


def _build_synthetic_signal(extracted: dict | None) -> dict:
    """Construct a plausible signal dict from an extracted event.

    Assumes aligned TA confirmation (RSI + EMA in the same direction as the
    event) to produce the cleanest BUY/SELL/HOLD for metric scoring.
    """
    now = datetime.utcnow().isoformat()

    if not extracted:
        return {
            "asset":        "TEST",
            "signal":       "HOLD",
            "confidence":   50.0,
            "risk_level":   "medium",
            "time_horizon": "swing",
            "reasoning": [
                "No significant news-driven impact detected",
                "Signal held: no macro/event bias present — awaiting catalyst",
            ],
            "generated_at": now,
            "event_ids":    [],
        }

    sentiment  = extracted.get("sentiment", "neutral")
    importance = extracted.get("importance", "medium")

    impact_score = compute_impact_score(sentiment, importance)
    event_boost  = {
        "high":   15.0,
        "medium":  8.0,
        "low":     4.0,
    }.get(importance, 8.0)

    base     = 50.0
    reasoning: list[str] = []

    if sentiment == "risk_on":
        base += event_boost
        reasoning.append(
            f"News/event flow is bullish (impact score: +{impact_score})"
        )
        base += 10.0   # RSI oversold
        reasoning.append("RSI oversold at 32.0 — potential reversal upward")
        base += 7.0    # EMA bullish
        reasoning.append("Price above EMA — bullish structure")
    elif sentiment == "risk_off":
        base -= event_boost
        reasoning.append(
            f"News/event flow is bearish (impact score: {impact_score})"
        )
        base -= 10.0   # RSI overbought
        reasoning.append("RSI overbought at 72.0 — caution, may pull back")
        base -= 7.0    # EMA bearish
        reasoning.append("Price below EMA — bearish structure")
    else:
        reasoning.append("No significant news-driven impact detected")
        reasoning.append("Signal held: no macro/event bias present — awaiting catalyst")

    base = max(5.0, min(95.0, base))

    if sentiment == "risk_on" and base >= 62:
        signal = "BUY"
    elif sentiment == "risk_off" and base <= 38:
        signal = "SELL"
    else:
        signal = "HOLD"

    asset = (extracted.get("affected_assets") or ["TEST"])[0]

    return {
        "asset":        asset,
        "signal":       signal,
        "confidence":   round(base, 1),
        "risk_level":   "medium",
        "time_horizon": "swing",
        "reasoning":    reasoning,
        "generated_at": now,
        "event_ids":    [],
    }
