"""
Market intelligence gap tests — Q2, Q3, Q4.

Q2: "What changed in the market?"   → get_recent_changes
Q3: "Which event triggered this?"   → triggering_events in generate_signal
Q4: "What assets are correlated?"   → compute_correlations
"""
from datetime import datetime, timedelta

import pytest

from tests.conftest import make_market_event, make_linear_bars
from app.events.models import MarketEvent
from app.market_data.models import PriceBar


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_event(
    db,
    headline: str,
    category: str,
    sentiment: str,
    importance: str,
    affected_assets: list[str],
    extracted_at: datetime | None = None,
) -> MarketEvent:
    event = MarketEvent(
        news_article_id=None,
        headline=headline,
        category=category,
        sentiment=sentiment,
        importance=importance,
        affected_assets=affected_assets,
        keywords=[],
        llm_enriched=False,
        extraction_method="rule",
        extracted_at=extracted_at or datetime.utcnow(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _make_price_bars(db, symbol: str, closes: list[float]) -> None:
    """Insert synthetic PriceBar rows with the given closing prices."""
    base_time = datetime(2026, 5, 1, 0, 0, 0)
    for i, close in enumerate(closes):
        bar = PriceBar(
            symbol=symbol,
            asset_class="crypto",
            open=close,
            high=close * 1.001,
            low=close * 0.999,
            close=close,
            volume=1000.0,
            source="test",
            fetched_at=base_time + timedelta(hours=i),
        )
        db.add(bar)
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# Q2 — get_recent_changes
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetRecentChanges:

    def test_empty_db_returns_zero_counts(self, db):
        from app.events.service import get_recent_changes
        result = get_recent_changes(db, hours=6)
        assert result["current_event_count"] == 0
        assert result["prior_event_count"] == 0
        assert result["category_changes"] == []
        assert result["asset_changes"] == []

    def test_current_event_appears_in_category_changes(self, db):
        from app.events.service import get_recent_changes
        _make_event(db, "Fed cuts rates", "macroeconomic", "bullish", "high", ["SPY", "BTC"])
        result = get_recent_changes(db, hours=6)
        assert result["current_event_count"] == 1
        cats = {c["category"] for c in result["category_changes"]}
        assert "macroeconomic" in cats

    def test_old_event_does_not_appear_in_current_count(self, db):
        from app.events.service import get_recent_changes
        old_time = datetime.utcnow() - timedelta(hours=20)
        _make_event(db, "Old headline", "macroeconomic", "neutral", "low",
                    ["SPY"], extracted_at=old_time)
        result = get_recent_changes(db, hours=6)
        assert result["current_event_count"] == 0

    def test_prior_event_counted_in_prior_window(self, db):
        from app.events.service import get_recent_changes
        prior_time = datetime.utcnow() - timedelta(hours=9)
        _make_event(db, "Earlier headline", "macroeconomic", "bearish", "medium",
                    ["SPY"], extracted_at=prior_time)
        result = get_recent_changes(db, hours=6)
        assert result["prior_event_count"] == 1
        assert result["current_event_count"] == 0

    def test_positive_sentiment_shift_detected(self, db):
        from app.events.service import get_recent_changes
        # Prior window: bearish
        prior_time = datetime.utcnow() - timedelta(hours=9)
        _make_event(db, "Recession fears", "macroeconomic", "bearish", "high",
                    ["SPY"], extracted_at=prior_time)
        # Current window: bullish
        _make_event(db, "Fed pivots dovish", "macroeconomic", "bullish", "high",
                    ["SPY"])
        result = get_recent_changes(db, hours=6)
        macro = next(c for c in result["category_changes"] if c["category"] == "macroeconomic")
        assert macro["sentiment_shift"] > 0
        assert macro["shift_direction"] == "improving"

    def test_negative_sentiment_shift_detected(self, db):
        from app.events.service import get_recent_changes
        prior_time = datetime.utcnow() - timedelta(hours=9)
        _make_event(db, "Markets rally", "macroeconomic", "bullish", "high",
                    ["SPY"], extracted_at=prior_time)
        _make_event(db, "Inflation surge", "macroeconomic", "bearish", "high",
                    ["SPY"])
        result = get_recent_changes(db, hours=6)
        macro = next(c for c in result["category_changes"] if c["category"] == "macroeconomic")
        assert macro["sentiment_shift"] < 0
        assert macro["shift_direction"] == "deteriorating"

    def test_new_category_flagged(self, db):
        from app.events.service import get_recent_changes
        # Prior window has only macroeconomic
        prior_time = datetime.utcnow() - timedelta(hours=9)
        _make_event(db, "GDP growth", "macroeconomic", "bullish", "medium",
                    ["SPY"], extracted_at=prior_time)
        # Current window adds a new category
        _make_event(db, "Bitcoin ETF approved", "crypto", "bullish", "high",
                    ["BTC"])
        result = get_recent_changes(db, hours=6)
        assert "crypto" in result["new_categories"]

    def test_no_new_category_when_category_existed_in_prior(self, db):
        from app.events.service import get_recent_changes
        prior_time = datetime.utcnow() - timedelta(hours=9)
        _make_event(db, "GDP", "macroeconomic", "neutral", "medium",
                    ["SPY"], extracted_at=prior_time)
        _make_event(db, "Fed hike", "macroeconomic", "bearish", "high",
                    ["SPY"])
        result = get_recent_changes(db, hours=6)
        assert "macroeconomic" not in result["new_categories"]

    def test_asset_direction_bullish(self, db):
        from app.events.service import get_recent_changes
        _make_event(db, "Bitcoin ETF inflows", "crypto", "bullish", "high", ["BTC"])
        _make_event(db, "BTC adoption rising", "crypto", "bullish", "medium", ["BTC"])
        result = get_recent_changes(db, hours=6)
        btc = next(a for a in result["asset_changes"] if a["asset"] == "BTC")
        assert btc["direction"] == "bullish"
        assert btc["net_sentiment"] > 0.15

    def test_asset_direction_bearish(self, db):
        from app.events.service import get_recent_changes
        _make_event(db, "Crypto crackdown", "crypto", "bearish", "high", ["BTC"])
        _make_event(db, "Exchange hack", "crypto", "bearish", "high", ["BTC"])
        result = get_recent_changes(db, hours=6)
        btc = next(a for a in result["asset_changes"] if a["asset"] == "BTC")
        assert btc["direction"] == "bearish"
        assert btc["net_sentiment"] < -0.15

    def test_asset_direction_neutral(self, db):
        from app.events.service import get_recent_changes
        _make_event(db, "Mixed signals", "macroeconomic", "bullish", "low", ["SPY"])
        _make_event(db, "Uncertainty rises", "macroeconomic", "bearish", "low", ["SPY"])
        result = get_recent_changes(db, hours=6)
        spy = next(a for a in result["asset_changes"] if a["asset"] == "SPY")
        assert spy["direction"] == "neutral"

    def test_multiple_assets_in_same_event(self, db):
        from app.events.service import get_recent_changes
        _make_event(db, "Risk rally", "macroeconomic", "bullish", "high",
                    ["BTC", "SPY", "ETH"])
        result = get_recent_changes(db, hours=6)
        asset_names = {a["asset"] for a in result["asset_changes"]}
        assert {"BTC", "SPY", "ETH"}.issubset(asset_names)

    def test_category_changes_sorted_by_abs_shift(self, db):
        from app.events.service import get_recent_changes
        prior_time = datetime.utcnow() - timedelta(hours=9)
        # macroeconomic: small shift (both neutral in prior and bullish in current)
        _make_event(db, "Stable growth", "macroeconomic", "neutral", "medium",
                    ["SPY"], extracted_at=prior_time)
        _make_event(db, "Minor upside", "macroeconomic", "bullish", "low", ["SPY"])
        # geopolitical: large shift (prior bullish, current bearish)
        _make_event(db, "Peace talks", "geopolitical", "bullish", "high",
                    ["SPY"], extracted_at=prior_time)
        _make_event(db, "Conflict escalates", "geopolitical", "bearish", "high", ["SPY"])
        result = get_recent_changes(db, hours=6)
        shifts = [abs(c["sentiment_shift"]) for c in result["category_changes"]]
        assert shifts == sorted(shifts, reverse=True)

    def test_result_includes_required_keys(self, db):
        from app.events.service import get_recent_changes
        result = get_recent_changes(db, hours=6)
        required = {
            "period_hours", "current_event_count", "prior_event_count",
            "computed_at", "category_changes", "asset_changes", "new_categories",
        }
        assert required.issubset(result.keys())

    def test_period_hours_respected(self, db):
        from app.events.service import get_recent_changes
        result = get_recent_changes(db, hours=24)
        assert result["period_hours"] == 24


# ═══════════════════════════════════════════════════════════════════════════════
# Q3 — triggering_events in generate_signal
# ═══════════════════════════════════════════════════════════════════════════════

def _bullish_impact():
    return {"score": 3.0, "direction": "bullish", "strength": 0.8}


def _bullish_analysis():
    return {
        "indicators": {
            "rsi":        {"available": True, "value": 30, "signal": "oversold"},
            "ema":        {"available": True, "signal": "bullish"},
            "macd":       {"available": True, "trend": "bullish"},
            "volatility": {"available": True, "level": "medium"},
        },
        "breakout": {"available": False},
        "trend":    {"available": True, "trend": "uptrend"},
    }


class TestTriggeringEvents:

    def test_no_triggering_events_returns_empty_list(self):
        from app.signals.generator import generate_signal
        sig = generate_signal(
            symbol="BTC",
            impact=_bullish_impact(),
            analysis=_bullish_analysis(),
            current_price=90_000.0,
        )
        assert sig["triggering_events"] == []
        assert sig["event_ids"] == []

    def test_triggering_events_appear_in_output(self):
        from app.signals.generator import generate_signal
        events = [
            {"id": 1, "headline": "ETF inflows surge", "sentiment": "bullish",
             "importance": "high", "affected_assets": ["BTC"]},
        ]
        sig = generate_signal(
            symbol="BTC",
            impact=_bullish_impact(),
            analysis=_bullish_analysis(),
            current_price=90_000.0,
            triggering_events=events,
        )
        assert len(sig["triggering_events"]) == 1
        assert sig["triggering_events"][0]["id"] == 1

    def test_event_ids_populated(self):
        from app.signals.generator import generate_signal
        events = [
            {"id": 42, "headline": "BTC adoption", "sentiment": "bullish",
             "importance": "high", "affected_assets": ["BTC"]},
            {"id": 43, "headline": "Macro tailwind", "sentiment": "bullish",
             "importance": "medium", "affected_assets": ["BTC"]},
        ]
        sig = generate_signal(
            symbol="BTC",
            impact=_bullish_impact(),
            analysis=_bullish_analysis(),
            current_price=90_000.0,
            triggering_events=events,
        )
        assert set(sig["event_ids"]) == {42, 43}

    def test_events_without_id_excluded_from_event_ids(self):
        from app.signals.generator import generate_signal
        events = [
            {"headline": "No id event", "sentiment": "bullish",
             "importance": "low", "affected_assets": ["BTC"]},
        ]
        sig = generate_signal(
            symbol="BTC",
            impact=_bullish_impact(),
            analysis=_bullish_analysis(),
            current_price=90_000.0,
            triggering_events=events,
        )
        assert sig["triggering_events"] != []
        assert sig["event_ids"] == []

    def test_buy_signal_prefers_bullish_events(self):
        from app.signals.generator import generate_signal
        events = [
            {"id": 1, "headline": "Bear event", "sentiment": "bearish",
             "importance": "high", "affected_assets": ["BTC"]},
            {"id": 2, "headline": "Bull event A", "sentiment": "bullish",
             "importance": "high", "affected_assets": ["BTC"]},
            {"id": 3, "headline": "Bull event B", "sentiment": "bullish",
             "importance": "medium", "affected_assets": ["BTC"]},
        ]
        sig = generate_signal(
            symbol="BTC",
            impact=_bullish_impact(),
            analysis=_bullish_analysis(),
            current_price=90_000.0,
            triggering_events=events,
        )
        # BUY signal should prefer bullish events (ids 2 and 3)
        if sig["signal"] == "BUY":
            trigger_ids = {e["id"] for e in sig["triggering_events"]}
            assert 2 in trigger_ids or 3 in trigger_ids

    def test_max_three_triggers_returned(self):
        from app.signals.generator import generate_signal
        events = [
            {"id": i, "headline": f"Event {i}", "sentiment": "bullish",
             "importance": "high", "affected_assets": ["BTC"]}
            for i in range(1, 8)
        ]
        sig = generate_signal(
            symbol="BTC",
            impact=_bullish_impact(),
            analysis=_bullish_analysis(),
            current_price=90_000.0,
            triggering_events=events,
        )
        assert len(sig["triggering_events"]) <= 3

    def test_triggering_events_appear_in_reasoning(self):
        from app.signals.generator import generate_signal
        events = [
            {"id": 1, "headline": "Spot ETF approved by SEC",
             "sentiment": "bullish", "importance": "high",
             "affected_assets": ["BTC"]},
        ]
        sig = generate_signal(
            symbol="BTC",
            impact=_bullish_impact(),
            analysis=_bullish_analysis(),
            current_price=90_000.0,
            triggering_events=events,
        )
        reasoning_text = " ".join(sig["reasoning"])
        assert "Triggered by" in reasoning_text or "Spot ETF" in reasoning_text

    def test_hold_signal_includes_all_events_in_triggers(self):
        from app.signals.generator import generate_signal
        # HOLD: no event bias (neutral) → all events included without direction filter
        neutral_impact = {"score": 0.0, "direction": "neutral", "strength": 0.0}
        neutral_analysis = {
            "indicators": {
                "rsi":        {"available": False},
                "ema":        {"available": False},
                "macd":       {"available": False},
                "volatility": {"available": False},
            },
            "breakout": {"available": False},
            "trend":    {"available": False},
        }
        events = [
            {"id": 1, "headline": "Mixed signals", "sentiment": "bearish",
             "importance": "low", "affected_assets": ["BTC"]},
            {"id": 2, "headline": "Cautious tone", "sentiment": "bullish",
             "importance": "low", "affected_assets": ["BTC"]},
        ]
        sig = generate_signal(
            symbol="BTC",
            impact=neutral_impact,
            analysis=neutral_analysis,
            current_price=90_000.0,
            triggering_events=events,
        )
        assert sig["signal"] == "HOLD"
        # HOLD path includes all events (direction == "HOLD" condition)
        assert len(sig["triggering_events"]) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Q4 — compute_correlations
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeCorrelations:

    def test_empty_db_returns_empty_result(self, db):
        from app.analysis.service import compute_correlations
        result = compute_correlations(db, limit=60)
        assert result["assets"] == []
        assert result["matrix"] == {}
        assert result["top_pairs"] == []
        assert result["lookback_bars"] == 0

    def test_single_asset_no_pairs(self, db):
        from app.analysis.service import compute_correlations
        closes = [100.0 + i for i in range(10)]
        _make_price_bars(db, "BTC", closes)
        result = compute_correlations(db, limit=60)
        assert "BTC" in result["assets"]
        assert result["top_pairs"] == []

    def test_two_identical_series_have_correlation_near_one(self, db):
        from app.analysis.service import compute_correlations
        closes = [100.0 + i * 0.5 for i in range(20)]
        _make_price_bars(db, "BTC", closes)
        _make_price_bars(db, "ETH", closes)
        result = compute_correlations(db, limit=60)
        pair = next(
            (p for p in result["top_pairs"]
             if set([p["asset_a"], p["asset_b"]]) == {"BTC", "ETH"}),
            None,
        )
        assert pair is not None
        assert pair["correlation"] > 0.99

    def test_inverse_series_have_negative_correlation(self, db):
        from app.analysis.service import compute_correlations
        # Zigzag prices so returns are anti-phased: BTC up → ETH down each step
        btc = [100.0 + (2.0 if i % 2 == 0 else 0.0) for i in range(20)]
        eth = [100.0 - (2.0 if i % 2 == 0 else 0.0) for i in range(20)]
        _make_price_bars(db, "BTC", btc)
        _make_price_bars(db, "ETH", eth)
        result = compute_correlations(db, limit=60)
        pair = next(
            (p for p in result["top_pairs"]
             if set([p["asset_a"], p["asset_b"]]) == {"BTC", "ETH"}),
            None,
        )
        assert pair is not None
        assert pair["correlation"] < -0.9

    def test_matrix_is_symmetric(self, db):
        from app.analysis.service import compute_correlations
        closes_a = [100.0 + i for i in range(20)]
        closes_b = [200.0 + i * 0.3 for i in range(20)]
        _make_price_bars(db, "BTC", closes_a)
        _make_price_bars(db, "ETH", closes_b)
        result = compute_correlations(db, limit=60)
        mat = result["matrix"]
        if "BTC" in mat and "ETH" in mat:
            assert mat["BTC"]["ETH"] == mat["ETH"]["BTC"]

    def test_diagonal_is_one(self, db):
        from app.analysis.service import compute_correlations
        _make_price_bars(db, "BTC", [100.0 + i for i in range(20)])
        _make_price_bars(db, "ETH", [50.0  + i for i in range(20)])
        result = compute_correlations(db, limit=60)
        for sym in result["assets"]:
            assert result["matrix"][sym][sym] == 1.0

    def test_top_pairs_sorted_by_abs_correlation(self, db):
        from app.analysis.service import compute_correlations
        # BTC vs ETH: identical (corr ~1.0)
        closes = [100.0 + i for i in range(20)]
        _make_price_bars(db, "BTC", closes)
        _make_price_bars(db, "ETH", closes)
        # BTC vs SPY: inverse (corr ~ -1.0)
        inv = [120.0 - i for i in range(20)]
        _make_price_bars(db, "SPY", inv)
        result = compute_correlations(db, limit=60)
        if len(result["top_pairs"]) >= 2:
            corrs = [abs(p["correlation"]) for p in result["top_pairs"]]
            assert corrs == sorted(corrs, reverse=True)

    def test_relationship_labels_strongly_positive(self, db):
        from app.analysis.service import compute_correlations
        closes = [100.0 + i for i in range(20)]
        _make_price_bars(db, "BTC", closes)
        _make_price_bars(db, "ETH", closes)
        result = compute_correlations(db, limit=60)
        pair = next(
            (p for p in result["top_pairs"]
             if set([p["asset_a"], p["asset_b"]]) == {"BTC", "ETH"}),
            None,
        )
        assert pair["relationship"] == "strongly_positive"

    def test_relationship_labels_strongly_negative(self, db):
        from app.analysis.service import compute_correlations
        # Anti-phased zigzag: BTC up → ETH down each step
        btc = [100.0 + (2.0 if i % 2 == 0 else 0.0) for i in range(20)]
        eth = [100.0 - (2.0 if i % 2 == 0 else 0.0) for i in range(20)]
        _make_price_bars(db, "BTC", btc)
        _make_price_bars(db, "ETH", eth)
        result = compute_correlations(db, limit=60)
        pair = next(
            (p for p in result["top_pairs"]
             if set([p["asset_a"], p["asset_b"]]) == {"BTC", "ETH"}),
            None,
        )
        assert pair["relationship"] == "strongly_negative"

    def test_fewer_than_5_bars_yields_no_pair_correlations(self, db):
        from app.analysis.service import compute_correlations
        _make_price_bars(db, "BTC", [100.0, 101.0, 102.0])
        _make_price_bars(db, "ETH", [50.0, 51.0, 52.0])
        result = compute_correlations(db, limit=60)
        assert result["top_pairs"] == []

    def test_result_includes_computed_at(self, db):
        from app.analysis.service import compute_correlations
        result = compute_correlations(db, limit=60)
        assert "computed_at" in result
        assert isinstance(result["computed_at"], str)
