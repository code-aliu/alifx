from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=True, unique=True)  # dedup key
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)  # newsapi | rss
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_news_articles_published", "published_at"),
        Index("ix_news_articles_processed", "processed"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "source_name": self.source_name,
            "provider": self.provider,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "fetched_at": self.fetched_at.isoformat(),
        }
