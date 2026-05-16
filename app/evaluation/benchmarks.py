"""
Replay benchmark suite.

For each of the 11 predefined market scenarios (CPI, Fed, crypto ETF, earnings,
geopolitical, oil) this module runs:

  1. replay/engine.py  → directional accuracy (did the signal match expected bias?)
  2. reasoning/service → reasoning quality score (5-metric validation)

This separates WHAT the system decided from HOW it reasoned about it.
Both matter for decision-support quality.
"""
from __future__ import annotations
import statistics
from sqlalchemy.orm import Session

from app.replay.engine import run_scenario_replay, list_replay_scenarios
from app.reasoning.service import run_test_scenario
from app.reasoning.scenarios import SCENARIOS
from app.core.logging import get_logger

logger = get_logger(__name__)

_DIRECTION_MAP = {"bullish": "BUY", "bearish": "SELL", "neutral": "HOLD"}


def run_benchmark_suite(db: Session) -> dict:
    """
    Run all replay scenarios + reasoning validation and compile a structured report.
    Returns aggregate scores and per-scenario breakdown.
    """
    results = []

    for scenario in SCENARIOS:
        sid = scenario["id"]
        try:
            replay  = run_scenario_replay(sid, db)
            quality = run_test_scenario(sid, db)
            results.append(_format(scenario, replay, quality))

        except Exception as exc:
            logger.warning(f"Benchmark: {sid} failed — {exc}")
            results.append(_failed(scenario))

    matched   = [r for r in results if r["direction_match"]]
    scored    = [r for r in results if r["reasoning_score"] is not None]

    avg_dir_acc = round(
        statistics.mean(r["directional_accuracy_pct"] for r in results
                        if r["directional_accuracy_pct"] is not None), 1
    ) if results else 0.0

    avg_reasoning = round(
        statistics.mean(r["reasoning_score"] for r in scored), 1
    ) if scored else None

    # Category breakdowns
    by_category: dict[str, list] = {}
    for r in results:
        cat = r["category"]
        by_category.setdefault(cat, {"direction": [], "reasoning": []})
        if r["directional_accuracy_pct"] is not None:
            by_category[cat]["direction"].append(r["directional_accuracy_pct"])
        if r["reasoning_score"] is not None:
            by_category[cat]["reasoning"].append(r["reasoning_score"])

    category_scores = {
        cat: {
            "avg_direction_accuracy": round(statistics.mean(v["direction"]), 1) if v["direction"] else None,
            "avg_reasoning_score":    round(statistics.mean(v["reasoning"]), 1) if v["reasoning"] else None,
            "count":                  max(len(v["direction"]), len(v["reasoning"])),
        }
        for cat, v in by_category.items()
    }

    # Strongest / weakest categories by reasoning score
    cat_reasoning = {
        k: v["avg_reasoning_score"]
        for k, v in category_scores.items()
        if v["avg_reasoning_score"] is not None
    }
    sorted_cats = sorted(cat_reasoning.items(), key=lambda x: x[1], reverse=True)

    return {
        "total_scenarios":              len(results),
        "direction_match_count":        len(matched),
        "direction_match_rate":         round(len(matched) / max(len(results), 1) * 100, 1),
        "avg_directional_accuracy_pct": avg_dir_acc,
        "avg_reasoning_score":          avg_reasoning,
        "strongest_categories":         [{"category": k, "score": v} for k, v in sorted_cats[:2]],
        "weakest_categories":           [{"category": k, "score": v} for k, v in sorted_cats[-2:][::-1]],
        "category_scores":              category_scores,
        "scenarios":                    results,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _format(scenario: dict, replay: dict, quality: dict) -> dict:
    expected_bias = scenario["expected"].get("directional_bias", "neutral")
    expected_signal = _DIRECTION_MAP.get(expected_bias, "HOLD")
    summary = replay.get("summary", {})
    assets_analyzed = summary.get("assets_analyzed", 0)

    # Direction match: did most signals match expected bias?
    dir_acc = summary.get("directional_accuracy_pct")
    direction_match = (dir_acc or 0) >= 50

    vr = quality.get("validation_report", {})
    raw_score = vr.get("overall_score")
    reasoning_score = round(raw_score * 100, 1) if raw_score is not None else None
    metrics_passed = vr.get("metrics_passed")

    # Build readable comparison table
    signal_results = replay.get("signal_results", [])
    comparison = [
        {
            "asset":            r["asset"],
            "expected":         expected_signal,
            "system_signal":    r["signal"],
            "match":            r["directional_match"],
            "confidence":       r["confidence"],
            "simulated_outcome": r.get("simulated_outcome"),
        }
        for r in signal_results
    ]

    return {
        "scenario_id":             scenario["id"],
        "name":                    scenario["name"],
        "category":                scenario["event_type"],
        "headline":                scenario["headline"],
        "expected_direction":      expected_signal,
        "direction_match":         direction_match,
        "directional_accuracy_pct": dir_acc,
        "assets_analyzed":         assets_analyzed,
        "reasoning_score":         reasoning_score,
        "metrics_passed":          metrics_passed,
        "comparison":              comparison,
    }


def _failed(scenario: dict) -> dict:
    return {
        "scenario_id":              scenario["id"],
        "name":                     scenario["name"],
        "category":                 scenario["event_type"],
        "headline":                 scenario["headline"],
        "expected_direction":       "—",
        "direction_match":          False,
        "directional_accuracy_pct": None,
        "assets_analyzed":          0,
        "reasoning_score":          None,
        "metrics_passed":           None,
        "comparison":               [],
    }
