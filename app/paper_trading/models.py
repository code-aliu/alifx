from datetime import datetime
from sqlalchemy import String, Float, DateTime, Integer, Boolean, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PaperPortfolio(Base):
    """Single portfolio record — always ID=1. Tracks cash and realized PnL."""
    __tablename__ = "paper_portfolio"

    id:              Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    initial_balance: Mapped[float] = mapped_column(Float, default=10000.0, nullable=False)
    current_balance: Mapped[float] = mapped_column(Float, default=10000.0, nullable=False)
    total_pnl:       Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_pnl_pct:   Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    win_count:       Mapped[int]   = mapped_column(Integer, default=0, nullable=False)
    loss_count:      Mapped[int]   = mapped_column(Integer, default=0, nullable=False)
    trade_count:     Mapped[int]   = mapped_column(Integer, default=0, nullable=False)
    updated_at:      Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def win_rate(self) -> float:
        total = self.win_count + self.loss_count
        return round(self.win_count / total * 100, 1) if total > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "id":              self.id,
            "initial_balance": self.initial_balance,
            "current_balance": round(self.current_balance, 2),
            "total_pnl":       round(self.total_pnl, 2),
            "total_pnl_pct":   round(self.total_pnl_pct, 2),
            "win_count":       self.win_count,
            "loss_count":      self.loss_count,
            "trade_count":     self.trade_count,
            "win_rate":        self.win_rate,
            "updated_at":      self.updated_at.isoformat(),
        }


class PaperTrade(Base):
    """A single simulated trade — notional-value based, no fractional shares needed."""
    __tablename__ = "paper_trades"

    id:           Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol:       Mapped[str]   = mapped_column(String(20), nullable=False)
    direction:    Mapped[str]   = mapped_column(String(5), nullable=False)   # BUY | SELL
    notional:     Mapped[float] = mapped_column(Float, nullable=False)       # USD amount committed
    entry_price:  Mapped[float] = mapped_column(Float, nullable=False)
    quantity:     Mapped[float] = mapped_column(Float, nullable=False)       # notional / entry_price
    stop_loss:    Mapped[float] = mapped_column(Float, nullable=True)
    take_profit:  Mapped[float] = mapped_column(Float, nullable=True)
    signal_id:    Mapped[int]   = mapped_column(Integer, nullable=True)      # TradingSignal.id reference
    confidence:   Mapped[float] = mapped_column(Float, nullable=True)
    status:       Mapped[str]   = mapped_column(String(10), default="open", nullable=False)  # open | closed
    exit_price:   Mapped[float] = mapped_column(Float, nullable=True)
    exit_reason:  Mapped[str]   = mapped_column(String(20), nullable=True)   # take_profit | stop_loss | manual | expired
    pnl:          Mapped[float] = mapped_column(Float, nullable=True)        # realized PnL in USD
    pnl_pct:      Mapped[float] = mapped_column(Float, nullable=True)        # realized PnL %
    opened_at:    Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at:    Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Audit trail — snapshot of context at open/close
    regime_at_open:  Mapped[str | None]  = mapped_column(String(50), nullable=True)
    regime_at_close: Mapped[str | None]  = mapped_column(String(50), nullable=True)
    audit_entry:     Mapped[dict | None] = mapped_column(JSON, nullable=True)  # signal reasoning + events at open
    audit_exit:      Mapped[dict | None] = mapped_column(JSON, nullable=True)  # outcome explanation at close

    __table_args__ = (
        Index("ix_paper_trades_symbol_status", "symbol", "status"),
        Index("ix_paper_trades_opened_at", "opened_at"),
    )

    def unrealized_pnl(self, current_price: float) -> tuple[float, float]:
        """Return (pnl_usd, pnl_pct) for an open trade at current_price."""
        if self.direction == "BUY":
            pnl_usd = (current_price - self.entry_price) * self.quantity
        else:
            pnl_usd = (self.entry_price - current_price) * self.quantity
        pnl_pct = pnl_usd / self.notional * 100
        return round(pnl_usd, 2), round(pnl_pct, 2)

    def to_dict(self, current_price: float | None = None) -> dict:
        base = {
            "id":          self.id,
            "symbol":      self.symbol,
            "direction":   self.direction,
            "notional":    self.notional,
            "entry_price": self.entry_price,
            "quantity":    round(self.quantity, 8),
            "stop_loss":   self.stop_loss,
            "take_profit": self.take_profit,
            "confidence":  self.confidence,
            "status":      self.status,
            "exit_price":  self.exit_price,
            "exit_reason": self.exit_reason,
            "pnl":         round(self.pnl, 2) if self.pnl is not None else None,
            "pnl_pct":     round(self.pnl_pct, 2) if self.pnl_pct is not None else None,
            "opened_at":   self.opened_at.isoformat(),
            "closed_at":   self.closed_at.isoformat() if self.closed_at else None,
        }
        if self.status == "open" and current_price:
            upnl, upnl_pct = self.unrealized_pnl(current_price)
            base["unrealized_pnl"]     = upnl
            base["unrealized_pnl_pct"] = upnl_pct
            base["current_price"]      = current_price
        base["regime_at_open"]  = self.regime_at_open
        base["regime_at_close"] = self.regime_at_close
        base["audit_entry"]     = self.audit_entry
        base["audit_exit"]      = self.audit_exit
        return base
