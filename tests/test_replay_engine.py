"""
Historical replay engine tests.

Covers:
  • list_replay_scenarios() — structure and completeness
  • run_scenario_replay() — unknown ID, no-data path, structure
  • _direction_matches() — all combinations
  • _simulate_outcome() — BUY/SELL logic with inserted bars
  • _build_impact_map() — impact dict construction
  • run_all_scenarios() — aggregation structure
"""
from datetime import datetime, timedelta
import pytest

from app.replay.engine import (
    run_scenario_replay,
    run_all_scenarios,
    list_replay_scenarios,
    _direction_matches,
    _simulate_outcome,
    _build_impact_map,
)
from app.market_data.models import PriceBar


# ── Helpers ───────────────────────────────────────────────────────────────────

def _insert_bars(db, symbol: str, prices: list[float]) -> None:
    """Insert a series of price bars for the given symbol."""
    base_time = datetime.utcnow() - timedelta(minutes=len(prices))
    asset_class = "crypto" if symbol in ("BTC", "ETH") else "stock"
    for i, price in enumerate(prices):
        bar = PriceBar(
            symbol=symbol,
            asset_class=asset_class,
            source="test",
            open=price,
            high=price * 1.001,
            low=price * 0.999,
            close=price,
            volume=1000.0,
            fetched_at=base_time + timedelta(minutes=i),
        )
        db.add(bar)
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# list_replay_scenarios
# ═══════════════════════════════════════════════════════════════════════════════

class TestListReplayScenarios:

    def test_returns_list(self):
        scenarios = list_replay_scenarios()
        assert isinstance(scenarios, list)

    def test_returns_11_scenarios(self):
        scenarios = list_replay_scenarios()
        assert len(scenarios) == 11

    def test_each_scenario_has_required_fields(self):
        required = {"id", "name", "event_type", "headline", "description"}
        for s in list_replay_scenarios():
            assert required.issubset(s.keys()), f"Missing fields in scenario {s.get('id')}"

    def test_scenario_ids_are_unique(self):
        ids = [s["id"] for s in list_replay_scenarios()]
        assert len(ids) == len(set(ids))

    def test_expected_has_directional_bias(self):
        from app.reasoning.scenarios import SCENARIOS
        for s in SCENARIOS:
            exp = s["expected"]
            assert "directional_bias" in exp, f"No directional_bias in {s['id']}"
            assert exp["directional_bias"] in ("bullish", "bearish", "neutral")

    def test_known_scenario_ids_present(self):
        ids = {s["id"] for s in list_replay_scenarios()}
        for expected_id in ("cpi_hot", "cpi_cool", "fed_hike", "fed_cut", "btc_etf"):
            assert expected_id in ids


# ═══════════════════════════════════════════════════════════════════════════════
# run_scenario_replay — unknown ID
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunScenarioReplayUnknownId:

    def test_unknown_id_returns_error_dict(self, db):
        result = run_scenario_replay("nonexistent_scenario_xyz", db)
        assert result.get("error") == "scenario_not_found"

    def test_unknown_id_echoes_scenario_id(self, db):
        result = run_scenario_replay("nonexistent_scenario_xyz", db)
        assert result["scenario_id"] == "nonexistent_scenario_xyz"


# ═══════════════════════════════════════════════════════════════════════════════
# run_scenario_replay — structure with minimal data
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunScenarioReplayStructure:

    def test_result_has_required_keys(self, db):
        result = run_scenario_replay("cpi_hot", db)
        required = {"scenario", "signal_results", "summary"}
        assert required.issubset(result.keys())

    def test_scenario_meta_is_populated(self, db):
        result = run_scenario_replay("cpi_hot", db)
        meta = result["scenario"]
        assert meta["id"] == "cpi_hot"
        assert "name" in meta
        assert "headline" in meta

    def test_summary_has_required_keys(self, db):
        result = run_scenario_replay("cpi_hot", db)
        summary = result["summary"]
        assert "assets_analyzed" in summary
        assert "directional_accuracy_pct" in summary

    def test_signal_results_is_list(self, db):
        result = run_scenario_replay("cpi_hot", db)
        assert isinstance(result["signal_results"], list)

    def test_no_price_data_yields_zero_assets(self, db):
        # Without price bars, no signals should be generated
        result = run_scenario_replay("cpi_hot", db)
        assert result["summary"]["assets_analyzed"] == 0

    def test_with_price_bars_may_generate_signals(self, db):
        # Insert enough bars for BTC so the engine can attempt analysis
        prices = list(range(85_000, 85_060))  # 60 bars near flat
        _insert_bars(db, "BTC", [float(p) for p in prices])
        result = run_scenario_replay("btc_etf", db)
        # Result should have valid structure regardless of whether signals fired
        assert isinstance(result["signal_results"], list)
        assert result["summary"]["assets_analyzed"] >= 0


# ═══════════════════════════════════════════════════════════════════════════════
# _direction_matches
# ═══════════════════════════════════════════════════════════════════════════════

class TestDirectionMatches:

    def test_buy_matches_bullish(self):
        assert _direction_matches("BUY", "bullish") is True

    def test_sell_matches_bearish(self):
        assert _direction_matches("SELL", "bearish") is True

    def test_hold_matches_neutral(self):
        assert _direction_matches("HOLD", "neutral") is True

    def test_buy_does_not_match_bearish(self):
        assert _direction_matches("BUY", "bearish") is False

    def test_sell_does_not_match_bullish(self):
        assert _direction_matches("SELL", "bullish") is False

    def test_buy_does_not_match_neutral(self):
        assert _direction_matches("BUY", "neutral") is False

    def test_none_bias_treated_as_neutral(self):
        assert _direction_matches("HOLD", None) is True

    def test_buy_with_none_bias_false(self):
        assert _direction_matches("BUY", None) is False


