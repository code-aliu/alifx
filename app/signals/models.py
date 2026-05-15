from datetime import datetime
from sqlalchemy import String, Float, DateTime, Integer, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class TradingSignal(Base):
    __tablename__ = "trading_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset: Mapped[str] = mapped_column(String(20), nullable=False)
    signal: Mapped[str] = mapped_column(String(10), nullable=False)          # BUY | SELL | NEUTRAL | WATCH
    confidence: Mapped[float] = mapped_column(Float, nullable=False)         # 0–100
    time_horizon: Mapped[str] = mapped_column(String(20), nullable=False)    # scalp | intraday | swing | macro
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)      # low | medium | high
    reasoning: Mapped[list] = mapped_column(JSON, nullable=False)            # list of explanation strings
    event_ids: Mapped[list] = mapped_column(JSON, nullable=True)             # contributing MarketEvent ids
    entry_price: Mapped[float] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float] = mapped_column(Float, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_trading_signals_asset", "asset"),
        Index("ix_trading_signals_generated_at", "generated_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "asset":        self.asset,
            "signal":       self.signal,
            "confidence":   self.confidence,
            "time_horizon": self.time_horizon,
            "risk_level":   self.risk_level,
            "reasoning":    self.reasoning,
            "event_ids":    self.event_ids or [],
            "entry_price":  self.entry_price,
            "stop_loss":    self.stop_loss,
            "take_profit":  self.take_profit,
            "generated_at": self.generated_at.isoformat(),
            "expires_at":   self.expires_at.isoformat() if self.expires_at else None,
        }
