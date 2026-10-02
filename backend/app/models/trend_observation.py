from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.database.base import Base

class TrendObservation(Base):
    __tablename__ = "trend_observations"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, index=True)
    keyword = Column(String, index=True)
    region = Column(String)
    interest_value = Column(Float)
    period = Column(String)
    source = Column(String)
    observed_at = Column(DateTime(timezone=True), server_default=func.now())
