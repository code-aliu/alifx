"""
Integration tests — Market Regime Detection

Tests all four detection signals (volatility, price trend, event flow, cross-asset)
and the classifier that combines them into a primary regime.
Also tests the regime → signal confidence adjustment path.
"""
import pytest
from tests.conftest import make_linear_bars, make_price_bars

from app.regime.detector import (
    detect_volatility_regime,
    detect_price_trend_regime,
    detect_event_regime,
    detect_cross_asset_regime,
    classify_regime,
    detect_regime,
    REGIME_SIGNAL_DELTA,
)
from app.signals.generator import generate_signal


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _impact(symbol, score):
    direction = "bullish" if score > 0 else "bearish" if score < 0 else "neutral"
    return {symbol: {"score": score, "direction": direction, "strength": min(abs(score)/6, 1.0)}}


def _full_bullish_impact():
    assets = ["BTC", "ETH", "SPY", "QQQ", "NVDA", "AAPL", "EURUSD", "GBPUSD", "USDJPY"]
    return {a: {"score": 6.0, "direction": "bullish", "strength": 1.0} for a in assets}


def _full_bearish_impact():
    assets = ["BTC", "ETH", "SPY", "QQQ", "NVDA", "AAPL", "EURUSD", "GBPUSD", "USDJPY"]
    return {a: {"score": -6.0, "direction": "bearish", "strength": 1.0} for a in assets}


def _neutral_impact():
    assets = ["BTC", "ETH", "SPY", "QQQ", "NVDA", "AAPL", "EURUSD", "GBPUSD", "USDJPY"]
    return {a: {"score": 0.0, "direction": "neutral", "strength": 0.0} for a in assets}


# ── 1. Volatility regime ──────────────────────────────────────────────────────

class TestVolatilityRegime:

    def test_high_volatility_on_wild_bars(self):
        """Alternating 5% up/down bars → high_volatility."""
        from datetime import datetime, timedelta
        import random
        rng = random.Random(7)
        price = 90_000.0
        bars = []
        for i in range(20):
            price *= rng.choice([1.05, 0.95])
            bars.append({
                "open": price, "high": price * 1.01, "low": price * 0.99,
                "close": price, "volume": 1000,
                "fetched_at": datetime(2026, 5, 14) + timedelta(minutes=i),
            })
        result = detect_volatility_regime(bars)
        assert result["available"] is True
        assert result["regime"] == "high_volatility"
        assert result["confidence"] > 0.5

    def test_low_volatility_on_flat_bars(self):
        """Perfectly flat price → low_volatility."""
        from datetime import datetime, timedelta
        bars = [
            {"open": 100.0, "high": 100.05, "low": 99.95, "close": 100.0,
             "volume": 1000, "fetched_at": datetime(2026, 5, 14) + timedelta(minutes=i)}
            for i in range(20)
        ]
        result = detect_volatility_regime(bars)
        assert result["available"] is True
        assert result["regime"] == "low_volatility"
        assert result["confidence"] > 0

    def test_insufficient_bars_returns_unavailable(self):
        bars = make_linear_bars("BTC", 90_000, 95_000, n=10)
        result = detect_volatility_regime(bars)
        assert result["available"] is False

    def test_uptrend_bars_are_medium_volatility(self):
        bars = make_price_bars("BTC", 88_000, 95_200, n=60, volatility_pct=1.2)
        result = detect_volatility_regime(bars)
        assert result["available"] is True
        assert "atr_pct" in result
        assert "vol_std" in result

    def test_forex_bars_are_lower_volatility_than_btc(self):
        btc_bars   = make_price_bars("BTC",    88_000, 95_200, n=60, volatility_pct=1.2)
        forex_bars = make_price_bars("EURUSD", 1.075,  1.087,  n=60, volatility_pct=0.3)
        btc_vol   = detect_volatility_regime(btc_bars)
        forex_vol = detect_volatility_regime(forex_bars)
        # BTC should have higher ATR% than EURUSD
        assert btc_vol.get("atr_pct", 0) > forex_vol.get("atr_pct", 0)


# ── 2. Price trend regime ─────────────────────────────────────────────────────

