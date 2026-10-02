from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.database.base import Base


class Merchant(Base):
    """A business identity, shared across every module.

    This is deliberately the one place a business is identified. Competitors
    discovers them; Products, Trends and Market Pulse will attach their own
    observations to the same rows rather than re-identifying the same companies
    under different names. Nothing here is specific to a module, an industry or
    a country.

    Point-in-time facts (what a search said today, where it said it, how
    confident we were) belong on an observation row, not here -- see
    ``CompetitorObservation``. This table holds only what identifies the
    business and the best classification we currently have for it.
    """

    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(String, unique=True, index=True, nullable=True) # e.g. place_id or custom ID
    name = Column(String, index=True)
    normalized_name = Column(String, index=True)
    website = Column(String, nullable=True)
    normalized_domain = Column(String, index=True, nullable=True)
    place_id = Column(String, nullable=True)
    data_id = Column(String, nullable=True)
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable=True)
    source = Column(String, default="google_maps")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # What kind of web entity this is, from ResultClassifier. Only a "business"
    # may be presented as a competitor; a directory or article that mentions
    # many businesses is not one of them.
    entity_type = Column(String, default="unknown", index=True)

    # Identity confidence, never a judgement about the business itself:
    # verified | discovered | uncertain | rejected.
    status = Column(String, default="discovered", index=True)

    # Set on every rediscovery, so staleness is visible without reading the
    # observation history.
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
