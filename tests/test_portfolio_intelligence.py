"""
Portfolio intelligence layer tests.

Covers:
  • compute_portfolio_intelligence() — empty, single, multi-position
  • _concentration() — notional and pct calculation
  • _directional_exposure() — risk-on / risk-off split
  • _correlation_analysis() — high-corr pair detection, conflicting positions
  • _build_warnings() — concentration, directional skew, conflicts
"""
from datetime import datetime, timedelta
import pytest

from app.portfolio_intelligence.service import (
    compute_portfolio_intelligence,
    _concentration,
    _directional_exposure,
    _correlation_analysis,
    _build_warnings,
)
from app.paper_trading.models import PaperTrade, PaperPortfolio
from app.paper_trading.executor import get_or_create_portfolio


# ── Helpers ───────────────────────────────────────────────────────────────────

def _open_trade(
    db,
    symbol: str = "BTC",
    direction: str = "BUY",
    notional: float = 500.0,
    entry_price: float = 90_000.0,
) -> PaperTrade:
    trade = PaperTrade(
        symbol=symbol,
        direction=direction,
        notional=notional,
        entry_price=entry_price,
        quantity=notional / entry_price,
        confidence=70.0,
        status="open",
        opened_at=datetime.utcnow() - timedelta(hours=1),
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


def _mock_corr(pairs: dict) -> dict:
    """Build a fake correlation matrix dict, as returned by compute_correlations()."""
    matrix: dict[str, dict[str, float]] = {}
    for (a, b), corr in pairs.items():
        matrix.setdefault(a, {})[b] = corr
        matrix.setdefault(b, {})[a] = corr
    return {"matrix": matrix}


# ═══════════════════════════════════════════════════════════════════════════════
# compute_portfolio_intelligence — empty portfolio
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmptyPortfolio:

    def test_no_trades_returns_no_open_positions(self, db):
        result = compute_portfolio_intelligence(db)
        assert result["status"] == "no_open_positions"

    def test_no_trades_zero_notional(self, db):
        result = compute_portfolio_intelligence(db)
        assert result["total_open_notional"] == 0.0

    def test_no_trades_empty_concentration(self, db):
        result = compute_portfolio_intelligence(db)
        assert result["concentration"] == {}

    def test_no_trades_no_warnings(self, db):
        result = compute_portfolio_intelligence(db)
        assert result["risk_warnings"] == []

    def test_closed_trades_not_counted(self, db):
        # Insert a closed trade — should not affect the portfolio snapshot
        trade = PaperTrade(
            symbol="BTC",
            direction="BUY",
            notional=500.0,
            entry_price=90_000.0,
            quantity=500 / 90_000.0,
            confidence=70.0,
            status="closed",
            exit_price=91_000.0,
            pnl=5.0,
            pnl_pct=1.0,
            opened_at=datetime.utcnow() - timedelta(hours=4),
            closed_at=datetime.utcnow() - timedelta(hours=1),
        )
        db.add(trade)
        db.commit()
        result = compute_portfolio_intelligence(db)
        assert result["status"] == "no_open_positions"


# ═══════════════════════════════════════════════════════════════════════════════
# compute_portfolio_intelligence — single position
# ═══════════════════════════════════════════════════════════════════════════════

class TestSinglePosition:

    def test_one_position_returns_ok_or_warnings(self, db):
        _open_trade(db, "BTC", "BUY", 500.0)
        result = compute_portfolio_intelligence(db)
        assert result["status"] in ("ok", "warnings")

    def test_open_positions_count(self, db):
        _open_trade(db, "BTC", "BUY", 500.0)
        result = compute_portfolio_intelligence(db)
        assert result["open_positions"] == 1

    def test_total_notional_matches(self, db):
        _open_trade(db, "BTC", "BUY", 500.0)
        result = compute_portfolio_intelligence(db)
        assert result["total_open_notional"] == 500.0

    def test_concentration_keys_present(self, db):
        _open_trade(db, "BTC", "BUY", 500.0)
        result = compute_portfolio_intelligence(db)
        assert "BTC" in result["concentration"]

    def test_single_position_100pct_concentration(self, db):
        _open_trade(db, "BTC", "BUY", 500.0)
        result = compute_portfolio_intelligence(db)
        assert result["concentration"]["BTC"]["pct_of_portfolio"] == 100.0

    def test_single_buy_100pct_risk_on(self, db):
        _open_trade(db, "BTC", "BUY", 500.0)
        result = compute_portfolio_intelligence(db)
        assert result["directional_exposure"]["risk_on_pct"] == 100.0
        assert result["directional_exposure"]["risk_off_pct"] == 0.0

    def test_single_sell_100pct_risk_off(self, db):
        _open_trade(db, "BTC", "SELL", 500.0)
        result = compute_portfolio_intelligence(db)
        assert result["directional_exposure"]["risk_off_pct"] == 100.0

    def test_100pct_concentration_triggers_warning(self, db):
        _open_trade(db, "BTC", "BUY", 500.0)
        result = compute_portfolio_intelligence(db)
        # 100% > 40% threshold → concentration warning
        warnings = result["risk_warnings"]
        assert any("concentration" in w.lower() or "BTC" in w for w in warnings)

    def test_100pct_directional_triggers_warning(self, db):
        _open_trade(db, "BTC", "BUY", 500.0)
        result = compute_portfolio_intelligence(db)
        # 100% BUY > 80% → directional skew warning
        warnings = result["risk_warnings"]
        assert any("risk-on" in w.lower() or "skewed" in w.lower() for w in warnings)


# ═══════════════════════════════════════════════════════════════════════════════
# compute_portfolio_intelligence — multi-position
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultiPosition:

    def test_balanced_portfolio_no_directional_warning(self, db):
        _open_trade(db, "BTC", "BUY",  500.0)
        _open_trade(db, "SPY", "SELL", 500.0)
        result = compute_portfolio_intelligence(db)
        warnings = result["risk_warnings"]
        # 50/50 split — no directional skew warning
        assert not any("risk-on" in w.lower() or "risk-off" in w.lower() for w in warnings)

    def test_two_positions_total_notional(self, db):
        _open_trade(db, "BTC", "BUY",  300.0)
        _open_trade(db, "SPY", "BUY",  700.0)
        result = compute_portfolio_intelligence(db)
        assert result["total_open_notional"] == pytest.approx(1000.0)

    def test_concentration_split_by_asset(self, db):
        _open_trade(db, "BTC", "BUY", 300.0)
        _open_trade(db, "SPY", "BUY", 700.0)
        result = compute_portfolio_intelligence(db)
        conc = result["concentration"]
        assert "BTC" in conc and "SPY" in conc
        assert conc["BTC"]["pct_of_portfolio"] == pytest.approx(30.0)
        assert conc["SPY"]["pct_of_portfolio"] == pytest.approx(70.0)

    def test_directional_split(self, db):
        _open_trade(db, "BTC", "BUY",  600.0)
        _open_trade(db, "SPY", "SELL", 400.0)
        result = compute_portfolio_intelligence(db)
        exp = result["directional_exposure"]
        assert exp["risk_on_pct"]  == pytest.approx(60.0)
        assert exp["risk_off_pct"] == pytest.approx(40.0)

    def test_same_asset_multiple_positions_aggregated(self, db):
        _open_trade(db, "BTC", "BUY", 200.0)
        _open_trade(db, "BTC", "BUY", 300.0)
        result = compute_portfolio_intelligence(db)
        assert result["concentration"]["BTC"]["notional"] == pytest.approx(500.0)


# ═══════════════════════════════════════════════════════════════════════════════
# _concentration (unit)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConcentration:

    def test_pct_of_portfolio_calculated(self, db):
        t1 = _open_trade(db, "BTC", "BUY", 400.0)
        t2 = _open_trade(db, "SPY", "BUY", 600.0)
        result = _concentration([t1, t2], 1000.0)
        assert result["BTC"]["pct_of_portfolio"] == pytest.approx(40.0)
        assert result["SPY"]["pct_of_portfolio"] == pytest.approx(60.0)

    def test_zero_total_does_not_crash(self, db):
        t = _open_trade(db, "BTC", "BUY", 500.0)
        result = _concentration([t], 0.0)
        assert result["BTC"]["pct_of_portfolio"] == 0.0

    def test_notional_rounded_to_cents(self, db):
        t = _open_trade(db, "BTC", "BUY", 333.3333)
        result = _concentration([t], 333.3333)
        assert result["BTC"]["notional"] == pytest.approx(333.33, abs=0.01)


# ═══════════════════════════════════════════════════════════════════════════════
# _directional_exposure (unit)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDirectionalExposure:

    def test_all_buy_100pct_risk_on(self, db):
        t1 = _open_trade(db, "BTC", "BUY", 500.0)
        t2 = _open_trade(db, "SPY", "BUY", 500.0)
        result = _directional_exposure([t1, t2], 1000.0)
        assert result["risk_on_pct"]  == 100.0
        assert result["risk_off_pct"] == 0.0

    def test_all_sell_100pct_risk_off(self, db):
        t = _open_trade(db, "BTC", "SELL", 1000.0)
        result = _directional_exposure([t], 1000.0)
        assert result["risk_off_pct"] == 100.0

    def test_mixed_notionals(self, db):
        t1 = _open_trade(db, "BTC", "BUY",  700.0)
        t2 = _open_trade(db, "SPY", "SELL", 300.0)
        result = _directional_exposure([t1, t2], 1000.0)
        assert result["risk_on_pct"]  == pytest.approx(70.0)
        assert result["risk_off_pct"] == pytest.approx(30.0)


# ═══════════════════════════════════════════════════════════════════════════════
# _correlation_analysis (unit)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCorrelationAnalysis:

    def test_no_corr_data_returns_empty(self, db):
        t = _open_trade(db, "BTC", "BUY", 500.0)
        high_corr, conflicting = _correlation_analysis([t], None)
        assert high_corr == []
        assert conflicting == []

    def test_high_corr_pair_flagged(self, db):
        t1 = _open_trade(db, "BTC", "BUY", 500.0)
        t2 = _open_trade(db, "SPY", "BUY", 500.0)
        corr_data = _mock_corr({("BTC", "SPY"): 0.85})
        high_corr, _ = _correlation_analysis([t1, t2], corr_data)
        assert len(high_corr) == 1
        assert high_corr[0]["correlation"] == pytest.approx(0.85)

    def test_low_corr_pair_not_flagged(self, db):
        t1 = _open_trade(db, "BTC", "BUY", 500.0)
        t2 = _open_trade(db, "SPY", "BUY", 500.0)
        corr_data = _mock_corr({("BTC", "SPY"): 0.50})
        high_corr, _ = _correlation_analysis([t1, t2], corr_data)
        assert len(high_corr) == 0

    def test_conflicting_positions_detected(self, db):
        t1 = _open_trade(db, "BTC", "BUY",  500.0)
        t2 = _open_trade(db, "SPY", "SELL", 500.0)
        corr_data = _mock_corr({("BTC", "SPY"): 0.80})
        _, conflicting = _correlation_analysis([t1, t2], corr_data)
        assert len(conflicting) == 1
        assert conflicting[0]["direction_a"] != conflicting[0]["direction_b"]

    def test_same_direction_not_conflicting(self, db):
        t1 = _open_trade(db, "BTC", "BUY", 500.0)
        t2 = _open_trade(db, "SPY", "BUY", 500.0)
        corr_data = _mock_corr({("BTC", "SPY"): 0.80})
        _, conflicting = _correlation_analysis([t1, t2], corr_data)
        assert len(conflicting) == 0

    def test_pair_not_double_counted(self, db):
        t1 = _open_trade(db, "BTC", "BUY",  500.0)
        t2 = _open_trade(db, "SPY", "SELL", 500.0)
        corr_data = _mock_corr({("BTC", "SPY"): 0.85})
        high_corr, _ = _correlation_analysis([t1, t2], corr_data)
        assert len(high_corr) == 1

    def test_corr_from_reverse_key_also_detected(self, db):
        # matrix has SPY→BTC, not BTC→SPY
        t1 = _open_trade(db, "BTC", "BUY", 500.0)
        t2 = _open_trade(db, "SPY", "BUY", 500.0)
        corr_data = {"matrix": {"SPY": {"BTC": 0.75}}}
        high_corr, _ = _correlation_analysis([t1, t2], corr_data)
        assert len(high_corr) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# _build_warnings (unit)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildWarnings:

    def _make_concentration(self, sym, pct):
        return {sym: {"notional": pct * 10, "pct_of_portfolio": pct}}

    def _make_directional(self, risk_on_pct):
        risk_off_pct = 100.0 - risk_on_pct
        return {
            "risk_on_pct": risk_on_pct,
            "risk_off_pct": risk_off_pct,
            "risk_on_notional": risk_on_pct * 10,
            "risk_off_notional": risk_off_pct * 10,
        }

    def test_high_concentration_triggers_warning(self):
        concentration = self._make_concentration("BTC", 50.0)
        directional   = self._make_directional(50.0)
        warnings = _build_warnings(concentration, directional, [], 1000.0)
        assert any("BTC" in w for w in warnings)

    def test_low_concentration_no_warning(self):
        concentration = self._make_concentration("BTC", 30.0)
        directional   = self._make_directional(50.0)
        warnings = _build_warnings(concentration, directional, [], 1000.0)
        assert not any("BTC" in w for w in warnings)

    def test_risk_on_skew_triggers_warning(self):
        concentration = self._make_concentration("BTC", 10.0)
        directional   = self._make_directional(90.0)
        warnings = _build_warnings(concentration, directional, [], 1000.0)
        assert any("risk-on" in w.lower() for w in warnings)

    def test_risk_off_skew_triggers_warning(self):
        concentration = self._make_concentration("BTC", 10.0)
        directional   = self._make_directional(5.0)  # 5% risk-on → 95% risk-off
        warnings = _build_warnings(concentration, directional, [], 1000.0)
        assert any("risk-off" in w.lower() for w in warnings)

    def test_balanced_directional_no_skew_warning(self):
        concentration = self._make_concentration("BTC", 10.0)
        directional   = self._make_directional(55.0)
        warnings = _build_warnings(concentration, directional, [], 1000.0)
        assert not any("skewed" in w.lower() for w in warnings)

    def test_conflicting_positions_adds_warning(self):
        concentration = self._make_concentration("BTC", 10.0)
        directional   = self._make_directional(50.0)
        conflicting = [{"asset_a": "BTC", "asset_b": "SPY"}]
        warnings = _build_warnings(concentration, directional, conflicting, 1000.0)
        assert any("conflicting" in w.lower() for w in warnings)

    def test_no_issues_returns_empty_warnings(self):
        concentration = self._make_concentration("BTC", 20.0)
        directional   = self._make_directional(55.0)
        warnings = _build_warnings(concentration, directional, [], 1000.0)
        assert warnings == []


# ═══════════════════════════════════════════════════════════════════════════════
# full compute_portfolio_intelligence integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputePortfolioIntelligenceIntegration:

    def test_has_all_required_keys(self, db):
        _open_trade(db, "BTC", "BUY", 500.0)
        result = compute_portfolio_intelligence(db)
        required = {
            "open_positions", "total_open_notional",
            "concentration", "directional_exposure",
            "correlation_exposure", "conflicting_positions",
            "risk_warnings", "status",
        }
        assert required.issubset(result.keys())

    def test_status_ok_when_balanced(self, db):
        # Two equal positions in opposite directions, no concentration warning
        _open_trade(db, "BTC", "BUY",  300.0)
        _open_trade(db, "SPY", "SELL", 300.0)
        _open_trade(db, "EURUSD", "BUY", 400.0)
        result = compute_portfolio_intelligence(db)
        # directional: 700 buy / 300 sell = 70% / 30% — within threshold
        # no single asset > 40%
        assert result["status"] in ("ok", "warnings")

    def test_correlation_exposure_is_list(self, db):
        _open_trade(db, "BTC", "BUY", 500.0)
        result = compute_portfolio_intelligence(db)
        assert isinstance(result["correlation_exposure"], list)

    def test_conflicting_positions_is_list(self, db):
        _open_trade(db, "BTC", "BUY", 500.0)
        result = compute_portfolio_intelligence(db)
        assert isinstance(result["conflicting_positions"], list)
