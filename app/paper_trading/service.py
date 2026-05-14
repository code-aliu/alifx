from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.paper_trading.models import PaperTrade, PaperPortfolio
from app.paper_trading.executor import get_or_create_portfolio, open_trade, close_trade, DEFAULT_TRADE_NOTIONAL
from app.paper_trading.monitor import check_open_positions
from app.signals.service import run_signal_pipeline, get_latest_signals
from app.market_data.service import get_latest_prices
from app.core.logging import get_logger

logger = get_logger(__name__)

AUTO_TRADE_CONFIDENCE_THRESHOLD = 68.0  # only auto-execute high-confidence signals


def run_paper_trading_cycle(db: Session) -> dict:
    """Full paper trading cycle: monitor open positions, then auto-execute new signals."""
    closed  = check_open_positions(db)
    opened  = _auto_execute_signals(db)
    return {"positions_closed": closed, "positions_opened": opened}


def _auto_execute_signals(db: Session) -> int:
    """Open paper trades for high-confidence BUY/SELL signals that have no open position."""
    signals      = get_latest_signals(db)
    latest_prices = {p["symbol"]: p["close"] for p in get_latest_prices(db)}
    opened       = 0

    for signal in signals:
        if signal.get("signal") not in ("BUY", "SELL"):
            continue
        if (signal.get("confidence") or 0) < AUTO_TRADE_CONFIDENCE_THRESHOLD:
            continue

        symbol = signal["asset"]
        price  = latest_prices.get(symbol)
        if not price:
            continue

        trade = open_trade(
            db=db,
            symbol=symbol,
            direction=signal["signal"],
            entry_price=price,
            stop_loss=signal.get("stop_loss"),
            take_profit=signal.get("take_profit"),
            signal_id=signal.get("id"),
            confidence=signal.get("confidence"),
            notional=DEFAULT_TRADE_NOTIONAL,
        )
        if trade:
            opened += 1

    return opened


def get_portfolio_summary(db: Session) -> dict:
    """Return portfolio state with open position unrealized PnL."""
    portfolio    = get_or_create_portfolio(db)
    latest_prices = {p["symbol"]: p["close"] for p in get_latest_prices(db)}

    open_trades = (
        db.query(PaperTrade)
        .filter(PaperTrade.status == "open")
        .order_by(PaperTrade.opened_at.desc())
        .all()
    )

    open_positions = [t.to_dict(current_price=latest_prices.get(t.symbol)) for t in open_trades]
    total_unrealized = sum(p.get("unrealized_pnl", 0) for p in open_positions)
    equity = round(portfolio.current_balance + sum(t.notional for t in open_trades) + total_unrealized, 2)

    return {
        "portfolio":         portfolio.to_dict(),
        "equity":            equity,
        "total_unrealized":  round(total_unrealized, 2),
        "open_positions":    open_positions,
        "open_count":        len(open_positions),
    }


def get_trade_history(db: Session, limit: int = 50, status: str | None = None) -> list[dict]:
    query = db.query(PaperTrade)
    if status:
        query = query.filter(PaperTrade.status == status)
    trades = query.order_by(PaperTrade.opened_at.desc()).limit(limit).all()
    return [t.to_dict() for t in trades]


def get_stats(db: Session) -> dict:
    portfolio = get_or_create_portfolio(db)

    closed_trades = (
        db.query(PaperTrade)
        .filter(PaperTrade.status == "closed")
        .all()
    )

    if not closed_trades:
        return {"portfolio": portfolio.to_dict(), "trade_stats": {"message": "No closed trades yet"}}

    pnls       = [t.pnl for t in closed_trades if t.pnl is not None]
    winners    = [p for p in pnls if p >= 0]
    losers     = [p for p in pnls if p < 0]
    avg_win    = round(sum(winners) / len(winners), 2) if winners else 0
    avg_loss   = round(sum(losers) / len(losers), 2) if losers else 0
    best_trade = round(max(pnls), 2) if pnls else 0
    worst_trade = round(min(pnls), 2) if pnls else 0
    profit_factor = round(abs(sum(winners) / sum(losers)), 2) if losers and sum(losers) != 0 else None

    # Recent performance (last 7 days)
    cutoff    = datetime.utcnow() - timedelta(days=7)
    recent    = [t.pnl for t in closed_trades if t.closed_at and t.closed_at >= cutoff and t.pnl is not None]
    recent_pnl = round(sum(recent), 2)

    return {
        "portfolio": portfolio.to_dict(),
        "trade_stats": {
            "total_closed":    len(closed_trades),
            "win_count":       portfolio.win_count,
            "loss_count":      portfolio.loss_count,
            "win_rate_pct":    portfolio.win_rate,
            "avg_win_usd":     avg_win,
            "avg_loss_usd":    avg_loss,
            "best_trade_usd":  best_trade,
            "worst_trade_usd": worst_trade,
            "profit_factor":   profit_factor,
            "pnl_last_7d":     recent_pnl,
            "total_realized_pnl": round(portfolio.total_pnl, 2),
        },
    }


def manually_close_trade(db: Session, trade_id: int, current_prices: dict) -> PaperTrade | None:
    trade = db.query(PaperTrade).filter(PaperTrade.id == trade_id, PaperTrade.status == "open").first()
    if not trade:
        return None
    price = current_prices.get(trade.symbol)
    if not price:
        return None
    return close_trade(db, trade, price, exit_reason="manual")
