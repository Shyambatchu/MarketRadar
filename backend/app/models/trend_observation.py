from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.sql import func

from app.database.base import Base


class TrendObservation(Base):
    """One Google Trends interest point for one term.

    Google Trends interest is *relative*: 0-100 scaled to the peak within one
    request (its terms, geography and time range). A value is therefore only
    comparable with values from the same request, which ``request_key``
    identifies. It is never search volume, market share or sales.
    """

    __tablename__ = "trend_observations"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, index=True)
    keyword = Column(String, index=True)
    region = Column(String)                 # the geo requested ("" = worldwide)
    interest_value = Column(Float)
    period = Column(String)                 # the provider's display label for the point
    source = Column(String)                 # serpapi_google_trends
    observed_at = Column(DateTime(timezone=True), server_default=func.now())  # collected

    # ---- added for the google_trends integration -----------------------
    point_at = Column(DateTime(timezone=True), nullable=True, index=True)
    timeframe = Column(String, nullable=True)       # e.g. "today 12-m"
    request_key = Column(String, nullable=True, index=True)
    data_type = Column(String, nullable=True)       # TIMESERIES
    partial = Column(Boolean, nullable=True)        # the provider flagged the point incomplete
