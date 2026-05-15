from datetime import datetime
from sqlalchemy import String, Float, DateTime, Integer, JSON, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class SignalOutcome(Base):
    """One row per TradingSignal — tracks how each signal performed over time."""
    __tablename__ = "signal_outcomes"

    id:            Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id:     Mapped[int]   = mapped_column(Integer, nullable=False)       # FK → trading_signals.id
    asset:         Mapped[str]   = mapped_column(String(20), nullable=False)
    direction:     Mapped[str]   = mapped_column(String(10), nullable=False)    # BUY | SELL | HOLD
    confidence:    Mapped[float] = mapped_column(Float, nullable=False)
    time_horizon:  Mapped[str]   = mapped_column(String(20), nullable=False, default="swing")

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active | completed | expired | invalidated

    # Price context
    price_at_signal: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss:       Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit:     Mapped[float | None] = mapped_column(Float, nullable=True)
    price_at_close:  Mapped[float | None] = mapped_column(Float, nullable=True)
    price_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Outcome
    outcome: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # win | loss | neutral | expired

    # Context at generation time
    market_regime:     Mapped[str | None]  = mapped_column(String(50), nullable=True)
    event_ids:         Mapped[list | None] = mapped_column(JSON, nullable=True)
    trade_id:          Mapped[int | None]  = mapped_column(Integer, nullable=True)

    # Quality score (0–100)
    performance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at:  Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("signal_id", name="uq_signal_outcomes_signal_id"),
        Index("ix_signal_outcomes_asset",  "asset"),
        Index("ix_signal_outcomes_status", "status"),
    )

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "signal_id":        self.signal_id,
            "asset":            self.asset,
            "direction":        self.direction,
            "confidence":       self.confidence,
            "time_horizon":     self.time_horizon,
            "status":           self.status,
            "price_at_signal":  self.price_at_signal,
            "stop_loss":        self.stop_loss,
            "take_profit":      self.take_profit,
            "price_at_close":   self.price_at_close,
            "price_change_pct": self.price_change_pct,
            "outcome":          self.outcome,
            "market_regime":    self.market_regime,
            "event_ids":        self.event_ids or [],
            "trade_id":         self.trade_id,
            "performance_score":self.performance_score,
            "created_at":       self.created_at.isoformat(),
            "resolved_at":      self.resolved_at.isoformat() if self.resolved_at else None,
        }
