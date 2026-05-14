"""
Position monitor — runs every polling cycle.

For each open trade, checks the current price against stop-loss and take-profit.
Closes positions automatically when levels are hit.
"""
from sqlalchemy.orm import Session
from app.paper_trading.models import PaperTrade
from app.paper_trading.executor import close_trade
from app.market_data.service import get_latest_prices
from app.core.logging import get_logger

logger = get_logger(__name__)


def check_open_positions(db: Session) -> int:
    """Evaluate all open positions against current prices.

    Returns number of positions closed.
    """
    open_trades = (
        db.query(PaperTrade)
        .filter(PaperTrade.status == "open")
        .all()
    )
    if not open_trades:
        return 0

    latest = {p["symbol"]: p["close"] for p in get_latest_prices(db)}
    closed = 0

    for trade in open_trades:
        current_price = latest.get(trade.symbol)
        if not current_price:
            continue

        reason = _check_exit_condition(trade, current_price)
        if reason:
            close_trade(db, trade, current_price, exit_reason=reason)
            closed += 1

    if closed:
        logger.info(f"Paper trading monitor: closed {closed} positions")
    return closed


def _check_exit_condition(trade: PaperTrade, current_price: float) -> str | None:
    if trade.direction == "BUY":
        if trade.take_profit and current_price >= trade.take_profit:
            return "take_profit"
        if trade.stop_loss and current_price <= trade.stop_loss:
            return "stop_loss"
    elif trade.direction == "SELL":
        if trade.take_profit and current_price <= trade.take_profit:
            return "take_profit"
        if trade.stop_loss and current_price >= trade.stop_loss:
            return "stop_loss"
    return None
