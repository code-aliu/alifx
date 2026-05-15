"""
Integration tests — Phase 2+3: Signal Generation Pipeline

Tests the impact mapper and signal generator in isolation with realistic
event and market data inputs. No database or external I/O required.
"""
import pytest
from app.impact.mapper import map_events_to_impact, summarize_impact
from app.signals.generator import generate_signal
from tests.conftest import make_market_event


# ── Impact mapping ────────────────────────────────────────────────────────────

class TestImpactMapping:

    def test_single_risk_on_high_event_is_bullish(self, db):
        article = make_market_event(
            db,
            article_id=None,
            headline="BlackRock Bitcoin ETF sees record inflows",
            category="crypto",
            sentiment="risk_on",
            importance="high",
            affected_assets=["BTC", "ETH"],
        )
        # Use a plain object that has sentiment/importance/affected_assets attrs
        scores = map_events_to_impact([article])
        assert scores["BTC"] > 0
        assert scores["ETH"] > 0
        assert scores["SPY"] == 0.0

    def test_risk_off_event_produces_negative_score(self, db):
        event = make_market_event(
            db,
            article_id=None,
            headline="US economy enters recession",
            category="macroeconomic",
            sentiment="risk_off",
            importance="high",
            affected_assets=["SPY", "QQQ", "BTC"],
        )
        scores = map_events_to_impact([event])
        assert scores["SPY"] < 0
        assert scores["BTC"] < 0

    def test_neutral_event_does_not_move_score(self, db):
        event = make_market_event(
            db,
            article_id=None,
            headline="Fed holds rates unchanged",
            category="macroeconomic",
            sentiment="neutral",
            importance="medium",
            affected_assets=["USD", "SPY"],
        )
        scores = map_events_to_impact([event])
        # neutral → score = 0 for all assets
        assert all(v == 0.0 for v in scores.values())

    def test_multiple_bullish_events_compound(self, db):
        events = []
        for _ in range(3):
            events.append(make_market_event(
                db, article_id=None,
                headline="Rate cut announced",
                category="macroeconomic",
                sentiment="risk_on",
                importance="high",
                affected_assets=["BTC", "ETH", "SPY"],
            ))
        scores = map_events_to_impact(events)
        # 3 × high weight (3) = 9 for BTC
        assert scores["BTC"] == pytest.approx(9.0)

    def test_conflicting_events_partially_cancel(self, db):
        bull = make_market_event(
            db, article_id=None,
            headline="Inflation cools — rate cut expected",
            category="macroeconomic",
            sentiment="risk_on",
            importance="high",
            affected_assets=["SPY"],
        )
        bear = make_market_event(
            db, article_id=None,
            headline="GDP contracts — recession risk rises",
            category="macroeconomic",
            sentiment="risk_off",
            importance="high",
            affected_assets=["SPY"],
        )
        scores = map_events_to_impact([bull, bear])
        # +3 (risk_on high) + -3 (risk_off high) = 0
        assert scores["SPY"] == pytest.approx(0.0)


# ── Impact summarization ──────────────────────────────────────────────────────

class TestImpactSummarization:

    def test_positive_score_is_bullish(self):
        summary = summarize_impact({"BTC": 6.0})
        assert summary["BTC"]["direction"] == "bullish"
        assert summary["BTC"]["strength"] == pytest.approx(1.0)

    def test_negative_score_is_bearish(self):
        summary = summarize_impact({"SPY": -3.0})
        assert summary["SPY"]["direction"] == "bearish"
        assert summary["SPY"]["strength"] == pytest.approx(0.5)

    def test_zero_score_is_neutral(self):
        summary = summarize_impact({"EURUSD": 0.0})
        assert summary["EURUSD"]["direction"] == "neutral"
        assert summary["EURUSD"]["strength"] == pytest.approx(0.0)

    def test_strength_capped_at_one(self):
        summary = summarize_impact({"BTC": 100.0})
        assert summary["BTC"]["strength"] == pytest.approx(1.0)


# ── Signal generation ─────────────────────────────────────────────────────────