# ═══════════════════════════════════════════════════════════════════════════════
# _simulate_outcome
# ═══════════════════════════════════════════════════════════════════════════════

class TestSimulateOutcome:

    def test_insufficient_bars_returns_unknown(self, db):
        # Only 10 bars — less than n_context + 5 = 45
        _insert_bars(db, "BTC", [90_000.0] * 10)
        result = _simulate_outcome("BUY", db, "BTC")
        assert result == "unknown"

    def test_buy_win_when_price_rises(self, db):
        # Context bars flat, forward bars rise by >1%
        context = [90_000.0] * 40
        forward = [90_000.0 + (i * 100) for i in range(10)]  # rises ~1000 = ~1.1%
        _insert_bars(db, "BTC", context + forward)
        result = _simulate_outcome("BUY", db, "BTC", n_context=40, n_forward=10)
        assert result == "win"

    def test_buy_loss_when_price_falls(self, db):
        # Forward bars fall by >1%
        context = [90_000.0] * 40
        forward = [90_000.0 - (i * 100) for i in range(10)]  # falls ~900 = ~1%
        _insert_bars(db, "BTC", context + forward)
        result = _simulate_outcome("BUY", db, "BTC", n_context=40, n_forward=10)
        assert result == "loss"

    def test_sell_win_when_price_falls(self, db):
        context = [90_000.0] * 40
        forward = [90_000.0 - (i * 100) for i in range(10)]
        _insert_bars(db, "BTC", context + forward)
        result = _simulate_outcome("SELL", db, "BTC", n_context=40, n_forward=10)
        assert result == "win"

    def test_sell_loss_when_price_rises(self, db):
        context = [90_000.0] * 40
        forward = [90_000.0 + (i * 100) for i in range(10)]
        _insert_bars(db, "BTC", context + forward)
        result = _simulate_outcome("SELL", db, "BTC", n_context=40, n_forward=10)
        assert result == "loss"

    def test_hold_always_neutral(self, db):
        context = [90_000.0] * 40
        forward = [90_000.0 + (i * 200) for i in range(10)]  # strong rally
        _insert_bars(db, "BTC", context + forward)
        result = _simulate_outcome("HOLD", db, "BTC", n_context=40, n_forward=10)
        assert result == "neutral"

    def test_flat_price_buy_returns_neutral(self, db):
        # Flat bars → price change < 1% threshold
        bars = [90_000.0] * 55
        _insert_bars(db, "BTC", bars)
        result = _simulate_outcome("BUY", db, "BTC", n_context=40, n_forward=10)
        assert result == "neutral"


# ═══════════════════════════════════════════════════════════════════════════════
# _build_impact_map
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildImpactMap:

    def test_risk_on_event_bullish_direction(self):
        extracted = {
            "sentiment": "risk_on",
            "importance": "high",
            "affected_assets": ["BTC", "SPY"],
        }
        impact_map = _build_impact_map(extracted)
        for tracked_sym, impact in impact_map.items():
            assert impact["direction"] == "bullish"
            assert impact["score"] > 0

    def test_risk_off_event_bearish_direction(self):
        extracted = {
            "sentiment": "risk_off",
            "importance": "high",
            "affected_assets": ["BTC"],
        }
        impact_map = _build_impact_map(extracted)
        for tracked_sym, impact in impact_map.items():
            assert impact["direction"] == "bearish"
            assert impact["score"] < 0

    def test_unknown_asset_code_skipped(self):
        extracted = {
            "sentiment": "risk_on",
            "importance": "medium",
            "affected_assets": ["UNKNOWN_ASSET_XYZ"],
        }
        impact_map = _build_impact_map(extracted)
        assert len(impact_map) == 0

    def test_empty_assets_returns_empty_map(self):
        extracted = {
            "sentiment": "risk_on",
            "importance": "high",
            "affected_assets": [],
        }
        assert _build_impact_map(extracted) == {}

    def test_strength_is_normalised(self):
        extracted = {
            "sentiment": "risk_on",
            "importance": "high",
            "affected_assets": ["BTC"],
        }
        impact_map = _build_impact_map(extracted)
        for impact in impact_map.values():
            assert 0.0 <= impact["strength"] <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# run_all_scenarios
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunAllScenarios:

    def test_result_has_required_keys(self, db):
        result = run_all_scenarios(db)
        required = {
            "total_scenarios", "scenarios_extracted",
            "extraction_rate_pct", "avg_directional_accuracy", "results",
        }
        assert required.issubset(result.keys())

    def test_total_scenarios_is_11(self, db):
        result = run_all_scenarios(db)
        assert result["total_scenarios"] == 11

    def test_results_list_matches_scenario_count(self, db):
        result = run_all_scenarios(db)
        assert len(result["results"]) == 11

    def test_extraction_rate_is_percentage(self, db):
        result = run_all_scenarios(db)
        rate = result["extraction_rate_pct"]
        assert 0.0 <= rate <= 100.0

    def test_each_result_has_required_fields(self, db):
        result = run_all_scenarios(db)
        required = {"scenario_id", "scenario_name", "extracted", "assets_analyzed"}
        for r in result["results"]:
            assert required.issubset(r.keys())

    def test_extracted_is_boolean(self, db):
        result = run_all_scenarios(db)
        for r in result["results"]:
            assert isinstance(r["extracted"], bool)
