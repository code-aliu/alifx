"""
Signal validation unit tests — tests each check in isolation and composed.

Covers:
  • check_staleness     — time-horizon-aware freshness
  • detect_conflicts    — event/TA mismatch + signal/regime mismatch
  • compute_volatility_penalty — risk level + ATR% penalty
  • compute_consistency_score  — cross-signal direction agreement
  • validate_signal     — full composed pass
"""
from datetime import datetime, timedelta
import pytest

from app.validation.service import (
    check_staleness,
    compute_volatility_penalty,
    compute_consistency_score,
    validate_signal,
    _quality_label,
)
from app.signals.models import TradingSignal


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_signal(
    signal="BUY",
    confidence=70.0,
    risk_level="medium",
    time_horizon="swing",
    reasoning=None,
    generated_at=None,
) -> dict:
    return {
        "asset":        "BTC",
        "signal":       signal,
        "confidence":   confidence,
        "risk_level":   risk_level,
        "time_horizon": time_horizon,
        "reasoning":    reasoning or [],
        "generated_at": (generated_at or datetime.utcnow()).isoformat(),
        "entry_price":  90_000.0,
        "stop_loss":    87_300.0,
        "take_profit":  95_400.0,
        "event_ids":    [],
    }


def _insert_signal(db, asset="BTC", signal="BUY", minutes_ago=1) -> TradingSignal:
    row = TradingSignal(
        asset=asset,
        signal=signal,
        confidence=70.0,
        time_horizon="swing",
        risk_level="medium",
        reasoning=[],
        event_ids=[],
        entry_price=90_000.0,
        generated_at=datetime.utcnow() - timedelta(minutes=minutes_ago),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ═══════════════════════════════════════════════════════════════════════════════
# check_staleness
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckStaleness:

    def test_fresh_swing_signal_is_not_stale(self):
        sig = _make_signal(time_horizon="swing", generated_at=datetime.utcnow())
        is_stale, reason = check_staleness(sig)
        assert not is_stale
        assert reason is None

    def test_swing_signal_older_than_24h_is_stale(self):
        old = datetime.utcnow() - timedelta(hours=25)
        sig = _make_signal(time_horizon="swing", generated_at=old)
        is_stale, reason = check_staleness(sig)
        assert is_stale
        assert reason is not None
        assert "swing" in reason

    def test_intraday_threshold_is_4h(self):
        five_hours_ago = datetime.utcnow() - timedelta(hours=5)
        sig = _make_signal(time_horizon="intraday", generated_at=five_hours_ago)
        is_stale, _ = check_staleness(sig)
        assert is_stale

    def test_intraday_3h_old_is_still_fresh(self):
        three_hours_ago = datetime.utcnow() - timedelta(hours=3)
        sig = _make_signal(time_horizon="intraday", generated_at=three_hours_ago)
        is_stale, _ = check_staleness(sig)
        assert not is_stale

    def test_macro_threshold_is_72h(self):
        seventy_hours_ago = datetime.utcnow() - timedelta(hours=70)
        sig = _make_signal(time_horizon="macro", generated_at=seventy_hours_ago)
        is_stale, _ = check_staleness(sig)
        assert not is_stale

    def test_macro_signal_73h_old_is_stale(self):
        sig = _make_signal(
            time_horizon="macro",
            generated_at=datetime.utcnow() - timedelta(hours=73),
        )
        is_stale, _ = check_staleness(sig)
        assert is_stale

    def test_scalp_threshold_is_1h(self):
        sig = _make_signal(
            time_horizon="scalp",
            generated_at=datetime.utcnow() - timedelta(minutes=90),
        )
        is_stale, _ = check_staleness(sig)
        assert is_stale

    def test_missing_generated_at_is_stale(self):
        sig = _make_signal()
        sig.pop("generated_at")
        is_stale, reason = check_staleness(sig)
        assert is_stale
        assert reason is not None

    def test_stale_reason_contains_hours_old(self):
        sig = _make_signal(
            time_horizon="swing",
            generated_at=datetime.utcnow() - timedelta(hours=30),
        )
        _, reason = check_staleness(sig)
        assert "30" in reason or "h old" in reason


# ═══════════════════════════════════════════════════════════════════════════════
# compute_volatility_penalty
# ═══════════════════════════════════════════════════════════════════════════════

class TestVolatilityPenalty:

    def test_low_risk_no_penalty(self):
        assert compute_volatility_penalty("low", None) == 0.0

    def test_medium_risk_2_point_penalty(self):
        assert compute_volatility_penalty("medium", None) == 2.0

    def test_high_risk_5_point_penalty(self):
        assert compute_volatility_penalty("high", None) == 5.0

    def test_atr_above_3pct_adds_extra(self):
        # ATR% = 4.0, extra = min(4-3, 5) = 1
        penalty = compute_volatility_penalty("medium", atr_pct=4.0)
        assert penalty == 3.0  # 2.0 base + 1.0 extra

    def test_high_atr_capped_at_5_extra(self):
        # ATR% = 15, extra capped at 5
        penalty = compute_volatility_penalty("high", atr_pct=15.0)
        assert penalty == 10.0  # 5.0 base + 5.0 extra (capped)

    def test_atr_below_threshold_no_extra(self):
        penalty = compute_volatility_penalty("low", atr_pct=2.0)
        assert penalty == 0.0

    def test_unknown_risk_level_defaults_to_medium(self):
        assert compute_volatility_penalty("extreme", None) == 2.0


# ═══════════════════════════════════════════════════════════════════════════════
# compute_consistency_score
# ═══════════════════════════════════════════════════════════════════════════════

class TestConsistencyScore:

    def test_no_signals_returns_1(self, db):
        score = compute_consistency_score(db, "BTC")
        assert score == 1.0

    def test_single_signal_returns_1(self, db):
        _insert_signal(db, "BTC", "BUY")
        score = compute_consistency_score(db, "BTC")
        assert score == 1.0

    def test_all_matching_directions_score_1(self, db):
        for i in range(5):
            _insert_signal(db, "BTC", "BUY", minutes_ago=i + 1)
        score = compute_consistency_score(db, "BTC")
        assert score == 1.0

    def test_all_different_directions_score_0(self, db):
        # Alternate BUY / SELL so the latest (BUY) matches none of the prior
        _insert_signal(db, "BTC", "BUY", minutes_ago=1)   # latest
        _insert_signal(db, "BTC", "SELL", minutes_ago=2)
        _insert_signal(db, "BTC", "SELL", minutes_ago=3)
        _insert_signal(db, "BTC", "SELL", minutes_ago=4)
        _insert_signal(db, "BTC", "SELL", minutes_ago=5)
        score = compute_consistency_score(db, "BTC")
        assert score == 0.0

    def test_partial_match(self, db):
        # Latest BUY; 2 prior BUY, 2 prior SELL → 2/4 = 0.5
        _insert_signal(db, "BTC", "BUY", minutes_ago=1)
        _insert_signal(db, "BTC", "BUY", minutes_ago=2)
        _insert_signal(db, "BTC", "BUY", minutes_ago=3)
        _insert_signal(db, "BTC", "SELL", minutes_ago=4)
        _insert_signal(db, "BTC", "SELL", minutes_ago=5)
        score = compute_consistency_score(db, "BTC")
        assert score == pytest.approx(0.5)

    def test_only_looks_at_this_asset(self, db):
        # SPY signals should not count towards BTC consistency
        _insert_signal(db, "BTC", "BUY", minutes_ago=1)
        _insert_signal(db, "SPY", "SELL", minutes_ago=2)
        score = compute_consistency_score(db, "BTC")
        assert score == 1.0  # only 1 BTC signal, no comparison possible


# ═══════════════════════════════════════════════════════════════════════════════
# _quality_label
# ═══════════════════════════════════════════════════════════════════════════════

class TestQualityLabel:

    def test_strong_with_no_flags(self):
        assert _quality_label(75.0, []) == "strong"

    def test_moderate_with_no_flags(self):
        assert _quality_label(60.0, []) == "moderate"

    def test_weak_with_no_flags(self):
        assert _quality_label(45.0, []) == "weak"

    def test_degraded_when_flags_present(self):
        assert _quality_label(80.0, ["stale_signal"]) == "degraded"

    def test_degraded_overrides_high_confidence(self):
        assert _quality_label(95.0, ["event_ta_conflict"]) == "degraded"


# ═══════════════════════════════════════════════════════════════════════════════
# validate_signal (full pass)
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateSignal:

    def test_fresh_low_risk_signal_passes_cleanly(self, db):
        sig = _make_signal(signal="BUY", confidence=72.0, risk_level="low")
        result = validate_signal(sig, db)
        assert not result["is_stale"]
        assert result["volatility_penalty"] == 0.0
        assert result["consistency_score"] == 1.0
        assert result["signal_quality"] in ("strong", "moderate")
        assert result["flags"] == []

    def test_stale_signal_flagged(self, db):
        old_sig = _make_signal(
            time_horizon="swing",
            generated_at=datetime.utcnow() - timedelta(hours=30),
        )
        result = validate_signal(old_sig, db)
        assert result["is_stale"]
        assert "stale_signal" in result["flags"]
        assert result["signal_quality"] == "degraded"

    def test_high_risk_reduces_adjusted_confidence(self, db):
        sig = _make_signal(confidence=70.0, risk_level="high")
        result = validate_signal(sig, db)
        assert result["adjusted_confidence"] < 70.0
        assert result["volatility_penalty"] == 5.0

    def test_event_ta_conflict_flagged_from_reasoning(self, db):
        reasoning = [
            "RSI oversold — bullish",
            "MACD bearish — downward momentum",
            "Event and technical signals are conflicting — confidence capped",
        ]
        sig = _make_signal(signal="HOLD", reasoning=reasoning)
        result = validate_signal(sig, db)
        assert "event_ta_conflict" in result["conflict_flags"]

    def test_clean_signal_has_no_conflict_flags(self, db):
        reasoning = [
            "News/event flow is bullish",
            "RSI oversold — potential reversal upward",
            "EMA golden cross — bullish momentum",
        ]
        sig = _make_signal(signal="BUY", reasoning=reasoning)
        result = validate_signal(sig, db)
        assert "event_ta_conflict" not in result["conflict_flags"]

    def test_adjusted_confidence_clamped_to_5(self, db):
        sig = _make_signal(confidence=5.0, risk_level="high")
        result = validate_signal(sig, db)
        assert result["adjusted_confidence"] >= 5.0

    def test_inconsistent_signals_flagged(self, db):
        # 4 prior SELL, latest BUY → consistency = 0.0
        for i in range(4):
            _insert_signal(db, "BTC", "SELL", minutes_ago=i + 2)
        sig = _make_signal(signal="BUY", confidence=70.0)
        result = validate_signal(sig, db)
        assert result["consistency_score"] == 0.0
        assert "inconsistent_signals" in result["flags"]

    def test_validation_result_has_all_required_keys(self, db):
        sig = _make_signal()
        result = validate_signal(sig, db)
        required = {
            "is_stale", "stale_reason", "consistency_score",
            "conflict_flags", "volatility_penalty", "adjusted_confidence",
            "warnings", "flags", "signal_quality",
        }
        assert required.issubset(result.keys())

    def test_atr_penalty_applied_when_atr_pct_high(self, db):
        sig = _make_signal(confidence=70.0, risk_level="low")
        # atr_pct = 5.0 → extra = min(5-3, 5) = 2 pts above base 0
        result = validate_signal(sig, db, atr_pct=5.0)
        assert result["volatility_penalty"] == 2.0
        assert result["adjusted_confidence"] == pytest.approx(68.0)
