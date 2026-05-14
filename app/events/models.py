from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, Float, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class MarketEvent(Base):
    __tablename__ = "market_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    news_article_id: Mapped[int] = mapped_column(Integer, ForeignKey("news_articles.id"), nullable=True)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)       # macroeconomic | geopolitical | earnings | crypto | sector
    sentiment: Mapped[str] = mapped_column(String(20), nullable=False)       # risk_on | risk_off | neutral
    importance: Mapped[str] = mapped_column(String(10), nullable=False)      # high | medium | low
    affected_assets: Mapped[list] = mapped_column(JSON, nullable=False)      # ["BTC", "USD", "NASDAQ"]
    keywords: Mapped[list] = mapped_column(JSON, nullable=True)              # matched rule keywords
    llm_enriched: Mapped[bool] = mapped_column(String(5), default=False)
    extraction_method: Mapped[str] = mapped_column(String(10), default="rule")  # rule | llm
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_market_events_category", "category"),
        Index("ix_market_events_extracted_at", "extracted_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "headline": self.headline,
            "category": self.category,
            "sentiment": self.sentiment,
            "importance": self.importance,
            "affected_assets": self.affected_assets,
            "keywords": self.keywords,
            "extraction_method": self.extraction_method,
            "extracted_at": self.extracted_at.isoformat(),
        }
