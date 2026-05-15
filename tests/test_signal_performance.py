"""
Signal performance tracking tests.

Covers:
  • SignalOutcome model + signal_tracking/service.py
  • performance/service.py — metrics, drawdown, Sharpe, correlation
  • PaperTrade audit columns
  • executor.py audit_entry / audit_exit population
"""
from datetime import datetime, timedelta
import pytest

from app.signal_tracking.models import SignalOutcome
from app.signal_tracking.service import (
    create_signal_outcome,
    resolve_active_outcomes,
    get_recent_outcomes,
    link_trade_to_outcome,
    _check_price_outcome,
    _score,
)
from app.performance.service import (
    get_signal_performance,
    get_performance_timeseries,
    _max_drawdown,
    _sharpe,
    _confidence_correlation,
    _pearson,
)
from app.paper_trading.models import PaperTrade, PaperPortfolio
from app.paper_trading.executor import open_trade, close_trade, get_or_create_portfolio
from app.signals.models import TradingSignal


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_signal(
    db,
    asset="BTC",
    direction="BUY",
    confidence=72.0,
    entry_price=90_000.0,
    stop_loss=87_300.0,
    take_profit=95_400.0,
    minutes_ago=1,
) -> dict:
    row = TradingSignal(
        asset=asset,
        signal=direction,
        confidence=confidence,
        time_horizon="swing",
        risk_level="medium",
        reasoning=["News/event flow is bullish (impact score: +3.0)"],
        event_ids=[],
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        generated_at=datetime.utcnow() - timedelta(minutes=minutes_ago),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.to_dict()


def _make_portfolio(db) -> PaperPortfolio:
    return get_or_create_portfolio(db)


def _insert_price(db, symbol="BTC", price=90_000.0):
    from app.market_data.models import PriceBar
    bar = PriceBar(
        symbol=symbol,
        asset_class="crypto",
        source="test",
        open=price, high=price * 1.001, low=price * 0.999, close=price,
        volume=1000.0,
        fetched_at=datetime.utcnow(),
    )
    db.add(bar)
    db.commit()


def _closed_trade(db, symbol="BTC", direction="BUY", pnl=15.0, pnl_pct=3.0, confidence=72.0):
    _make_portfolio(db)
    _insert_price(db, symbol, 90_000.0)
    row = PaperTrade(
        symbol=symbol,
        direction=direction,
        notional=500.0,
        entry_price=90_000.0,
        quantity=500 / 90_000.0,
        confidence=confidence,
        status="closed",
        exit_price=92_700.0,
        exit_reason="take_profit",
        pnl=pnl,
        pnl_pct=pnl_pct,
        opened_at=datetime.utcnow() - timedelta(hours=2),
        closed_at=datetime.utcnow() - timedelta(minutes=30),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ═══════════════════════════════════════════════════════════════════════════════
# SignalOutcome model
# ═══════════════════════════════════════════════════════════════════════════════

class TestSignalOutcomeModel:

    def test_to_dict_has_required_fields(self, db):
        sig = _make_signal(db)
        outcome = create_signal_outcome(db, sig)
        d = outcome.to_dict()
        required = {
            "id", "signal_id", "asset", "direction", "confidence",
            "status", "outcome", "price_at_signal", "created_at",
        }
        assert required.issubset(d.keys())

    def test_initial_status_is_active(self, db):
        sig = _make_signal(db)
        outcome = create_signal_outcome(db, sig)
        assert outcome.status == "active"
        assert outcome.outcome is None

    def test_price_at_signal_stored(self, db):
        sig = _make_signal(db, entry_price=91_000.0)
        outcome = create_signal_outcome(db, sig)
        assert outcome.price_at_signal == 91_000.0

    def test_stop_loss_and_take_profit_stored(self, db):
        sig = _make_signal(db, stop_loss=87_000.0, take_profit=96_000.0)
        outcome = create_signal_outcome(db, sig)
        assert outcome.stop_loss == 87_000.0
        assert outcome.take_profit == 96_000.0


# ═══════════════════════════════════════════════════════════════════════════════
# create_signal_outcome
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateSignalOutcome:

    def test_creates_outcome_for_valid_signal(self, db):
        sig = _make_signal(db)
        outcome = create_signal_outcome(db, sig)
        assert outcome is not None
        assert outcome.signal_id == sig["id"]

    def test_duplicate_create_returns_existing(self, db):
        sig = _make_signal(db)
        o1 = create_signal_outcome(db, sig)
        o2 = create_signal_outcome(db, sig)
        assert o1.id == o2.id

    def test_signal_without_id_returns_none(self, db):
        result = create_signal_outcome(db, {"asset": "BTC", "signal": "BUY", "confidence": 70.0})
        assert result is None

    def test_direction_matches_signal(self, db):
        sig = _make_signal(db, direction="SELL")
        outcome = create_signal_outcome(db, sig)
        assert outcome.direction == "SELL"

    def test_confidence_stored(self, db):
        sig = _make_signal(db, confidence=85.0)
        outcome = create_signal_outcome(db, sig)
        assert outcome.confidence == 85.0


# ═══════════════════════════════════════════════════════════════════════════════
# resolve_active_outcomes
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveActiveOutcomes:

    def test_no_active_outcomes_returns_0(self, db):
        count = resolve_active_outcomes(db)
        assert count == 0

    def test_expired_signal_gets_resolved(self, db):
        sig = _make_signal(db)
        outcome = create_signal_outcome(db, sig)
        # Force it to be old enough to expire (swing = 24h)
        outcome.created_at = datetime.utcnow() - timedelta(hours=25)
        db.commit()

        _insert_price(db, "BTC", 90_500.0)
        resolved = resolve_active_outcomes(db)
        assert resolved >= 1

        db.refresh(outcome)
        assert outcome.status == "expired"
        assert outcome.outcome == "expired"

    def test_win_outcome_when_take_profit_hit(self, db):
        sig = _make_signal(db, entry_price=90_000.0, take_profit=92_000.0)
        outcome = create_signal_outcome(db, sig)
        _insert_price(db, "BTC", 93_000.0)  # above take_profit

        resolve_active_outcomes(db)
        db.refresh(outcome)
        assert outcome.outcome == "win"
        assert outcome.status == "completed"

    def test_loss_outcome_when_stop_loss_hit(self, db):
        sig = _make_signal(db, entry_price=90_000.0, stop_loss=88_000.0)
        outcome = create_signal_outcome(db, sig)
        _insert_price(db, "BTC", 87_000.0)  # below stop_loss

        resolve_active_outcomes(db)
        db.refresh(outcome)
        assert outcome.outcome == "loss"

    def test_price_change_pct_calculated_on_resolve(self, db):
        sig = _make_signal(db, entry_price=90_000.0, take_profit=92_000.0)
        outcome = create_signal_outcome(db, sig)
        _insert_price(db, "BTC", 93_000.0)

        resolve_active_outcomes(db)
        db.refresh(outcome)
        assert outcome.price_change_pct is not None
        assert outcome.price_change_pct > 0

    def test_performance_score_set_on_win(self, db):
        sig = _make_signal(db, entry_price=90_000.0, take_profit=92_000.0)
        outcome = create_signal_outcome(db, sig)
        _insert_price(db, "BTC", 93_000.0)

        resolve_active_outcomes(db)
        db.refresh(outcome)
        assert outcome.performance_score is not None
        assert outcome.performance_score >= 60  # wins score 60+

    def test_resolved_at_set(self, db):
        sig = _make_signal(db)
        outcome = create_signal_outcome(db, sig)
        outcome.created_at = datetime.utcnow() - timedelta(hours=25)
        db.commit()

        _insert_price(db, "BTC", 90_500.0)
        resolve_active_outcomes(db)
        db.refresh(outcome)
        assert outcome.resolved_at is not None

    def test_hold_signals_not_resolved(self, db):
        sig = _make_signal(db, direction="HOLD")
        outcome = create_signal_outcome(db, sig)
        _insert_price(db, "BTC", 95_000.0)

        # Fresh HOLD signal should stay active even at big price move
        resolved = resolve_active_outcomes(db)
        db.refresh(outcome)
        assert outcome.status == "active"


# ═══════════════════════════════════════════════════════════════════════════════
# link_trade_to_outcome
# ═══════════════════════════════════════════════════════════════════════════════

class TestLinkTradeToOutcome:

    def test_links_trade_id_to_outcome(self, db):
        sig = _make_signal(db)
        outcome = create_signal_outcome(db, sig)
        link_trade_to_outcome(db, sig["id"], trade_id=42)
        db.refresh(outcome)
        assert outcome.trade_id == 42

    def test_missing_signal_id_does_not_raise(self, db):
        link_trade_to_outcome(db, None, trade_id=99)  # should be silent


# ═══════════════════════════════════════════════════════════════════════════════
# _check_price_outcome
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckPriceOutcome:

    def _outcome(self, direction="BUY", price=90_000.0, sl=87_000.0, tp=94_000.0):
        o = SignalOutcome(
            signal_id=1, asset="BTC", direction=direction,
            confidence=70.0, time_horizon="swing", status="active",
            price_at_signal=price, stop_loss=sl, take_profit=tp,
            created_at=datetime.utcnow(),
        )
        return o

    def test_buy_win_at_take_profit(self):
        o = self._outcome("BUY", 90_000, 87_000, 94_000)
        assert _check_price_outcome(o, 95_000) == "win"

    def test_buy_loss_at_stop_loss(self):
        o = self._outcome("BUY", 90_000, 87_000, 94_000)
        assert _check_price_outcome(o, 86_000) == "loss"

    def test_sell_win_at_take_profit(self):
        o = self._outcome("SELL", 90_000, 93_000, 85_000)
        assert _check_price_outcome(o, 84_000) == "win"

    def test_sell_loss_at_stop_loss(self):
        o = self._outcome("SELL", 90_000, 93_000, 85_000)
        assert _check_price_outcome(o, 94_000) == "loss"

    def test_no_levels_win_by_default_threshold(self):
        o = self._outcome("BUY", 90_000, None, None)
        # +3% default threshold for win
        assert _check_price_outcome(o, 92_700) == "win"

    def test_no_levels_loss_by_default_threshold(self):
        o = self._outcome("BUY", 90_000, None, None)
        assert _check_price_outcome(o, 87_200) == "loss"

    def test_within_thresholds_returns_none(self):
        o = self._outcome("BUY", 90_000, None, None)
        # +1% — within thresholds, no outcome yet
        assert _check_price_outcome(o, 90_900) is None


# ═══════════════════════════════════════════════════════════════════════════════
# _score
# ═══════════════════════════════════════════════════════════════════════════════

class TestScore:

    def test_win_scores_at_least_60(self):
        assert _score("win", 0.0) == 60.0

    def test_win_increases_with_magnitude(self):
        assert _score("win", 5.0) > _score("win", 1.0)

    def test_win_caps_at_100(self):
        assert _score("win", 100.0) == 100.0

    def test_loss_scores_at_most_40(self):
        assert _score("loss", 0.0) == 40.0

    def test_loss_decreases_with_magnitude(self):
        assert _score("loss", 5.0) < _score("loss", 1.0)

    def test_loss_floors_at_0(self):
        assert _score("loss", 100.0) == 0.0

    def test_neutral_is_50(self):
        assert _score("neutral", 0.0) == 50.0

    def test_expired_is_25(self):
        assert _score("expired", 0.0) == 25.0


# ═══════════════════════════════════════════════════════════════════════════════
# get_recent_outcomes
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetRecentOutcomes:

    def test_returns_empty_when_no_outcomes(self, db):
        results = get_recent_outcomes(db)
        assert results == []

    def test_returns_outcomes_ordered_by_newest(self, db):
        sig1 = _make_signal(db, asset="BTC", minutes_ago=10)
        sig2 = _make_signal(db, asset="ETH", minutes_ago=1)
        create_signal_outcome(db, sig1)
        create_signal_outcome(db, sig2)

        results = get_recent_outcomes(db, limit=2)
        assert results[0]["asset"] == "ETH"  # newest first

    def test_filter_by_status(self, db):
        sig = _make_signal(db)
        outcome = create_signal_outcome(db, sig)
        outcome.created_at = datetime.utcnow() - timedelta(hours=25)
        db.commit()
        _insert_price(db, "BTC", 90_500.0)
        resolve_active_outcomes(db)

        expired = get_recent_outcomes(db, status="expired")
        assert len(expired) >= 1

    def test_filter_by_asset(self, db):
        sig = _make_signal(db, asset="SPY")
        create_signal_outcome(db, sig)
        results = get_recent_outcomes(db, asset="SPY")
        assert all(r["asset"] == "SPY" for r in results)


# ═══════════════════════════════════════════════════════════════════════════════
# performance/service.py — _max_drawdown
# ═══════════════════════════════════════════════════════════════════════════════

class TestMaxDrawdown:

    def test_empty_returns_zero(self):
        result = _max_drawdown([], 10_000)
        assert result["max_drawdown_usd"] == 0.0

    def test_all_wins_zero_drawdown(self):
        result = _max_drawdown([100, 200, 150], 10_000)
        assert result["max_drawdown_usd"] == 0.0

    def test_single_loss_detected(self):
        result = _max_drawdown([100, -300, 50], 10_000)
        # Peak = 100, trough at 100-300=-200 → drawdown = 300
        assert result["max_drawdown_usd"] == 300.0

    def test_max_drawdown_pct_based_on_initial(self):
        result = _max_drawdown([-500], 10_000)
        assert result["max_drawdown_pct"] == pytest.approx(5.0)

    def test_sequential_losses_accumulate(self):
        result = _max_drawdown([50, -100, -100, -100], 10_000)
        # Peak = 50, running: 50 → -50 → -150 → -250, drawdown = 50 - (-250) = 300
        assert result["max_drawdown_usd"] == 300.0


# ═══════════════════════════════════════════════════════════════════════════════
# performance/service.py — _sharpe
# ═══════════════════════════════════════════════════════════════════════════════

class TestSharpe:

    def test_fewer_than_2_returns_none(self):
        assert _sharpe([]) is None
        assert _sharpe([3.0]) is None

    def test_zero_std_returns_none(self):
        assert _sharpe([3.0, 3.0, 3.0]) is None

    def test_positive_for_consistent_wins(self):
        result = _sharpe([3.0, 2.5, 3.5, 2.8, 3.2])
        assert result is not None
        assert result > 0

    def test_negative_for_consistent_losses(self):
        result = _sharpe([-2.0, -3.0, -1.5, -2.5])
        assert result is not None
        assert result < 0


# ═══════════════════════════════════════════════════════════════════════════════
# performance/service.py — _confidence_correlation
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfidenceCorrelation:

    def _make_outcome(self, confidence, outcome_str):
        o = SignalOutcome(
            signal_id=1, asset="BTC", direction="BUY",
            confidence=confidence, time_horizon="swing",
            status="completed", outcome=outcome_str,
            price_at_signal=90_000, created_at=datetime.utcnow(),
        )
        return o

    def test_fewer_than_3_returns_none(self):
        outcomes = [self._make_outcome(70, "win"), self._make_outcome(60, "loss")]
        assert _confidence_correlation(outcomes) is None

    def test_positive_when_high_confidence_wins(self):
        outcomes = [
            self._make_outcome(80, "win"),
            self._make_outcome(85, "win"),
            self._make_outcome(50, "loss"),
            self._make_outcome(45, "loss"),
            self._make_outcome(90, "win"),
        ]
        corr = _confidence_correlation(outcomes)
        assert corr is not None
        assert corr > 0  # higher confidence → more wins

    def test_negative_when_high_confidence_loses(self):
        outcomes = [
            self._make_outcome(80, "loss"),
            self._make_outcome(85, "loss"),
            self._make_outcome(50, "win"),
            self._make_outcome(45, "win"),
            self._make_outcome(90, "loss"),
        ]
        corr = _confidence_correlation(outcomes)
        assert corr is not None
        assert corr < 0


# ═══════════════════════════════════════════════════════════════════════════════
# performance/service.py — _pearson
# ═══════════════════════════════════════════════════════════════════════════════

class TestPearson:

    def test_perfect_positive_correlation(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert _pearson(x, x) == pytest.approx(1.0)

    def test_perfect_negative_correlation(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [5.0, 4.0, 3.0, 2.0, 1.0]
        assert _pearson(x, y) == pytest.approx(-1.0)

    def test_zero_std_returns_0(self):
        x = [3.0, 3.0, 3.0]
        y = [1.0, 2.0, 3.0]
        assert _pearson(x, y) == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# get_signal_performance (integration)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetSignalPerformance:

    def test_empty_db_returns_valid_structure(self, db):
        result = get_signal_performance(db)
        assert "summary" in result
        assert "risk_metrics" in result
        assert "by_asset" in result
        assert "by_regime" in result
        assert "by_direction" in result

    def test_win_rate_0_when_no_data(self, db):
        result = get_signal_performance(db)
        assert result["summary"]["win_rate_pct"] == 0.0

    def test_win_rate_computed_from_outcomes(self, db):
        sig = _make_signal(db)
        outcome = create_signal_outcome(db, sig)
        outcome.status = "completed"
        outcome.outcome = "win"
        outcome.performance_score = 75.0
        db.commit()

        result = get_signal_performance(db)
        assert result["summary"]["win_count"] == 1
        assert result["summary"]["win_rate_pct"] == 100.0

    def test_by_asset_breakdown_populated(self, db):
        sig = _make_signal(db, asset="BTC")
        outcome = create_signal_outcome(db, sig)
        outcome.status = "completed"
        outcome.outcome = "win"
        db.commit()

        result = get_signal_performance(db)
        assert "BTC" in result["by_asset"]

    def test_max_drawdown_from_trades(self, db):
        _closed_trade(db, pnl=100.0)
        _closed_trade(db, pnl=-300.0)
        result = get_signal_performance(db)
        dd = result["risk_metrics"]["max_drawdown_usd"]
        assert dd > 0


# ═══════════════════════════════════════════════════════════════════════════════
# get_performance_timeseries
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetPerformanceTimeseries:

    def test_empty_returns_valid_structure(self, db):
        result = get_performance_timeseries(db)
        assert "series" in result
        assert "initial_balance" in result
        assert result["total_trades"] == 0

    def test_series_has_cumulative_pnl(self, db):
        _closed_trade(db, pnl=50.0)
        _closed_trade(db, pnl=30.0)
        result = get_performance_timeseries(db)
        series = result["series"]
        assert len(series) == 2
        # Second entry should have cumulative = 80
        assert series[-1]["cumulative_pnl"] == pytest.approx(80.0)

    def test_final_equity_reflects_pnl(self, db):
        _closed_trade(db, pnl=200.0)
        result = get_performance_timeseries(db)
        assert result["final_equity"] == pytest.approx(10_200.0)


# ═══════════════════════════════════════════════════════════════════════════════
# PaperTrade audit columns
# ═══════════════════════════════════════════════════════════════════════════════

class TestPaperTradeAuditColumns:

    def test_open_trade_stores_audit_entry(self, db):
        _make_portfolio(db)
        _insert_price(db, "BTC", 90_000.0)

        audit = {
            "signal_reasoning": ["RSI oversold", "Bullish event"],
            "market_regime":    "risk_on",
            "confidence":       72.0,
        }
        trade = open_trade(
            db, "BTC", "BUY", 90_000.0,
            stop_loss=87_000.0, take_profit=95_400.0,
            audit_data=audit, notional=500.0,
        )
        assert trade is not None
        assert trade.audit_entry is not None
        assert trade.audit_entry["market_regime"] == "risk_on"

    def test_open_trade_stores_regime_at_open(self, db):
        _make_portfolio(db)
        audit = {"market_regime": "trending"}
        trade = open_trade(db, "ETH", "BUY", 3000.0, audit_data=audit, notional=500.0)
        assert trade.regime_at_open == "trending"

    def test_close_trade_stores_audit_exit(self, db):
        _make_portfolio(db)
        trade = open_trade(db, "BTC", "BUY", 90_000.0, notional=500.0)
        closed = close_trade(db, trade, 93_000.0, exit_reason="take_profit")
        assert closed.audit_exit is not None
        assert closed.audit_exit["exit_reason"] == "take_profit"
        assert closed.audit_exit["outcome"] == "win"

    def test_audit_exit_contains_pnl(self, db):
        _make_portfolio(db)
        trade = open_trade(db, "BTC", "BUY", 90_000.0, notional=500.0)
        closed = close_trade(db, trade, 87_000.0, exit_reason="stop_loss")
        assert closed.audit_exit["outcome"] == "loss"
        assert closed.audit_exit["pnl_usd"] < 0

    def test_audit_exit_outcome_explanation_is_string(self, db):
        _make_portfolio(db)
        trade = open_trade(db, "BTC", "BUY", 90_000.0, notional=500.0)
        closed = close_trade(db, trade, 93_000.0, exit_reason="take_profit")
        assert isinstance(closed.audit_exit["outcome_explanation"], str)
        assert len(closed.audit_exit["outcome_explanation"]) > 10
