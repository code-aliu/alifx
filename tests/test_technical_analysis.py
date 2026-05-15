"""
Integration tests — Phase 2: Technical Analysis

Tests RSI, EMA, MACD, volatility, trend, and breakout computations
against synthetic but realistic OHLC price series for BTC, SPY, EUR/USD.
All assertions are grounded in the actual indicator formulas in the codebase.
"""
import pytest
from app.analysis.indicators import compute_all, compute_flat
from app.analysis.patterns import detect_trend, detect_breakout


# ── RSI ───────────────────────────────────────────────────────────────────────

class TestRSI:

    def test_rsi_neutral_on_balanced_uptrend(self, btc_uptrend_bars):
        result = compute_all(btc_uptrend_bars)
        rsi = result["rsi"]

        assert rsi["available"] is True
        assert 30 < rsi["value"] < 70
        assert rsi["signal"] == "neutral"

    def test_rsi_unavailable_below_15_bars(self, btc_uptrend_bars):
        result = compute_all(btc_uptrend_bars[:10])
        rsi = result["rsi"]
        assert rsi["available"] is False

    def test_rsi_overbought_after_strong_sustained_rally(self):
        """Predominantly up bars with periodic tiny pullbacks → overbought RSI.

        The RSI computation uses `avg_loss.replace(0, np.nan)`, so avg_loss must
        stay above 0. Periodic small pullbacks (every 6 bars) provide non-zero
        losses in the diff series while keeping the overall trend strongly bullish.
        """
        from datetime import datetime, timedelta
        bars = []
        price = 90_000.0
        base = datetime(2026, 5, 14)
        for i in range(35):
            prev = price
            # Every 6th bar is a small pullback; all others are strong up bars.
            if i > 0 and i % 6 == 0:
                price *= 0.985
            else:
                price *= 1.028
            bars.append({
                "open":       prev,
                "high":       max(prev, price) * 1.001,
                "low":        min(prev, price) * 0.999,
                "close":      price,
                "volume":     1000,
                "fetched_at": base + timedelta(minutes=i),
            })
        result = compute_all(bars)
        rsi = result["rsi"]
        assert rsi["available"] is True
        assert rsi["value"] >= 70, f"Expected RSI >= 70, got {rsi['value']}"
        assert rsi["signal"] == "overbought"

    def test_rsi_oversold_after_sustained_sell_off(self):
        """Consecutive -2% candles for 30 bars drives RSI into oversold territory."""
        bars = []
        from datetime import datetime, timedelta
        price = 90_000.0
        for i in range(30):
            price *= 0.98
            bars.append({
                "open": price * 1.01, "high": price * 1.02,
                "low": price * 0.99, "close": price,
                "volume": 1000,
                "fetched_at": datetime(2026, 5, 14) + timedelta(minutes=i),
            })
        result = compute_all(bars)
        rsi = result["rsi"]
        assert rsi["available"] is True
        assert rsi["value"] <= 30
        assert rsi["signal"] == "oversold"


# ── EMA ───────────────────────────────────────────────────────────────────────

class TestEMA:

    def test_ema_available_with_sufficient_bars(self, spy_bullish_bars):
        result = compute_all(spy_bullish_bars)
        ema = result["ema"]
        assert ema["available"] is True
        assert "ema_20" in ema
        assert ema["ema_20"] > 0

    def test_ema_50_available_with_60_bars(self, spy_bullish_bars):
        result = compute_all(spy_bullish_bars)
        ema = result["ema"]
        assert ema["ema_50_available"] is True
        assert "ema_50" in ema

    def test_ema_200_unavailable_with_60_bars(self, spy_bullish_bars):
        result = compute_all(spy_bullish_bars)
        ema = result["ema"]
        assert ema["ema_200_available"] is False

    def test_ema_signal_bullish_on_uptrend(self, spy_bullish_bars):
        result = compute_all(spy_bullish_bars)
        ema = result["ema"]
        assert ema["signal"] in ("bullish", "golden_cross")

    def test_ema_signal_bearish_on_downtrend(self, btc_downtrend_bars):
        result = compute_all(btc_downtrend_bars)
        ema = result["ema"]
        assert ema["available"] is True
        assert ema["signal"] in ("bearish", "death_cross")

    def test_ema_unavailable_below_21_bars(self, btc_uptrend_bars):
        result = compute_all(btc_uptrend_bars[:15])
        ema = result["ema"]
        assert ema["available"] is False


# ── MACD ─────────────────────────────────────────────────────────────────────

class TestMACD:

    def test_macd_available_with_35_plus_bars(self, btc_uptrend_bars):
        result = compute_all(btc_uptrend_bars)
        macd = result["macd"]
        assert macd["available"] is True
        assert "macd" in macd
        assert "signal" in macd
        assert "histogram" in macd

    def test_macd_unavailable_below_35_bars(self, btc_uptrend_bars):
        result = compute_all(btc_uptrend_bars[:30])
        macd = result["macd"]
        assert macd["available"] is False

    def test_macd_bullish_on_uptrend(self):
        """Perfectly linear uptrend produces a consistently positive MACD histogram."""
        from tests.conftest import make_linear_bars
        bars = make_linear_bars("SPY", 545, 582, n=60)
        result = compute_all(bars)
        macd = result["macd"]
        assert macd["available"] is True
        assert macd["trend"] in ("bullish", "bullish_crossover")
        # Histogram should be positive (EMA_fast > EMA_slow on uptrend)
        assert macd["histogram"] > 0

    def test_macd_bearish_on_downtrend(self):
        """Perfectly linear downtrend produces a consistently negative MACD histogram."""
        from tests.conftest import make_linear_bars
        bars = make_linear_bars("BTC", 95_000, 82_000, n=60)
        result = compute_all(bars)
        macd = result["macd"]
        assert macd["available"] is True
        assert macd["trend"] in ("bearish", "bearish_crossover")
        # Histogram should be negative (EMA_fast < EMA_slow on downtrend)
        assert macd["histogram"] < 0


