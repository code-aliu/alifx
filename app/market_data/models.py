from datetime import datetime
from sqlalchemy import String, Float, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PriceBar(Base):
    __tablename__ = "price_bars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(10), nullable=False)  # crypto | stock | forex
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)  # binance | yahoo | frankfurter
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_price_bars_symbol_fetched", "symbol", "fetched_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "source": self.source,
            "fetched_at": self.fetched_at.isoformat(),
        }