class TestSignalGeneration:

    def _bullish_analysis(self):
        return {
            "indicators": {
                "rsi":        {"available": True, "value": 52, "signal": "neutral"},
                "ema":        {"available": True, "ema_20": 94_500, "signal": "bullish",
                               "ema_50_available": True, "ema_50": 93_000},
                "macd":       {"available": True, "trend": "bullish", "histogram": 200},
                "volatility": {"available": True, "value": 1.8, "level": "medium"},
            },
            "breakout": {"available": False},
            "trend":    {"available": True, "trend": "uptrend",
                         "short_ma": 94_800, "long_ma": 92_500},
        }

    def _bearish_analysis(self):
        return {
            "indicators": {
                "rsi":        {"available": True, "value": 74, "signal": "overbought"},
                "ema":        {"available": True, "ema_20": 91_000, "signal": "bearish",
                               "ema_50_available": True, "ema_50": 93_000},
                "macd":       {"available": True, "trend": "bearish", "histogram": -300},
                "volatility": {"available": True, "value": 2.5, "level": "medium"},
            },
            "breakout": {"available": False},
            "trend":    {"available": True, "trend": "downtrend",
                         "short_ma": 91_000, "long_ma": 93_500},
        }

    def _neutral_analysis(self):
        return {
            "indicators": {
                "rsi":        {"available": False},
                "ema":        {"available": False},
                "macd":       {"available": False},
                "volatility": {"available": False},
            },
            "breakout": {"available": False},
            "trend":    {"available": False},
        }

    # BUY signal conditions
    def test_buy_signal_with_bullish_event_and_bullish_ta(self):
        impact = {"score": 6.0, "direction": "bullish", "strength": 1.0}
        signal = generate_signal("BTC", impact, self._bullish_analysis(), 95_000)

        assert signal["signal"] == "BUY"
        assert signal["confidence"] >= 62
        assert signal["asset"] == "BTC"
        assert signal["stop_loss"] < 95_000
        assert signal["take_profit"] > 95_000

    # SELL signal conditions
    def test_sell_signal_with_bearish_event_and_bearish_ta(self):
        impact = {"score": -6.0, "direction": "bearish", "strength": 1.0}
        signal = generate_signal("SPY", impact, self._bearish_analysis(), 580)

        assert signal["signal"] == "SELL"
        assert signal["confidence"] <= 38
        assert signal["stop_loss"] > 580
        assert signal["take_profit"] < 580

    # HOLD — no event bias
    def test_hold_when_no_event_bias(self):
        impact = {"score": 0.0, "direction": "neutral", "strength": 0.0}
        signal = generate_signal("BTC", impact, self._bullish_analysis(), 95_000)

        assert signal["signal"] == "HOLD"
        assert any("no macro/event bias" in r.lower() for r in signal["reasoning"])

    # HOLD — no TA confirmation
    def test_hold_when_no_ta_confirmation(self):
        impact = {"score": 3.0, "direction": "bullish", "strength": 0.5}
        signal = generate_signal("BTC", impact, self._neutral_analysis(), 95_000)

        assert signal["signal"] == "HOLD"
        assert any("no clear technical confirmation" in r.lower() for r in signal["reasoning"])

    # Conflict capping
    def test_confidence_capped_when_event_and_ta_conflict(self):
        """Bullish event + bearish TA → conflict → confidence capped at 58."""
        impact = {"score": 6.0, "direction": "bullish", "strength": 1.0}
        signal = generate_signal("BTC", impact, self._bearish_analysis(), 95_000)

        assert signal["confidence"] <= 58
        assert any("conflicting" in r.lower() for r in signal["reasoning"])

    # Dual requirement enforced
    def test_dual_requirement_both_needed(self):
        """Even with very strong TA, if no event bias → HOLD."""
        impact = {"score": 0.05, "direction": "bullish", "strength": 0.008}  # below threshold
        signal = generate_signal("SPY", impact, self._bullish_analysis(), 580)

        assert signal["signal"] == "HOLD"

    # Risk level propagation
    def test_risk_level_from_volatility(self):
        high_vol_analysis = self._bullish_analysis()
        high_vol_analysis["indicators"]["volatility"] = {
            "available": True, "value": 4.5, "level": "high"
        }
        impact = {"score": 3.0, "direction": "bullish", "strength": 0.5}
        signal = generate_signal("BTC", impact, high_vol_analysis, 95_000)
        assert signal["risk_level"] == "high"

    def test_risk_level_low_on_calm_market(self):
        low_vol_analysis = self._bullish_analysis()
        low_vol_analysis["indicators"]["volatility"] = {
            "available": True, "value": 0.4, "level": "low"
        }
        impact = {"score": 3.0, "direction": "bullish", "strength": 0.5}
        signal = generate_signal("EURUSD", impact, low_vol_analysis, 1.085)
        assert signal["risk_level"] == "low"

    # Confidence bounds
    def test_confidence_is_bounded_between_5_and_95(self):
        impact = {"score": 100.0, "direction": "bullish", "strength": 1.0}
        signal = generate_signal("BTC", impact, self._bullish_analysis(), 95_000)
        assert 5 <= signal["confidence"] <= 95

    # Required output fields
    def test_signal_output_has_required_fields(self):
        impact = {"score": 3.0, "direction": "bullish", "strength": 0.5}
        signal = generate_signal("BTC", impact, self._bullish_analysis(), 95_000)
        required = {"asset", "signal", "confidence", "time_horizon", "risk_level",
                    "reasoning", "entry_price", "stop_loss", "take_profit",
                    "generated_at", "expires_at"}
        assert required.issubset(signal.keys())

    def test_reasoning_is_non_empty_list(self):
        impact = {"score": 3.0, "direction": "bullish", "strength": 0.5}
        signal = generate_signal("BTC", impact, self._bullish_analysis(), 95_000)
        assert isinstance(signal["reasoning"], list)
        assert len(signal["reasoning"]) > 0

    def test_golden_cross_adds_extra_confidence(self):
        golden_analysis = self._bullish_analysis()
        golden_analysis["indicators"]["ema"]["signal"] = "golden_cross"
        impact = {"score": 3.0, "direction": "bullish", "strength": 0.5}

        normal_analysis = self._bullish_analysis()
        impact_same = {"score": 3.0, "direction": "bullish", "strength": 0.5}

        gc_signal = generate_signal("BTC", impact, golden_analysis, 95_000)
        normal_signal = generate_signal("BTC", impact_same, normal_analysis, 95_000)

        assert gc_signal["confidence"] > normal_signal["confidence"]