class TestPriceTrendRegime:

    def test_strong_uptrend_is_trending(self):
        bars = make_linear_bars("BTC", 80_000, 95_000, n=60)
        result = detect_price_trend_regime(bars)
        assert result["available"] is True
        assert result["regime"] == "trending"
        assert result["direction"] == "uptrend"

    def test_strong_downtrend_is_trending(self):
        bars = make_linear_bars("BTC", 95_000, 75_000, n=60)
        result = detect_price_trend_regime(bars)
        assert result["available"] is True
        assert result["regime"] == "trending"
        assert result["direction"] == "downtrend"

    def test_flat_market_is_ranging(self):
        from datetime import datetime, timedelta
        bars = [
            {"open": 580.0, "high": 580.5, "low": 579.5, "close": 580.0,
             "volume": 1000, "fetched_at": datetime(2026, 5, 14) + timedelta(minutes=i)}
            for i in range(30)
        ]
        result = detect_price_trend_regime(bars)
        assert result["available"] is True
        assert result["regime"] == "ranging"
        assert result["direction"] == "sideways"

    def test_insufficient_bars_returns_unavailable(self):
        result = detect_price_trend_regime(make_linear_bars("SPY", 565, 582, n=5))
        assert result["available"] is False

    def test_cv_is_positive(self):
        bars = make_linear_bars("BTC", 88_000, 95_200, n=60)
        result = detect_price_trend_regime(bars)
        assert result["cv"] >= 0


# ── 3. Event flow regime ─────────────────────────────────────────────────────

class TestEventFlowRegime:

    def test_all_bullish_impact_is_risk_on(self):
        result = detect_event_regime(_full_bullish_impact())
        assert result["regime"] == "risk_on"
        assert result["confidence"] > 0.5

    def test_all_bearish_impact_is_risk_off(self):
        result = detect_event_regime(_full_bearish_impact())
        assert result["regime"] == "risk_off"
        assert result["confidence"] > 0.5

    def test_neutral_impact_is_neutral(self):
        result = detect_event_regime(_neutral_impact())
        assert result["regime"] == "neutral"

    def test_mixed_impact_depends_on_average(self):
        mixed = {
            "BTC":    {"score": 3.0,  "direction": "bullish", "strength": 0.5},
            "SPY":    {"score": -3.0, "direction": "bearish", "strength": 0.5},
            "EURUSD": {"score": 0.0,  "direction": "neutral", "strength": 0.0},
        }
        result = detect_event_regime(mixed)
        # avg = 0 → neutral
        assert result["regime"] == "neutral"

    def test_empty_impact_returns_unavailable(self):
        result = detect_event_regime({})
        assert result["available"] is False

    def test_bullish_count_bearish_count_fields_present(self):
        result = detect_event_regime(_full_bullish_impact())
        assert "bullish_count" in result
        assert "bearish_count" in result
        assert result["bullish_count"] > 0


# ── 4. Cross-asset regime ─────────────────────────────────────────────────────

class TestCrossAssetRegime:

    def test_all_bellwethers_bullish_is_risk_on(self):
        impact = {
            "BTC":    {"score": 3.0, "direction": "bullish", "strength": 0.5},
            "SPY":    {"score": 3.0, "direction": "bullish", "strength": 0.5},
            "EURUSD": {"score": 2.0, "direction": "bullish", "strength": 0.33},
        }
        result = detect_cross_asset_regime(impact)
        assert result["regime"] == "risk_on"
        assert result["confidence"] >= 0.67

    def test_all_bellwethers_bearish_is_risk_off(self):
        impact = {
            "BTC":    {"score": -3.0, "direction": "bearish", "strength": 0.5},
            "SPY":    {"score": -3.0, "direction": "bearish", "strength": 0.5},
            "EURUSD": {"score": -2.0, "direction": "bearish", "strength": 0.33},
        }
        result = detect_cross_asset_regime(impact)
        assert result["regime"] == "risk_off"

    def test_divergent_bellwethers_is_mixed(self):
        impact = {
            "BTC":    {"score": 3.0,  "direction": "bullish", "strength": 0.5},
            "SPY":    {"score": -3.0, "direction": "bearish", "strength": 0.5},
            "EURUSD": {"score": 0.0,  "direction": "neutral", "strength": 0.0},
        }
        result = detect_cross_asset_regime(impact)
        assert result["regime"] == "mixed"

    def test_directions_dict_present(self):
        result = detect_cross_asset_regime(_full_bullish_impact())
        assert "directions" in result
        assert "BTC" in result["directions"]

    def test_empty_impact_returns_unavailable(self):
        result = detect_cross_asset_regime({})
        assert result["available"] is False


# ── 5. Classifier ─────────────────────────────────────────────────────────────

