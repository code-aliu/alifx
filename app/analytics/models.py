from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, SmallInteger
from app.database import Base


class FeedbackEvent(Base):
    """
    User feedback on a specific AI response or signal.
    user_id is optional — unlinked if the user isn't authenticated.
    context_key is a short hash of the question or signal_id so we can
    correlate feedback to specific content without storing the full text.
    """
    __tablename__ = "feedback_events"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, nullable=True, index=True)       # null = anonymous
    feature     = Column(String(50), nullable=False, index=True)   # "copilot" | "guidance" | "signal"
    context_key = Column(String(100), nullable=True)               # sha1[:10] of question or str(signal_id)
    intent      = Column(String(50), nullable=True)                # copilot intent if applicable
    rating      = Column(SmallInteger, nullable=False)             # 1 = thumbs up, -1 = thumbs down
    clarity     = Column(SmallInteger, nullable=True)              # 1–3 stars (optional follow-up)
    notes       = Column(String(200), nullable=True)               # optional short text
    created_at  = Column(DateTime, default=datetime.utcnow, index=True)


class AnalyticsEvent(Base):
    """
    Lightweight anonymized interaction events for product intelligence.
    Never stores PII — only event type, optional integer user_id, and JSON metadata.
    """
    __tablename__ = "analytics_events"

    id         = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # "page_view" | "signal_view" | "event_click"
    user_id    = Column(Integer, nullable=True, index=True)
    event_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
