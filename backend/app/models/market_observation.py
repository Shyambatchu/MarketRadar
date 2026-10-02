from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.database.base import Base

class MarketObservation(Base):
    __tablename__ = "market_observations"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, index=True, nullable=True)
    product_id = Column(String, index=True, nullable=True) # Changed to String to match SerpApi
    product_name = Column(String, index=True)
    merchant_name = Column(String, index=True)
    query = Column(String, index=True)
    price = Column(Float, nullable=True)
    old_price = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    availability_signal = Column(String, nullable=True)
    product_link = Column(String, nullable=True)
    snippet = Column(String, nullable=True)
    position = Column(Integer, nullable=True)
    source = Column(String)
    location = Column(String, nullable=True)
    observed_at = Column(DateTime(timezone=True), server_default=func.now())