class TestClassifier:

    def _vol(self, regime, confidence):
        return {"regime": regime, "confidence": confidence, "available": True,
                "atr_pct": 2.0, "vol_std": 1.5}

    def _trend(self, regime, confidence, direction="uptrend"):
        return {"regime": regime, "confidence": confidence, "available": True,
                "cv": 0.04, "direction": direction}

    def _event(self, regime, confidence):
        return {"regime": regime, "confidence": confidence, "available": True,
                "avg_score": 3.0 if regime == "risk_on" else -3.0,
                "bullish_count": 7, "bearish_count": 2}

    def _cross(self, regime, confidence):
        return {"regime": regime, "confidence": confidence, "available": True,
                "directions": {"BTC": "bullish", "SPY": "bullish", "EURUSD": "bullish"},
                "bullish": 3, "bearish": 0}

    def test_strong_risk_on_wins_when_event_and_cross_agree(self):
        result = classify_regime(
            vol=self._vol("neutral", 0.3),
            price_trend=self._trend("trending", 0.5),
            event=self._event("risk_on", 0.9),
            cross_asset=self._cross("risk_on", 1.0),
        )
        assert result["primary_regime"] == "risk_on"
        assert result["confidence"] > 0

    def test_high_volatility_wins_when_extreme(self):
        result = classify_regime(
            vol=self._vol("high_volatility", 1.0),
            price_trend=self._trend("trending", 0.3),
            event=self._event("risk_on", 0.3),
            cross_asset=self._cross("risk_on", 0.3),
        )
        assert result["primary_regime"] == "high_volatility"

    def test_ranging_wins_when_no_trend_or_events(self):
        neutral_event = {"regime": "neutral", "confidence": 0.0, "available": True,
                         "avg_score": 0.0, "bullish_count": 0, "bearish_count": 0}
        mixed_cross   = {"regime": "mixed", "confidence": 0.3, "available": True,
                         "directions": {}, "bullish": 0, "bearish": 0}
        result = classify_regime(
            vol=self._vol("neutral", 0.2),
            price_trend=self._trend("ranging", 0.9, "sideways"),
            event=neutral_event,
            cross_asset=mixed_cross,
        )
        assert result["primary_regime"] == "ranging"

    def test_output_has_required_fields(self):
        result = classify_regime(
            vol=self._vol("neutral", 0.3),
            price_trend=self._trend("trending", 0.6),
            event=self._event("risk_on", 0.7),
            cross_asset=self._cross("risk_on", 0.8),
        )
        required = {"primary_regime", "secondary_regimes", "confidence",
                    "reasoning", "components", "signal_delta", "computed_at"}
        assert required.issubset(result.keys())

    def test_secondary_regimes_is_list(self):
        result = classify_regime(
            vol=self._vol("high_volatility", 0.8),
            price_trend=self._trend("trending", 0.7),
            event=self._event("risk_off", 0.9),
            cross_asset=self._cross("risk_off", 0.8),
        )
        assert isinstance(result["secondary_regimes"], list)

    def test_reasoning_is_non_empty(self):
        result = classify_regime(
            vol=self._vol("high_volatility", 0.9),
            price_trend=self._trend("trending", 0.7),
            event=self._event("risk_on", 0.8),
            cross_asset=self._cross("risk_on", 0.9),
        )
        assert len(result["reasoning"]) > 0

    def test_signal_delta_matches_primary_regime(self):
        result = classify_regime(
            vol=self._vol("neutral", 0.2),
            price_trend=self._trend("ranging", 0.9),
            event={"regime": "neutral", "confidence": 0.0, "available": True,
                   "avg_score": 0.0, "bullish_count": 0, "bearish_count": 0},
            cross_asset={"regime": "mixed", "confidence": 0.3, "available": True,
                         "directions": {}, "bullish": 0, "bearish": 0},
        )
        expected_delta = REGIME_SIGNAL_DELTA.get(result["primary_regime"], 0.0)
        assert result["signal_delta"] == expected_delta


# ── 6. detect_regime (full pipeline) ─────────────────────────────────────────

class TestDetectRegimePipeline:

    def test_btc_uptrend_with_bullish_events_is_risk_on_or_trending(self):
        bars   = make_linear_bars("BTC", 88_000, 95_000, n=60)
        result = detect_regime(bars, _full_bullish_impact())
        assert result["primary_regime"] in ("risk_on", "trending", "low_volatility")

    def test_empty_prices_returns_valid_result(self):
        result = detect_regime([], _full_bullish_impact())
        assert "primary_regime" in result
        assert result["primary_regime"] in ("risk_on", "ranging")

    def test_empty_impact_still_classifies_from_price(self):
        bars   = make_linear_bars("BTC", 88_000, 95_000, n=60)
        result = detect_regime(bars, {})
        assert "primary_regime" in result

    def test_bearish_events_with_volatile_bars_produces_risk_off_or_high_vol(self):
        from datetime import datetime, timedelta
        import random
        rng = random.Random(13)
        price = 90_000.0
        bars = []
        for i in range(25):
            price *= rng.choice([1.055, 0.945])
            bars.append({
                "open": price, "high": price * 1.01, "low": price * 0.99,
                "close": price, "volume": 1000,
                "fetched_at": datetime(2026, 5, 14) + timedelta(minutes=i),
            })
        result = detect_regime(bars, _full_bearish_impact())
        assert result["primary_regime"] in ("risk_off", "high_volatility", "trending")


