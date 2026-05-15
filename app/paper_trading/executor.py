from datetime import datetime
from sqlalchemy.orm import Session
from app.paper_trading.models import PaperTrade, PaperPortfolio
from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_TRADE_NOTIONAL = 500.0   # USD per trade
INITIAL_BALANCE        = 10000.0


def get_or_create_portfolio(db: Session) -> PaperPortfolio:
    portfolio = db.query(PaperPortfolio).filter(PaperPortfolio.id == 1).first()
    if not portfolio:
        portfolio = PaperPortfolio(
            id=1,
            initial_balance=INITIAL_BALANCE,
            current_balance=INITIAL_BALANCE,
        )
        db.add(portfolio)
        db.commit()
        db.refresh(portfolio)
    return portfolio


def open_trade(
    db: Session,
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    signal_id: int | None = None,
    confidence: float | None = None,
    notional: float = DEFAULT_TRADE_NOTIONAL,
    audit_data: dict | None = None,
) -> PaperTrade | None:
    """Open a new paper trade if the portfolio has sufficient balance."""
    portfolio = get_or_create_portfolio(db)

    if portfolio.current_balance < notional:
        logger.warning(f"Paper trading: insufficient balance to open {symbol} trade "
                       f"(need {notional}, have {portfolio.current_balance:.2f})")
        return None

    # Check for existing open position on the same symbol
    existing = (
        db.query(PaperTrade)
        .filter(PaperTrade.symbol == symbol, PaperTrade.status == "open")
        .first()
    )
    if existing:
        logger.info(f"Paper trading: position already open for {symbol}, skipping")
        return None

    quantity     = notional / entry_price
    regime_label = (audit_data or {}).get("market_regime")

    trade = PaperTrade(
        symbol=symbol,
        direction=direction,
        notional=notional,
        entry_price=entry_price,
        quantity=quantity,
        stop_loss=stop_loss,
        take_profit=take_profit,
        signal_id=signal_id,
        confidence=confidence,
        status="open",
        opened_at=datetime.utcnow(),
        regime_at_open=regime_label,
        audit_entry=audit_data,
    )
    db.add(trade)

    portfolio.current_balance -= notional
    portfolio.trade_count     += 1
    portfolio.updated_at       = datetime.utcnow()

    db.commit()
    db.refresh(trade)
    logger.info(f"Paper trading: opened {direction} {symbol} @ {entry_price} "
                f"notional=${notional} qty={quantity:.6f}")
    return trade


def close_trade(
    db: Session,
    trade: PaperTrade,
    exit_price: float,
    exit_reason: str = "manual",
    audit_exit: dict | None = None,
) -> PaperTrade:
    """Close an open trade, calculate realized PnL, and update the portfolio."""
    portfolio = get_or_create_portfolio(db)

    pnl_usd, pnl_pct = trade.unrealized_pnl(exit_price)

    exit_explanation = _build_exit_explanation(exit_reason, pnl_usd, pnl_pct, trade)

    trade.status         = "closed"
    trade.exit_price     = exit_price
    trade.exit_reason    = exit_reason
    trade.pnl            = pnl_usd
    trade.pnl_pct        = pnl_pct
    trade.closed_at      = datetime.utcnow()
    trade.audit_exit     = audit_exit or exit_explanation

    # Return notional + profit (or minus loss) to portfolio
    portfolio.current_balance += trade.notional + pnl_usd
    portfolio.total_pnl       += pnl_usd
    portfolio.total_pnl_pct    = round(
        (portfolio.current_balance - portfolio.initial_balance) / portfolio.initial_balance * 100, 2
    )

    if pnl_usd >= 0:
        portfolio.win_count  += 1
    else:
        portfolio.loss_count += 1
    portfolio.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(trade)
    logger.info(f"Paper trading: closed {trade.direction} {trade.symbol} @ {exit_price} "
                f"PnL={pnl_usd:+.2f} USD ({pnl_pct:+.2f}%) reason={exit_reason}")
    return trade


def _build_exit_explanation(
    exit_reason: str, pnl_usd: float, pnl_pct: float, trade: PaperTrade
) -> dict:
    outcome = "win" if pnl_usd >= 0 else "loss"
    reason_labels = {
        "take_profit": "Take-profit target reached — trade closed in profit as planned",
        "stop_loss":   "Stop-loss triggered — trade closed to limit downside",
        "manual":      "Trade manually closed by operator",
        "expired":     "Signal horizon expired — trade closed at current market price",
    }
    explanation = reason_labels.get(exit_reason, f"Trade closed: {exit_reason}")
    if outcome == "win":
        explanation += f" | Result: +{pnl_usd:.2f} USD (+{pnl_pct:.2f}%)"
    else:
        explanation += f" | Result: {pnl_usd:.2f} USD ({pnl_pct:.2f}%)"

    return {
        "exit_reason":       exit_reason,
        "outcome":           outcome,
        "pnl_usd":           round(pnl_usd, 2),
        "pnl_pct":           round(pnl_pct, 2),
        "exit_price":        trade.exit_price if trade.exit_price else None,
        "outcome_explanation": explanation,
    }
