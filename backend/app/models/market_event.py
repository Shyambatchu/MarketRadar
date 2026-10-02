from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database.base import Base

class MarketEvent(Base):
    __tablename__ = "market_events"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, index=True)
    event_type = Column(String, index=True)
    title = Column(String)
    description = Column(String)
    severity = Column(String)
    evidence = Column(String)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
