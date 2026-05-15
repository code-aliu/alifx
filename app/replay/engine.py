"""
Historical replay engine.

For each scenario, the engine:
  1. Extracts an event from the scenario headline
  2. Computes impact scores per affected tracked asset
  3. Runs full TA analysis on current price bars
  4. Calls generate_signal() with the event impact + TA
  5. Simulates a price outcome using recent bar movement
  6. Returns a structured replay report

This gives a "what would the system have done?" answer for each pre-defined
market event type, bounded by data already in the database.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.orm import Session

from app.reasoning.scenarios import SCENARIOS, get_scenario, list_scenarios
from app.events.extractor import extract_event
from app.impact.rules import compute_impact_score, ASSET_CODE_MAP, SENTIMENT_DIRECTION
from app.analysis.service import analyse_asset
from app.signals.generator import generate_signal
from app.market_data.service import get_latest_prices, get_price_history
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class _MockArticle:
    title: str
    description: str = ""
    id: int | None = None


# ── Public API ────────────────────────────────────────────────────────────────

def run_scenario_replay(scenario_id: str, db: Session) -> dict:
    """Run a single scenario through extraction → signal → simulated outcome."""
    scenario = get_scenario(scenario_id)
    if not scenario:
        return {"error": "scenario_not_found", "scenario_id": scenario_id}

    article   = _MockArticle(title=scenario["headline"])
    extracted = extract_event(article)

    if not extracted:
        return {
            "scenario":        _scenario_meta(scenario),
            "extracted_event": None,
            "result":          "no_event_extracted",
            "signal_results":  [],
            "summary":         {"assets_analyzed": 0, "directional_accuracy_pct": 0},
        }

    expected      = scenario["expected"]
    impact_map    = _build_impact_map(extracted)
    latest_prices = {p["symbol"]: p["close"] for p in get_latest_prices(db)}

    signal_results: list[dict] = []

    for asset_code in (extracted.get("affected_assets") or []):
        tracked = ASSET_CODE_MAP.get(asset_code)
        if not tracked:
            continue
        current_price = latest_prices.get(tracked)
        if not current_price:
            continue

        impact   = impact_map.get(tracked)
        analysis = analyse_asset(db, tracked)

        signal = generate_signal(
            symbol=tracked,
            impact=impact,
            analysis=analysis,
            current_price=current_price,
        )
        if not signal:
            continue

        expected_bias    = expected.get("directional_bias")
        signal_dir       = signal["signal"]
        directional_match = _direction_matches(signal_dir, expected_bias)
        simulated_outcome = _simulate_outcome(signal_dir, db, tracked)

        signal_results.append({
            "asset":              tracked,
            "signal":             signal_dir,
            "confidence":         signal["confidence"],
            "expected_bias":      expected_bias,
            "directional_match":  directional_match,
            "simulated_outcome":  simulated_outcome,
            "entry_price":        current_price,
            "stop_loss":          signal.get("stop_loss"),
            "take_profit":        signal.get("take_profit"),
            "reasoning":          signal["reasoning"],
        })

    total   = len(signal_results)
    matches = sum(1 for r in signal_results if r["directional_match"])
    wins    = sum(1 for r in signal_results if r["simulated_outcome"] == "win")

    return {
        "scenario":        _scenario_meta(scenario),
        "extracted_event": extracted,
        "expected":        expected,
        "signal_results":  signal_results,
        "summary": {
            "assets_analyzed":          total,
            "directional_matches":      matches,
            "directional_accuracy_pct": round(matches / total * 100, 1) if total else 0.0,
            "simulated_wins":           wins,
            "simulated_win_pct":        round(wins / total * 100, 1) if total else 0.0,
        },
        "replayed_at": datetime.utcnow().isoformat(),
    }


def run_all_scenarios(db: Session) -> dict:
    """Run all 11 scenarios and return aggregated results."""
    results   = []
    total_acc = []

    for scenario in SCENARIOS:
        result = run_scenario_replay(scenario["id"], db)
        summary = result.get("summary", {})
        results.append({
            "scenario_id":   scenario["id"],
            "scenario_name": scenario["name"],
            "event_type":    scenario["event_type"],
            "extracted":     result.get("extracted_event") is not None,
            "assets_analyzed": summary.get("assets_analyzed", 0),
            "directional_accuracy_pct": summary.get("directional_accuracy_pct", 0),
            "simulated_win_pct": summary.get("simulated_win_pct", 0),
        })
        if summary.get("assets_analyzed", 0) > 0:
            total_acc.append(summary.get("directional_accuracy_pct", 0))

    extracted_count = sum(1 for r in results if r["extracted"])
    avg_accuracy    = round(sum(total_acc) / len(total_acc), 1) if total_acc else 0.0

    return {
        "total_scenarios":          len(SCENARIOS),
        "scenarios_extracted":      extracted_count,
        "extraction_rate_pct":      round(extracted_count / len(SCENARIOS) * 100, 1),
        "avg_directional_accuracy": avg_accuracy,
        "results":                  results,
        "replayed_at":              datetime.utcnow().isoformat(),
    }


def list_replay_scenarios() -> list[dict]:
    return list_scenarios()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _scenario_meta(scenario: dict) -> dict:
    return {
        "id":          scenario["id"],
        "name":        scenario["name"],
        "event_type":  scenario["event_type"],
        "headline":    scenario["headline"],
    }


def _build_impact_map(extracted: dict) -> dict[str, dict]:
    """Build {tracked_symbol: impact_dict} for generate_signal()."""
    score = compute_impact_score(extracted["sentiment"], extracted["importance"])
    direction = (
        "bullish" if score > 0 else
        "bearish" if score < 0 else
        "neutral"
    )
    strength = abs(score) / 3.0  # normalise: max weight=3

    impact = {"score": score, "direction": direction, "strength": strength}
    result = {}
    for asset_code in (extracted.get("affected_assets") or []):
        tracked = ASSET_CODE_MAP.get(asset_code)
        if tracked:
            result[tracked] = impact
    return result


def _direction_matches(signal_dir: str, expected_bias: str | None) -> bool:
    mapping = {"bullish": "BUY", "bearish": "SELL", "neutral": "HOLD"}
    return signal_dir == mapping.get(expected_bias or "neutral", "HOLD")


def _simulate_outcome(
    signal_dir: str,
    db: Session,
    asset: str,
    n_context: int = 40,
    n_forward: int = 10,
) -> str:
    """Estimate outcome by splitting recent bars into context vs. forward windows.

    Context bars → used to generate the signal (TA).
    Forward bars → what actually happened afterwards (used for outcome).

    If fewer than n_context + n_forward bars exist, returns "unknown".
    """
    bars = get_price_history(db, asset, limit=n_context + n_forward)
    if len(bars) < n_context + 5:
        return "unknown"

    # Forward window = last n_forward bars
    forward = bars[-n_forward:]
    if not forward:
        return "unknown"

    start = forward[0]["close"]
    end   = forward[-1]["close"]
    pct   = (end - start) / start * 100 if start else 0.0

    if signal_dir == "BUY":
        return "win" if pct >= 1.0 else "loss" if pct <= -1.0 else "neutral"
    if signal_dir == "SELL":
        return "win" if pct <= -1.0 else "loss" if pct >= 1.0 else "neutral"
    return "neutral"
