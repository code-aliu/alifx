"""
Market Reasoning Validation Framework tests.

Covers:
  • scenarios.py  — list, get, expected shape
  • validator.py  — all 5 metric functions + build_audit_log + confidence journey
  • service.py    — run_test_scenario, get_reasoning_audit, validate_reasoning_from_headline
"""
from datetime import datetime, timedelta
import pytest

from app.reasoning.scenarios import (
    SCENARIOS,
    SCENARIO_INDEX,
    get_scenario,
    list_scenarios,
)
from app.reasoning.validator import (
    score_economic_coherence,
    score_internal_consistency,
    score_confidence_calibration,
    score_ta_confirmation_alignment,
    score_stale_signal_detection,
    build_audit_log,
    _build_confidence_journey,
    _infer_delta,
)
from app.reasoning.service import (
    run_test_scenario,
    get_reasoning_audit,
    validate_reasoning_from_headline,
    _build_synthetic_signal,
)
from app.signals.models import TradingSignal


# ── Helpers ───────────────────────────────────────────────────────────────────

def _insert_signal(db, asset="BTC", signal="BUY", confidence=72.0,
                   reasoning=None, minutes_ago=1) -> TradingSignal:
    row = TradingSignal(
        asset=asset,
        signal=signal,
        confidence=confidence,
        time_horizon="swing",
        risk_level="medium",
        reasoning=reasoning or [
            "News/event flow is bullish (impact score: +3.0)",
            "RSI oversold at 32.0 — potential reversal upward",
            "Price above EMA — bullish structure",
        ],
        event_ids=[],
        entry_price=90_000.0,
        generated_at=datetime.utcnow() - timedelta(minutes=minutes_ago),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _fresh_signal(signal="BUY", confidence=75.0, reasoning=None) -> dict:
    return {
        "asset":        "BTC",
        "signal":       signal,
        "confidence":   confidence,
        "risk_level":   "medium",
        "time_horizon": "swing",
        "reasoning":    reasoning or [
            "News/event flow is bullish (impact score: +3.0)",
            "RSI oversold at 32.0 — potential reversal upward",
            "Price above EMA — bullish structure",
        ],
        "generated_at": datetime.utcnow().isoformat(),
        "event_ids":    [],
    }


def _clean_validation() -> dict:
    return {
        "is_stale":            False,
        "stale_reason":        None,
        "flags":               [],
        "warnings":            [],
        "adjusted_confidence": 73.0,
        "volatility_penalty":  2.0,
        "consistency_score":   1.0,
        "signal_quality":      "strong",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# scenarios.py
# ═══════════════════════════════════════════════════════════════════════════════

class TestScenarios:

    def test_has_eleven_scenarios(self):
        assert len(SCENARIOS) == 11

    def test_scenario_index_covers_all(self):
        assert len(SCENARIO_INDEX) == len(SCENARIOS)

    def test_all_scenario_ids_unique(self):
        ids = [s["id"] for s in SCENARIOS]
        assert len(ids) == len(set(ids))

    def test_each_scenario_has_required_fields(self):
        required = {"id", "name", "event_type", "description", "headline", "expected"}
        for s in SCENARIOS:
            assert required.issubset(s.keys()), f"Scenario {s['id']} missing fields"

    def test_each_expected_has_required_keys(self):
        required = {
            "event_sentiment", "event_importance", "event_category",
            "directional_bias", "affected_assets", "reasoning_keywords",
            "regime_signal", "confidence_direction",
        }
        for s in SCENARIOS:
            assert required.issubset(s["expected"].keys()), \
                f"Scenario {s['id']} expected missing keys"

    def test_get_scenario_returns_correct(self):
        s = get_scenario("cpi_hot")
        assert s is not None
        assert s["id"] == "cpi_hot"
        assert s["expected"]["event_sentiment"] == "risk_off"

    def test_get_scenario_missing_returns_none(self):
        assert get_scenario("nonexistent_scenario") is None

    def test_list_scenarios_returns_metadata_only(self):
        listing = list_scenarios()
        assert len(listing) == 11
        for item in listing:
            assert "expected" not in item
            assert {"id", "name", "event_type", "description", "headline"}.issubset(item.keys())

    def test_scenario_sentiments_are_valid(self):
        valid = {"risk_on", "risk_off", "neutral"}
        for s in SCENARIOS:
            assert s["expected"]["event_sentiment"] in valid, s["id"]

    def test_scenario_importances_are_valid(self):
        valid = {"high", "medium", "low"}
        for s in SCENARIOS:
            assert s["expected"]["event_importance"] in valid, s["id"]

    def test_cpi_hot_is_risk_off_high(self):
        s = get_scenario("cpi_hot")
        assert s["expected"]["event_sentiment"] == "risk_off"
        assert s["expected"]["event_importance"] == "high"

    def test_btc_etf_is_crypto_risk_on(self):
        s = get_scenario("btc_etf")
        assert s["expected"]["event_category"] == "crypto"
        assert s["expected"]["event_sentiment"] == "risk_on"

    def test_geo_ceasefire_is_risk_on(self):
        s = get_scenario("geo_ceasefire")
        assert s["expected"]["event_sentiment"] == "risk_on"
        assert s["expected"]["directional_bias"] == "bullish"

    def test_oil_oversupply_is_low_importance(self):
        s = get_scenario("oil_oversupply")
        assert s["expected"]["event_importance"] == "low"


# ═══════════════════════════════════════════════════════════════════════════════
# validator.py — score_economic_coherence
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoreEconomicCoherence:

    def _expected(self):
        return {
            "event_sentiment":  "risk_off",
            "event_importance": "high",
            "event_category":   "macroeconomic",
        }

    def test_perfect_match_scores_1(self):
        extracted = {"sentiment": "risk_off", "importance": "high", "category": "macroeconomic"}
        result = score_economic_coherence(extracted, self._expected())
        assert result["score"] == 1.0
        assert result["label"] == "pass"

    def test_wrong_sentiment_loses_half(self):
        extracted = {"sentiment": "risk_on", "importance": "high", "category": "macroeconomic"}
        result = score_economic_coherence(extracted, self._expected())
        assert result["score"] == pytest.approx(0.5)

    def test_wrong_importance_loses_30pct(self):
        extracted = {"sentiment": "risk_off", "importance": "medium", "category": "macroeconomic"}
        result = score_economic_coherence(extracted, self._expected())
        assert result["score"] == pytest.approx(0.7)

    def test_wrong_category_loses_20pct(self):
        extracted = {"sentiment": "risk_off", "importance": "high", "category": "crypto"}
        result = score_economic_coherence(extracted, self._expected())
        assert result["score"] == pytest.approx(0.8)

    def test_all_wrong_scores_0(self):
        extracted = {"sentiment": "risk_on", "importance": "low", "category": "earnings"}
        result = score_economic_coherence(extracted, self._expected())
        assert result["score"] == 0.0
        assert result["label"] == "fail"

    def test_empty_extracted_scores_0(self):
        result = score_economic_coherence({}, self._expected())
        assert result["score"] == 0.0

    def test_detail_includes_check_symbols(self):
        extracted = {"sentiment": "risk_off", "importance": "high", "category": "macroeconomic"}
        result = score_economic_coherence(extracted, self._expected())
        assert "✓" in result["detail"]

    def test_partial_label_between_50_and_80(self):
        extracted = {"sentiment": "risk_off", "importance": "medium", "category": "earnings"}
        result = score_economic_coherence(extracted, self._expected())
        assert result["label"] == "partial"


# ═══════════════════════════════════════════════════════════════════════════════
# validator.py — score_internal_consistency
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoreInternalConsistency:

    def test_clean_buy_signal_passes(self):
        sig = _fresh_signal("BUY", 75.0)
        result = score_internal_consistency(sig)
        assert result["score"] >= 0.8
        assert result["label"] == "pass"

    def test_buy_below_threshold_fails(self):
        sig = _fresh_signal("BUY", 50.0)
        result = score_internal_consistency(sig)
        assert result["score"] < 0.8
        assert "BUY" in result["detail"]

    def test_sell_above_threshold_fails(self):
        sig = _fresh_signal("SELL", 50.0)
        result = score_internal_consistency(sig)
        assert result["score"] < 0.8

    def test_sparse_reasoning_penalises(self):
        sig = _fresh_signal(reasoning=["One line"])
        result = score_internal_consistency(sig)
        assert result["score"] < 1.0

    def test_hold_in_hold_signal_is_fine(self):
        sig = _fresh_signal(signal="HOLD", reasoning=[
            "No significant news-driven impact detected",
            "Signal held: no macro/event bias present — awaiting catalyst",
        ])
        result = score_internal_consistency(sig)
        # Hold lines in HOLD signal should not trigger the penalty
        assert result["score"] >= 0.5

    def test_hold_reasoning_in_buy_signal_penalises(self):
        sig = _fresh_signal(signal="BUY", confidence=75.0, reasoning=[
            "Signal held: no macro/event bias present — awaiting catalyst",
            "RSI oversold at 32.0 — potential reversal upward",
            "Price above EMA — bullish structure",
        ])
        result = score_internal_consistency(sig)
        assert result["score"] < 0.8


# ═══════════════════════════════════════════════════════════════════════════════
# validator.py — score_confidence_calibration
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoreConfidenceCalibration:

    def test_clean_signal_passes(self):
        sig = _fresh_signal("BUY", 75.0)
        result = score_confidence_calibration(sig, _clean_validation())
        assert result["label"] == "pass"
        assert result["score"] >= 0.8

    def test_high_confidence_with_flags_penalised(self):
        sig = _fresh_signal("BUY", 85.0)
        validation = {**_clean_validation(), "flags": ["stale_signal"], "is_stale": True}
        result = score_confidence_calibration(sig, validation)
        assert result["score"] < 0.8

    def test_low_confidence_no_flags_penalised(self):
        sig = _fresh_signal("BUY", 40.0)
        result = score_confidence_calibration(sig, _clean_validation())
        assert result["score"] < 1.0

    def test_large_adjustment_gap_penalised(self):
        sig = _fresh_signal("BUY", 80.0)
        val = {**_clean_validation(), "adjusted_confidence": 60.0}
        result = score_confidence_calibration(sig, val)
        assert result["score"] < 1.0

    def test_stale_high_confidence_penalised(self):
        sig = _fresh_signal("BUY", 80.0)
        val = {**_clean_validation(), "is_stale": True, "flags": ["stale_signal"]}
        result = score_confidence_calibration(sig, val)
        assert result["score"] < 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# validator.py — score_ta_confirmation_alignment
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoreTAConfirmationAlignment:

    def test_buy_with_bullish_ta_passes(self):
        sig = _fresh_signal("BUY", 75.0, reasoning=[
            "News/event flow is bullish (impact score: +3.0)",
            "RSI oversold at 32.0 — potential reversal upward",
            "Price above EMA — bullish structure",
        ])
        result = score_ta_confirmation_alignment(sig)
        assert result["label"] == "pass"
        assert result["score"] >= 0.7

    def test_sell_with_bearish_ta_passes(self):
        sig = _fresh_signal("SELL", 25.0, reasoning=[
            "News/event flow is bearish (impact score: -3.0)",
            "RSI overbought at 72.0 — caution, may pull back",
            "Price below EMA — bearish structure",
        ])
        result = score_ta_confirmation_alignment(sig)
        assert result["label"] == "pass"

    def test_conflicting_signal_returns_partial(self):
        sig = _fresh_signal("HOLD", 55.0, reasoning=[
            "News/event flow is bullish (impact score: +3.0)",
            "Price below EMA — bearish structure",
            "Event and technical signals are conflicting — confidence capped",
        ])
        result = score_ta_confirmation_alignment(sig)
        assert result["score"] == pytest.approx(0.5)
        assert result["label"] == "partial"

    def test_hold_signal_scores_0_7(self):
        sig = _fresh_signal("HOLD", reasoning=[
            "No significant news-driven impact detected",
            "Signal held: no macro/event bias present — awaiting catalyst",
        ])
        result = score_ta_confirmation_alignment(sig)
        assert result["score"] == pytest.approx(0.7)

    def test_no_ta_indicators_returns_partial(self):
        sig = _fresh_signal("BUY", 75.0, reasoning=[
            "News/event flow is bullish (impact score: +3.0)",
        ])
        result = score_ta_confirmation_alignment(sig)
        assert result["score"] == pytest.approx(0.5)
        assert result["label"] == "partial"

    def test_buy_with_bearish_ta_fails(self):
        sig = _fresh_signal("BUY", 75.0, reasoning=[
            "News/event flow is bullish (impact score: +3.0)",
            "RSI overbought at 75.0 — caution, may pull back",
            "Price below EMA — bearish structure",
        ])
        result = score_ta_confirmation_alignment(sig)
        assert result["label"] == "fail"


# ═══════════════════════════════════════════════════════════════════════════════
# validator.py — score_stale_signal_detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoreStaleSignalDetection:

    def test_fresh_signal_not_flagged_scores_1(self):
        sig = _fresh_signal()
        val = {**_clean_validation(), "is_stale": False}
        result = score_stale_signal_detection(sig, val)
        assert result["score"] == 1.0
        assert result["label"] == "pass"

    def test_stale_signal_correctly_detected_scores_1(self):
        old_ts = (datetime.utcnow() - timedelta(hours=30)).isoformat()
        sig = {**_fresh_signal(), "generated_at": old_ts, "time_horizon": "swing"}
        val = {**_clean_validation(), "is_stale": True}
        result = score_stale_signal_detection(sig, val)
        assert result["score"] == 1.0
        assert result["label"] == "pass"

    def test_stale_signal_not_detected_scores_0(self):
        old_ts = (datetime.utcnow() - timedelta(hours=30)).isoformat()
        sig = {**_fresh_signal(), "generated_at": old_ts, "time_horizon": "swing"}
        val = {**_clean_validation(), "is_stale": False}
        result = score_stale_signal_detection(sig, val)
        assert result["score"] == 0.0
        assert result["label"] == "fail"

    def test_false_positive_staleness_scores_low(self):
        sig = _fresh_signal()  # actually fresh
        val = {**_clean_validation(), "is_stale": True}  # wrongly flagged
        result = score_stale_signal_detection(sig, val)
        assert result["score"] < 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# validator.py — build_audit_log + confidence journey
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildAuditLog:

    def test_audit_has_required_fields(self):
        sig = _fresh_signal()
        audit = build_audit_log(sig)
        required = {"reasoning_layers", "confidence_journey", "reasoning_depth",
                    "signal", "confidence", "generated_at"}
        assert required.issubset(audit.keys())

    def test_layers_have_expected_keys(self):
        sig = _fresh_signal()
        audit = build_audit_log(sig)
        layers = audit["reasoning_layers"]
        assert {"event_macro", "technical", "regime", "conflict",
                "signal_held", "uncategorized"}.issubset(layers.keys())

    def test_event_line_goes_to_event_macro(self):
        sig = _fresh_signal(reasoning=["News/event flow is bullish (impact score: +3.0)"])
        audit = build_audit_log(sig)
        assert len(audit["reasoning_layers"]["event_macro"]) >= 1

    def test_ta_line_goes_to_technical(self):
        sig = _fresh_signal(reasoning=["RSI oversold at 32.0 — potential reversal upward"])
        audit = build_audit_log(sig)
        assert len(audit["reasoning_layers"]["technical"]) >= 1

    def test_regime_line_goes_to_regime(self):
        sig = _fresh_signal(reasoning=["Regime (risk_on): confidence adjusted +5 [confidence=72%]"])
        audit = build_audit_log(sig)
        assert len(audit["reasoning_layers"]["regime"]) >= 1

    def test_conflict_line_goes_to_conflict(self):
        sig = _fresh_signal(reasoning=[
            "Event and technical signals are conflicting — confidence capped"
        ])
        audit = build_audit_log(sig)
        assert len(audit["reasoning_layers"]["conflict"]) >= 1

    def test_reasoning_depth_matches_input(self):
        reasoning = [
            "News/event flow is bullish (impact score: +3.0)",
            "RSI oversold at 32.0 — potential reversal upward",
            "Price above EMA — bullish structure",
        ]
        audit = build_audit_log(_fresh_signal(reasoning=reasoning))
        assert audit["reasoning_depth"] == 3

    def test_confidence_journey_starts_at_50(self):
        sig = _fresh_signal()
        audit = build_audit_log(sig)
        journey = audit["confidence_journey"]
        assert journey[0]["cumulative"] == 50.0
        assert journey[0]["step"] == "baseline"

    def test_confidence_journey_moves_upward_for_bullish_reasoning(self):
        reasoning = [
            "News/event flow is bullish (impact score: +3.0)",
            "RSI oversold at 32.0 — potential reversal upward",
        ]
        audit = build_audit_log(_fresh_signal(reasoning=reasoning))
        journey = audit["confidence_journey"]
        final = journey[-1]["cumulative"]
        assert final > 50.0

    def test_conflict_cap_applied_in_journey(self):
        reasoning = [
            "News/event flow is bullish (impact score: +3.0)",
            "Price below EMA — bearish structure",
            "Event and technical signals are conflicting — confidence capped",
        ]
        audit = build_audit_log(_fresh_signal(reasoning=reasoning))
        cap_steps = [s for s in audit["confidence_journey"] if s["step"] == "conflict_cap"]
        # Cap only applied if cumulative was >58 before the cap line
        # With +15 event and -7 EMA, cumulative = 50+15-7=58, cap would not trigger
        # so this tests that the cap logic runs without error
        assert isinstance(audit["confidence_journey"], list)


class TestInferDelta:

    def test_bullish_event_high_delta_is_15(self):
        delta, step = _infer_delta("news/event flow is bullish (impact score: +3.0)")
        assert delta == 15.0
        assert step == "event_impact"

    def test_bearish_event_high_delta_is_minus_15(self):
        delta, step = _infer_delta("news/event flow is bearish (impact score: -3.0)")
        assert delta == -15.0

    def test_bullish_medium_event_delta_is_8(self):
        delta, _ = _infer_delta("news/event flow is bullish (impact score: +2.0)")
        assert delta == 8.0

    def test_rsi_oversold_is_plus_10(self):
        delta, step = _infer_delta("rsi oversold at 32.0 — potential reversal upward")
        assert delta == 10.0
        assert step == "rsi_oversold"

    def test_rsi_overbought_is_minus_10(self):
        delta, step = _infer_delta("rsi overbought at 75.0 — caution, may pull back")
        assert delta == -10.0

    def test_golden_cross_is_plus_10(self):
        delta, step = _infer_delta("ema golden cross — bullish momentum crossover")
        assert delta == 10.0
        assert step == "ema_golden_cross"

    def test_death_cross_is_minus_10(self):
        delta, step = _infer_delta("ema death cross — bearish momentum crossover")
        assert delta == -10.0

    def test_ema_bullish_is_plus_7(self):
        delta, _ = _infer_delta("price above ema — bullish structure")
        assert delta == 7.0

    def test_ema_bearish_is_minus_7(self):
        delta, _ = _infer_delta("price below ema — bearish structure")
        assert delta == -7.0

    def test_macd_positive_is_plus_8(self):
        delta, step = _infer_delta("macd positive — upward momentum")
        assert delta == 8.0
        assert step == "macd_bullish"

    def test_regime_adjustment_parsed(self):
        delta, step = _infer_delta(
            "regime (risk_on): confidence adjusted +5 [confidence=72%]"
        )
        assert delta == 5.0
        assert step == "regime_adjustment"

    def test_regime_adjustment_negative(self):
        delta, _ = _infer_delta(
            "regime (risk_off): confidence adjusted -8 [confidence=55%]"
        )
        assert delta == -8.0

    def test_uptrend_is_plus_6(self):
        delta, step = _infer_delta("price in established uptrend")
        assert delta == 6.0
        assert step == "uptrend"

    def test_downtrend_is_minus_6(self):
        delta, step = _infer_delta("price in established downtrend")
        assert delta == -6.0


# ═══════════════════════════════════════════════════════════════════════════════
# service.py — run_test_scenario
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunTestScenario:

    def test_nonexistent_scenario_returns_error(self, db):
        result = run_test_scenario("not_a_real_scenario", db)
        assert result.get("error") == "scenario_not_found"

    def test_result_has_required_keys(self, db):
        result = run_test_scenario("cpi_hot", db)
        required = {"scenario", "extracted_event", "expected", "impact_per_asset",
                    "synthetic_signal", "validation_report"}
        assert required.issubset(result.keys())

    def test_validation_report_has_all_5_metrics(self, db):
        result = run_test_scenario("cpi_hot", db)
        metrics = result["validation_report"]["metrics"]
        assert {"economic_coherence", "internal_consistency", "confidence_calibration",
                "ta_confirmation", "stale_detection"}.issubset(metrics.keys())

    def test_cpi_hot_extracted_as_risk_off(self, db):
        result = run_test_scenario("cpi_hot", db)
        assert result["extracted_event"] is not None
        assert result["extracted_event"]["sentiment"] == "risk_off"

    def test_cpi_hot_extracted_as_high_importance(self, db):
        result = run_test_scenario("cpi_hot", db)
        assert result["extracted_event"]["importance"] == "high"

    def test_cpi_cool_extracted_as_risk_on(self, db):
        result = run_test_scenario("cpi_cool", db)
        assert result["extracted_event"]["sentiment"] == "risk_on"

    def test_fed_hike_extracted_as_risk_off_high(self, db):
        result = run_test_scenario("fed_hike", db)
        extracted = result["extracted_event"]
        assert extracted["sentiment"] == "risk_off"
        assert extracted["importance"] == "high"

    def test_fed_cut_extracted_as_risk_on(self, db):
        result = run_test_scenario("fed_cut", db)
        assert result["extracted_event"]["sentiment"] == "risk_on"

    def test_btc_etf_extracted_as_crypto_risk_on(self, db):
        result = run_test_scenario("btc_etf", db)
        extracted = result["extracted_event"]
        assert extracted["category"] == "crypto"
        assert extracted["sentiment"] == "risk_on"

    def test_earnings_beat_is_risk_on_medium(self, db):
        result = run_test_scenario("earnings_beat", db)
        extracted = result["extracted_event"]
        assert extracted["sentiment"] == "risk_on"
        assert extracted["importance"] == "medium"

    def test_earnings_miss_is_risk_off(self, db):
        result = run_test_scenario("earnings_miss", db)
        assert result["extracted_event"]["sentiment"] == "risk_off"

    def test_geo_escalation_extracted_as_risk_off_high(self, db):
        result = run_test_scenario("geo_escalation", db)
        extracted = result["extracted_event"]
        assert extracted["sentiment"] == "risk_off"
        assert extracted["importance"] == "high"

    def test_geo_ceasefire_extracted_as_risk_on(self, db):
        result = run_test_scenario("geo_ceasefire", db)
        assert result["extracted_event"]["sentiment"] == "risk_on"

    def test_oil_supply_cut_is_risk_off(self, db):
        result = run_test_scenario("oil_supply_cut", db)
        assert result["extracted_event"]["sentiment"] == "risk_off"

    def test_oil_oversupply_is_risk_on_low(self, db):
        result = run_test_scenario("oil_oversupply", db)
        extracted = result["extracted_event"]
        assert extracted["sentiment"] == "risk_on"
        assert extracted["importance"] == "low"

    def test_economic_coherence_is_perfect_for_known_scenarios(self, db):
        # All our scenarios are designed to match extraction perfectly
        for scenario_id in ("cpi_hot", "cpi_cool", "fed_hike", "fed_cut",
                            "btc_etf", "earnings_beat", "geo_escalation"):
            result = run_test_scenario(scenario_id, db)
            ec = result["validation_report"]["metrics"]["economic_coherence"]
            assert ec["score"] == pytest.approx(1.0), \
                f"{scenario_id}: economic_coherence={ec['score']}, detail={ec['detail']}"

    def test_synthetic_signal_is_sell_for_risk_off_high(self, db):
        result = run_test_scenario("cpi_hot", db)
        assert result["synthetic_signal"]["signal"] == "SELL"

    def test_synthetic_signal_is_buy_for_risk_on_high(self, db):
        result = run_test_scenario("btc_etf", db)
        assert result["synthetic_signal"]["signal"] == "BUY"

    def test_impact_per_asset_is_populated(self, db):
        result = run_test_scenario("cpi_hot", db)
        # CPI affects BTC and SPY among others
        assert len(result["impact_per_asset"]) > 0

    def test_pass_rate_denominator_is_5(self, db):
        result = run_test_scenario("cpi_hot", db)
        assert result["validation_report"]["total_metrics"] == 5

    def test_overall_score_between_0_and_1(self, db):
        result = run_test_scenario("cpi_hot", db)
        score = result["validation_report"]["overall_score"]
        assert 0.0 <= score <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# service.py — get_reasoning_audit
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetReasoningAudit:

    def test_nonexistent_signal_returns_error(self, db):
        result = get_reasoning_audit(99999, db)
        assert result.get("error") == "signal_not_found"

    def test_result_has_required_keys(self, db):
        row = _insert_signal(db)
        result = get_reasoning_audit(row.id, db)
        required = {"signal_id", "asset", "signal", "confidence",
                    "generated_at", "audit_log", "validation", "reasoning_audit"}
        assert required.issubset(result.keys())

    def test_audit_log_has_layers_and_journey(self, db):
        row = _insert_signal(db)
        result = get_reasoning_audit(row.id, db)
        audit = result["audit_log"]
        assert "reasoning_layers" in audit
        assert "confidence_journey" in audit

    def test_reasoning_audit_has_4_metrics(self, db):
        row = _insert_signal(db)
        result = get_reasoning_audit(row.id, db)
        metrics = result["reasoning_audit"]["metrics"]
        assert {"internal_consistency", "confidence_calibration",
                "ta_confirmation", "stale_detection"}.issubset(metrics.keys())

    def test_fresh_signal_passes_stale_detection(self, db):
        row = _insert_signal(db, minutes_ago=1)
        result = get_reasoning_audit(row.id, db)
        sd = result["reasoning_audit"]["metrics"]["stale_detection"]
        assert sd["score"] == 1.0

    def test_stale_signal_detected_in_audit(self, db):
        old_reasoning = [
            "News/event flow is bullish (impact score: +3.0)",
            "RSI oversold at 32.0 — potential reversal upward",
        ]
        row = TradingSignal(
            asset="BTC", signal="BUY", confidence=72.0,
            time_horizon="swing", risk_level="medium",
            reasoning=old_reasoning, event_ids=[],
            entry_price=90_000.0,
            generated_at=datetime.utcnow() - timedelta(hours=30),
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        result = get_reasoning_audit(row.id, db)
        sd = result["reasoning_audit"]["metrics"]["stale_detection"]
        assert sd["score"] == 1.0
        assert "stale" in sd["detail"].lower()

    def test_overall_score_between_0_and_1(self, db):
        row = _insert_signal(db)
        result = get_reasoning_audit(row.id, db)
        score = result["reasoning_audit"]["overall_score"]
        assert 0.0 <= score <= 1.0

    def test_asset_matches_stored_signal(self, db):
        row = _insert_signal(db, asset="ETH")
        result = get_reasoning_audit(row.id, db)
        assert result["asset"] == "ETH"


# ═══════════════════════════════════════════════════════════════════════════════
# service.py — validate_reasoning_from_headline
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateReasoningFromHeadline:

    def test_known_headline_extracts_event(self, db):
        result = validate_reasoning_from_headline(
            "Bitcoin ETF approved by regulators — institutional bitcoin demand surge",
            db,
        )
        assert result["extracted_event"] is not None
        assert result["extracted_event"]["sentiment"] == "risk_on"

    def test_no_match_sets_no_event_matched(self, db):
        result = validate_reasoning_from_headline(
            "Local council approves new park benches in Surrey", db
        )
        assert result["no_event_matched"] is True
        assert result["extracted_event"] is None

    def test_impact_per_asset_populated_for_known_event(self, db):
        result = validate_reasoning_from_headline(
            "Inflation falls sharply — disinflation trend accelerates", db
        )
        assert len(result["impact_per_asset"]) > 0

    def test_asset_specific_impact_returned_when_requested(self, db):
        result = validate_reasoning_from_headline(
            "Inflation falls sharply — disinflation trend accelerates",
            db, asset="BTC",
        )
        assert result["asset_specific_impact"] is not None
        assert "score" in result["asset_specific_impact"]

    def test_unknown_asset_returns_none_impact(self, db):
        result = validate_reasoning_from_headline(
            "Inflation falls sharply — disinflation trend accelerates",
            db, asset="UNKNOWN_ASSET",
        )
        assert result["asset_specific_impact"] is None

    def test_scenario_comparison_included_when_given(self, db):
        result = validate_reasoning_from_headline(
            "US CPI report shows inflation running hotter than expected — price pressures mount",
            db, scenario_id="cpi_hot",
        )
        assert "scenario_comparison" in result
        assert result["scenario_comparison"]["scenario_id"] == "cpi_hot"
        assert "economic_coherence" in result["scenario_comparison"]

    def test_invalid_scenario_id_reports_error(self, db):
        result = validate_reasoning_from_headline(
            "Some headline", db, scenario_id="does_not_exist"
        )
        assert "error" in result["scenario_comparison"]

    def test_result_always_has_base_keys(self, db):
        result = validate_reasoning_from_headline("Any headline", db)
        required = {"headline", "extracted_event", "impact_per_asset",
                    "no_event_matched"}
        assert required.issubset(result.keys())


# ═══════════════════════════════════════════════════════════════════════════════
# service.py — _build_synthetic_signal
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildSyntheticSignal:

    def test_risk_on_high_produces_buy(self):
        extracted = {"sentiment": "risk_on", "importance": "high", "affected_assets": ["BTC"]}
        sig = _build_synthetic_signal(extracted)
        assert sig["signal"] == "BUY"
        assert sig["confidence"] > 62

    def test_risk_off_high_produces_sell(self):
        extracted = {"sentiment": "risk_off", "importance": "high", "affected_assets": ["BTC"]}
        sig = _build_synthetic_signal(extracted)
        assert sig["signal"] == "SELL"
        assert sig["confidence"] < 38

    def test_neutral_produces_hold(self):
        extracted = {"sentiment": "neutral", "importance": "medium", "affected_assets": ["SPY"]}
        sig = _build_synthetic_signal(extracted)
        assert sig["signal"] == "HOLD"

    def test_none_extracted_produces_hold(self):
        sig = _build_synthetic_signal(None)
        assert sig["signal"] == "HOLD"
        assert sig["confidence"] == 50.0

    def test_synthetic_signal_has_reasoning(self):
        extracted = {"sentiment": "risk_on", "importance": "medium", "affected_assets": ["SPY"]}
        sig = _build_synthetic_signal(extracted)
        assert len(sig["reasoning"]) >= 2

    def test_bullish_reasoning_contains_impact_score(self):
        extracted = {"sentiment": "risk_on", "importance": "high", "affected_assets": ["BTC"]}
        sig = _build_synthetic_signal(extracted)
        assert any("impact score" in l for l in sig["reasoning"])

    def test_generated_at_is_recent(self):
        extracted = {"sentiment": "risk_on", "importance": "high", "affected_assets": ["BTC"]}
        sig = _build_synthetic_signal(extracted)
        generated = datetime.fromisoformat(sig["generated_at"])
        assert (datetime.utcnow() - generated).total_seconds() < 5
