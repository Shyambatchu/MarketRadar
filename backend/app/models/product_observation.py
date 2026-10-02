from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.base import Base


class ProductObservation(Base):
    """One piece of evidence that a merchant offers a product.

    The same shape as ``CompetitorObservation``, attached to the same
    ``merchants`` rows: a business is identified once and every module hangs
    its own observations off it. Competitors records *that a business exists*;
    this records *what it offers*.

    Evidence is recorded, never inferred:

    * ``product_status`` is what the evidence supports, so an absent match is
      ``unknown`` rather than ``not_found`` -- only a specific contradiction
      (a different size, variant or model) justifies ``not_found``.
    * ``price_status`` is independent of ``product_status``. A product can be
      found on a merchant's catalogue with no usable price, and that is not a
      reason to doubt the product.
    * ``evidence_scope`` says what the evidence actually covers. A catalogue
      page proves the merchant lists the product; it never proves a physical
      store holds stock, so ``inventory_confirmed`` stays false unless
      something genuinely establishes inventory.

    Observations are append-only. Re-running a search adds history rather than
    overwriting it, which is what later modules will read for change over time.
    """

    __tablename__ = "product_observations"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id"), index=True)

    # ---- what was asked -------------------------------------------------
    product_query = Column(String, index=True)
    normalized_query = Column(String, index=True)
    market = Column(String, nullable=True, index=True)
    location_requested = Column(String, nullable=True)
    location_resolved = Column(String, nullable=True, index=True)

    # ---- what was observed ---------------------------------------------
    product_name = Column(String, nullable=True)
    normalized_product_name = Column(String, nullable=True)
    observed_size = Column(String, nullable=True)
    # A requested size that was never observed leaves identity intact but must
    # block price verification.
    size_confirmed = Column(Boolean, default=False)

    # found | not_found | unknown
    product_status = Column(String, default="unknown", index=True)
    # verified | unavailable | unknown
    price_status = Column(String, default="unknown", index=True)
    verification_reason = Column(String, nullable=True)

    price = Column(Float, nullable=True)
    currency = Column(String, nullable=True)

    # ---- where the evidence came from -----------------------------------
    source_type = Column(String, nullable=True)     # merchant_website_indexed
    source_url = Column(String, nullable=True)
    source_domain = Column(String, nullable=True)
    discovery_method = Column(String, nullable=True)  # indexed_search
    page_type = Column(String, nullable=True)         # product | listing | unknown

    # catalog | store_inventory | marketplace_listing
    evidence_scope = Column(String, default="catalog")
    inventory_confirmed = Column(Boolean, default=False)

    # ---- how identity was decided ---------------------------------------
    match_method = Column(String, default="product_identity")
    match_reason = Column(String, nullable=True)
    merchant_match_status = Column(String, default="matched")

    snippet = Column(Text, nullable=True)
    observed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    merchant = relationship("Merchant", backref="product_observations")
