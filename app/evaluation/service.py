"""
Intelligence Usefulness Evaluation Service.

Orchestrates all evaluation dimensions into a unified intelligence quality report.

Dimensions and weights:
  reasoning_quality   25%  — how well scenarios are handled (replay benchmark avg)
  explainability      20%  — coherence + actionability + conciseness + financial meaning
  timing              20%  — how early signals arrived relative to price moves
  calibration         20%  — how well confidence tracks actual win rates
  signal_utility      15%  — false-positive rate, HOLD accuracy, stale ratio

Overall score 0–100. Missing data for a dimension defaults to a neutral 50.

Also computes:
  - best_performing_reasoning_types : categories with highest benchmark scores
  - weakest_reasoning_categories    : categories that need improvement
  - most_reliable_assets            : assets with best explainability + performance
  - confidence_reliability_trend    : calibration buckets showing confidence accuracy
  - regime_performance              : win rate and signal count per market regime
"""
from __future__ import annotations
import statistics
from datetime import datetime
from sqlalchemy.orm import Session

from app.evaluation.metrics              import compute_signal_utility
from app.evaluation.timing               import compute_timing_quality
from app.evaluation.explainability_scorer import compute_explainability_summary
from app.evaluation.benchmarks           import run_benchmark_suite
from app.performance.service             import get_signal_performance
from app.signal_tracking.models          import SignalOutcome
from app.core.logging                    import get_logger

logger = get_logger(__name__)

_WEIGHTS = {
    "reasoning":     0.25,
    "explainability": 0.20,
    "timing":         0.20,
    "calibration":    0.20,
    "utility":        0.15,
}


def get_evaluation_summary(db: Session, run_benchmarks: bool = False) -> dict:
    """
    Full intelligence quality evaluation.

    run_benchmarks=True adds the replay scenario suite (adds ~1–2s).
    The summary endpoint omits benchmarks by default for speed;
    the dedicated /evaluation/benchmarks endpoint always runs them.
    """
    utility       = compute_signal_utility(db)
    timing        = compute_timing_quality(db)
    explainability = compute_explainability_summary(db)
    performance   = get_signal_performance(db)
    benchmarks    = run_benchmark_suite(db) if run_benchmarks else None
    regime_perf   = _regime_performance(db)

    reasoning_score = (benchmarks["avg_reasoning_score"] if benchmarks and benchmarks["avg_reasoning_score"] is not None else 50.0)
    timing_score    = timing["avg_timing_score"] if timing["avg_timing_score"] is not None else 50.0
    expl_score      = explainability["avg_composite"]
    cal_score       = utility["calibration_score"]

    # Utility score: low false-positive + high HOLD accuracy = good
    fp_penalty   = utility["false_positive_rate"]   # lower is better
    hold_bonus   = utility["hold_accuracy"]          # higher is better
    utility_score = round((100 - fp_penalty) * 0.5 + hold_bonus * 0.5, 1)

    overall = round(
        reasoning_score     * _WEIGHTS["reasoning"]     +
        expl_score          * _WEIGHTS["explainability"] +
        timing_score        * _WEIGHTS["timing"]         +
        cal_score           * _WEIGHTS["calibration"]    +
        utility_score       * _WEIGHTS["utility"],
        1,
    )

    # Asset reliability: combine explainability top_assets with perf by_asset
    perf_by_asset = {
        a["asset"]: a for a in performance.get("by_asset", [])
    } if performance else {}

    top_expl_assets = {a["asset"]: a["score"] for a in explainability["top_assets"]}
    reliable_assets = [
        {
            "asset":           asset,
            "explainability":  score,
            "win_rate":        perf_by_asset.get(asset, {}).get("win_rate_pct"),
            "total_signals":   perf_by_asset.get(asset, {}).get("total_signals"),
        }
        for asset, score in top_expl_assets.items()
    ]

    return {
        "overall_quality_score":  overall,
        "evaluated_at":           datetime.utcnow().isoformat(),
        "data_coverage": {
            "total_signals":      utility["total_signals"],
            "directional_signals": utility["directional_signals"],
            "hold_signals":       utility["hold_signals"],
        },
        "dimensions": {
            "reasoning_quality":  _dim(reasoning_score,  "How well the system handles known market scenarios"),
            "explainability":     _dim(expl_score,        "Coherence, actionability, and financial meaning of explanations"),
            "timing":             _dim(timing_score,      "How early signals arrived relative to expected moves"),
            "calibration":        _dim(cal_score,         "How well confidence levels predict actual win rates"),
            "signal_utility":     _dim(utility_score,     "False-positive rate and HOLD accuracy combined"),
        },
        "signal_utility":          utility,
        "timing":                  timing,
        "explainability":          explainability,
        "regime_performance":      regime_perf,
        "most_reliable_assets":    reliable_assets,
        "confidence_reliability":  utility["confidence_calibration"],
        "benchmarks":              benchmarks,
    }


def get_reasoning_quality(db: Session) -> dict:
    """Run the full benchmark suite and return reasoning quality breakdown."""
    benchmarks = run_benchmark_suite(db)
    return {
        "avg_reasoning_score":          benchmarks["avg_reasoning_score"],
        "direction_match_rate":         benchmarks["direction_match_rate"],
        "avg_directional_accuracy_pct": benchmarks["avg_directional_accuracy_pct"],
        "strongest_categories":         benchmarks["strongest_categories"],
        "weakest_categories":           benchmarks["weakest_categories"],
        "category_scores":              benchmarks["category_scores"],
        "scenarios":                    benchmarks["scenarios"],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dim(score: float, description: str) -> dict:
    return {
        "score":       round(score, 1),
        "grade":       _grade(score),
        "description": description,
    }


def _grade(score: float) -> str:
    if score >= 80: return "A"
    if score >= 65: return "B"
    if score >= 50: return "C"
    if score >= 35: return "D"
    return "F"


def _regime_performance(db: Session) -> list[dict]:
    """Win rate and signal count broken down by market regime at signal creation."""
    outcomes = db.query(SignalOutcome).all()
    regimes: dict[str, dict] = {}

    for o in outcomes:
        regime = o.market_regime or "unknown"
        if regime not in regimes:
            regimes[regime] = {"wins": 0, "losses": 0, "total": 0}
        regimes[regime]["total"] += 1
        if o.outcome == "win":
            regimes[regime]["wins"] += 1
        elif o.outcome == "loss":
            regimes[regime]["losses"] += 1

    result = []
    for regime, data in sorted(regimes.items(), key=lambda x: x[1]["total"], reverse=True):
        completed = data["wins"] + data["losses"]
        result.append({
            "regime":       regime,
            "total_signals": data["total"],
            "wins":          data["wins"],
            "losses":        data["losses"],
            "win_rate":      round(data["wins"] / completed * 100, 1) if completed else None,
        })
    return result
