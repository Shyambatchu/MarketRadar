from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func

from app.database.base import Base


class Opportunity(Base):
    """An evidence-backed lead worth investigating, with an explainable score.

    The score ranks leads against each other. It is not a probability of
    commercial success: it has never been validated against outcomes, and the
    UI never presents it as one.

    ``fingerprint`` identifies the same lead across refreshes, so its score and
    evidence update in place while the user's review status is kept.
    """

    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True)
    fingerprint = Column(String, unique=True, index=True)
    title = Column(String)
    category = Column(String, index=True)
    market = Column(String, nullable=True, index=True)
    location = Column(String, nullable=True, index=True)
    product = Column(String, nullable=True)
    merchant_id = Column(Integer, nullable=True)
    score = Column(Float, index=True)
    breakdown = Column(Text)         # JSON: inputs, weights, contributions, missing
    evidence = Column(Text)          # JSON: {"record_ids": [...], "source_urls": [...]}
    confidence = Column(String)      # high | medium | low
    relevance_note = Column(Text, nullable=True)
    suggested_action = Column(Text, nullable=True)
    # new | saved | reviewed | dismissed
    status = Column(String, default="new", index=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
    evidence_observed_at = Column(DateTime(timezone=True), nullable=True)