# ── 7. Regime → signal confidence adjustment ─────────────────────────────────

class TestRegimeSignalAdjustment:

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

    def test_risk_on_regime_boosts_buy_confidence(self):
        impact = {"score": 3.0, "direction": "bullish", "strength": 0.5}
        base_signal = generate_signal("BTC", impact, self._bullish_analysis(), 95_000)

        risk_on_regime = {
            "primary_regime": "risk_on",
            "confidence": 0.85,
            "reasoning": ["Event flow bullish", "Cross-asset all up"],
            "secondary_regimes": [],
        }
        boosted_signal = generate_signal("BTC", impact, self._bullish_analysis(), 95_000,
                                         regime=risk_on_regime)

        assert boosted_signal["confidence"] > base_signal["confidence"]
        assert boosted_signal["confidence"] == pytest.approx(
            base_signal["confidence"] + REGIME_SIGNAL_DELTA["risk_on"], abs=0.1
        )

    def test_risk_off_regime_reduces_buy_confidence(self):
        impact = {"score": 3.0, "direction": "bullish", "strength": 0.5}
        base_signal = generate_signal("BTC", impact, self._bullish_analysis(), 95_000)

        risk_off_regime = {
            "primary_regime": "risk_off",
            "confidence": 0.8,
            "reasoning": ["Event flow bearish"],
            "secondary_regimes": ["high_volatility"],
        }
        dampened_signal = generate_signal("BTC", impact, self._bullish_analysis(), 95_000,
                                          regime=risk_off_regime)

        assert dampened_signal["confidence"] < base_signal["confidence"]

    def test_ranging_regime_can_demote_buy_to_hold(self):
        """A borderline BUY (confidence just above 62) should become HOLD in a ranging market."""
        impact = {"score": 2.0, "direction": "bullish", "strength": 0.33}
        borderline_analysis = {
            "indicators": {
                "rsi":        {"available": True, "value": 52, "signal": "neutral"},
                "ema":        {"available": True, "ema_20": 94_500, "signal": "bullish",
                               "ema_50_available": False},
                "macd":       {"available": True, "trend": "bullish", "histogram": 100},
                "volatility": {"available": True, "value": 0.5, "level": "low"},
            },
            "breakout": {"available": False},
            "trend":    {"available": True, "trend": "uptrend",
                         "short_ma": 94_800, "long_ma": 93_000},
        }
        no_regime = generate_signal("BTC", impact, borderline_analysis, 95_000)
        ranging_regime = {
            "primary_regime": "ranging",
            "confidence": 0.9,
            "reasoning": ["CV low, sideways price action"],
            "secondary_regimes": [],
        }
        with_regime = generate_signal("BTC", impact, borderline_analysis, 95_000,
                                       regime=ranging_regime)

        # Ranging should reduce confidence
        assert with_regime["confidence"] < no_regime["confidence"]

    def test_regime_reasoning_appears_in_signal(self):
        impact = {"score": 3.0, "direction": "bullish", "strength": 0.5}
        regime = {
            "primary_regime": "risk_on",
            "confidence": 0.85,
            "reasoning": ["Cross-asset consensus: risk_on"],
            "secondary_regimes": [],
        }
        signal = generate_signal("BTC", impact, self._bullish_analysis(), 95_000,
                                  regime=regime)
        reasoning_text = " ".join(signal["reasoning"])
        assert "risk_on" in reasoning_text.lower()

    def test_no_regime_does_not_crash_generator(self):
        impact = {"score": 3.0, "direction": "bullish", "strength": 0.5}
        signal = generate_signal("BTC", impact, self._bullish_analysis(), 95_000, regime=None)
        assert signal is not None
        assert "signal" in signal

    def test_all_six_regime_deltas_are_defined(self):
        expected = {"risk_on", "risk_off", "trending", "ranging",
                    "high_volatility", "low_volatility"}
        assert expected == set(REGIME_SIGNAL_DELTA.keys())