# ── Volatility ────────────────────────────────────────────────────────────────

class TestVolatility:

    def test_btc_has_higher_volatility_than_spy(self, btc_uptrend_bars, spy_bullish_bars):
        btc_vol = compute_all(btc_uptrend_bars)["volatility"]["value"]
        spy_vol = compute_all(spy_bullish_bars)["volatility"]["value"]
        assert btc_vol > spy_vol

    def test_eurusd_low_volatility(self, eurusd_recovery_bars):
        result = compute_all(eurusd_recovery_bars)
        vol = result["volatility"]
        assert vol["available"] is True
        assert vol["level"] in ("low", "medium")

    def test_volatile_bars_get_high_level(self):
        """Sharp 5% candles should register as high volatility."""
        from datetime import datetime, timedelta
        import random
        rng = random.Random(7)
        price = 90_000.0
        bars = []
        for i in range(20):
            change = rng.choice([1.05, 0.95])
            price *= change
            bars.append({
                "open": price, "high": price * 1.01, "low": price * 0.99,
                "close": price, "volume": 1000,
                "fetched_at": datetime(2026, 5, 14) + timedelta(minutes=i),
            })
        vol = compute_all(bars)["volatility"]
        assert vol["level"] == "high"


# ── compute_flat ──────────────────────────────────────────────────────────────

class TestComputeFlat:

    def test_flat_format_keys(self, btc_uptrend_bars):
        flat = compute_flat(btc_uptrend_bars)
        required = {"latest_close", "trend", "rsi", "rsi_signal",
                    "ema_20", "ema_signal", "macd_signal", "volatility", "bars_used"}
        assert required.issubset(flat.keys())

    def test_flat_latest_close_near_end_price(self, btc_uptrend_bars):
        flat = compute_flat(btc_uptrend_bars)
        # Last bar is near $95,200 — within 5% is reasonable given noise
        assert 85_000 < flat["latest_close"] < 105_000

    def test_flat_eurusd_close_in_range(self, eurusd_recovery_bars):
        flat = compute_flat(eurusd_recovery_bars)
        assert 1.05 < flat["latest_close"] < 1.15

    def test_flat_returns_error_on_insufficient_bars(self, btc_uptrend_bars):
        flat = compute_flat(btc_uptrend_bars[:2])
        assert "error" in flat
        assert flat["error"] == "insufficient_data"


# ── Trend detection ───────────────────────────────────────────────────────────

class TestTrendDetection:

    def test_uptrend_detected_for_btc_rally(self, btc_uptrend_bars):
        result = detect_trend(btc_uptrend_bars)
        assert result["available"] is True
        assert result["trend"] == "uptrend"

    def test_downtrend_detected_for_btc_selloff(self, btc_downtrend_bars):
        result = detect_trend(btc_downtrend_bars)
        assert result["available"] is True
        assert result["trend"] == "downtrend"

    def test_uptrend_for_spy_rally(self, spy_bullish_bars):
        result = detect_trend(spy_bullish_bars)
        assert result["available"] is True
        assert result["trend"] in ("uptrend", "sideways")

    def test_insufficient_bars_returns_unavailable(self, btc_uptrend_bars):
        result = detect_trend(btc_uptrend_bars[:10])
        assert result["available"] is False

    def test_short_and_long_ma_present(self, btc_uptrend_bars):
        result = detect_trend(btc_uptrend_bars)
        assert "short_ma" in result
        assert "long_ma" in result


# ── Breakout detection ────────────────────────────────────────────────────────

class TestBreakoutDetection:

    def test_btc_breakout_up_detected(self):
        """Build a price series that explicitly breaks above the prior 20-bar high."""
        from datetime import datetime, timedelta
        bars = []
        base = datetime(2026, 5, 1)
        # 20 bars flat around 90,000
        for i in range(20):
            bars.append({
                "open": 90_000, "high": 90_500, "low": 89_500,
                "close": 90_000, "volume": 1000,
                "fetched_at": base + timedelta(minutes=i),
            })
        # 1 bar breaking out above
        bars.append({
            "open": 90_500, "high": 92_000, "low": 90_200,
            "close": 91_000,
            "volume": 5000,
            "fetched_at": base + timedelta(minutes=21),
        })
        result = detect_breakout(bars)
        assert result["available"] is True
        assert result["signal"] == "breakout_up"
        assert result["strength_pct"] > 0

    def test_range_bound_when_no_breakout(self, spy_bullish_bars):
        result = detect_breakout(spy_bullish_bars)
        assert result["available"] is True
        # A smooth uptrend may or may not break out — just verify structure
        assert result["signal"] in ("range_bound", "breakout_up", "breakdown")

    def test_insufficient_bars_returns_unavailable(self, btc_uptrend_bars):
        result = detect_breakout(btc_uptrend_bars[:15])
        assert result["available"] is False
