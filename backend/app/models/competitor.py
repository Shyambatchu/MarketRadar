from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.base import Base


class CompetitorObservation(Base):
    """One piece of evidence that a business competes in a market and place.

    Separate from ``Merchant`` because a business is one thing and the evidence
    about it is many: the same company is rediscovered by different queries,
    from different sources, in different markets, over time. Collapsing the two
    would mean each new search overwrote the last one's evidence and no history
    would survive.

    Evidence is only ever recorded, never inferred. Every field here is either
    something a provider actually returned or something the matcher actually
    decided; anything unknown stays null rather than being filled in.

    The same shape is intended for later modules: Products, Trends and Market
    Pulse attach their own observation tables to the same ``merchants`` rows, so
    a business identified once is reused rather than re-identified.
    """

    __tablename__ = "competitor_observations"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), index=True)

    # ---- what was asked -------------------------------------------------
    # Kept so an observation can never be mistaken for evidence about a
    # different market or place than the one that produced it.
    market = Column(String, index=True)
    query = Column(String)
    location_requested = Column(String, nullable=True)
    location_resolved = Column(String, nullable=True, index=True)

    # ---- where the evidence came from -----------------------------------
    # local | organic | merchant_website
    source_type = Column(String, index=True)
    source_url = Column(String, nullable=True)
    source_domain = Column(String, nullable=True)
    # google_maps_local | google_organic
    discovery_method = Column(String)
    # business | directory | social | article | marketplace | unknown
    entity_type = Column(String, index=True)

    # ---- how identity was decided ---------------------------------------
    # exact_domain | domain_alias | exact_name | name_and_address |
    # fuzzy_name | place_id | new
    match_method = Column(String, default="new")
    match_confidence = Column(String, default="unmatched")
    # Status this single observation supports, which is not necessarily the
    # merchant's overall status.
    status = Column(String, default="discovered", index=True)
    # Why this observation did not reach "verified", when it did not.
    reason = Column(String, nullable=True)

    # ---- observed signals, as reported --------------------------------
    position = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)
    reviews = Column(Integer, nullable=True)
    title = Column(String, nullable=True)
    snippet = Column(Text, nullable=True)

    observed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    merchant = relationship("Merchant", backref="competitor_observations")
