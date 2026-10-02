from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.serpapi_schemas import LocationResolutionSchema


class StageStatus(BaseModel):
    """Explicit per-stage outcome.

    Same contract as the Price Intelligence and Competitors funnels: a failed
    provider call is never reported as "0 products found".
    ok | degraded | error | skipped.
    """
    stage: str
    status: str
    detail: Optional[str] = None
    results_count: Optional[int] = None


class ProductEvidence(BaseModel):
    """One recorded observation of a product at a merchant.

    ``product_status`` and ``price_status`` are independent: a product can be
    found with no usable price, and that says nothing about whether the product
    exists.
    """
    merchant: str
    merchant_id: Optional[int] = None
    merchant_domain: Optional[str] = None
    merchant_match_status: str = "matched"

    product_name: Optional[str] = None
    normalized_product_name: Optional[str] = None
    observed_size: Optional[str] = None
    size_confirmed: bool = False

    # found | not_found | unknown
    product_status: str = "unknown"
    # verified | unavailable | unknown
    price_status: str = "unknown"
    verification_reason: Optional[str] = None

    price: Optional[float] = None
    currency: Optional[str] = None

    source_type: Optional[str] = None
    source_url: Optional[str] = None
    source_domain: Optional[str] = None
    discovery_method: Optional[str] = None
    page_type: Optional[str] = None

    # catalog | store_inventory | marketplace_listing
    evidence_scope: str = "catalog"
    # A catalogue listing never proves a physical store holds stock.
    inventory_confirmed: bool = False

    match_method: str = "product_identity"
    match_reason: Optional[str] = None

    snippet: Optional[str] = None
    observed_at: datetime


class RejectedProductResult(BaseModel):
    """Evidence that could not establish product identity, kept visible."""
    merchant: str
    title: Optional[str] = None
    url: Optional[str] = None
    page_type: Optional[str] = None
    reason: str
    detail: Optional[str] = None


class ProductSearchResponse(BaseModel):
    # ---- what was asked -------------------------------------------------
    product_query: str
    market: Optional[str] = None
    location_requested: Optional[str] = None
    location_resolved: Optional[str] = None
    location_resolution: Optional[LocationResolutionSchema] = None

    # ---- provider outcome ----------------------------------------------
    # success | no_results. A provider failure is a non-200 response.
    provider_status: str = "success"
    cache_hit: bool = False
    stages: List[StageStatus] = []

    # ---- funnel counters, each meaning one distinct thing ---------------
    merchants_considered: int = 0
    merchants_searched: int = 0
    merchants_without_domain: int = 0
    merchant_provider_errors: int = 0

    website_rows_examined: int = 0
    off_domain_rejected: int = 0
    listing_pages_rejected: int = 0
    candidate_matches: int = 0

    products_found: int = 0
    products_not_found: int = 0
    products_unknown: int = 0
    prices_verified: int = 0
    prices_unavailable: int = 0

    evidence: List[ProductEvidence] = []
    rejected_results: List[RejectedProductResult] = []


class ProductObservationRecord(BaseModel):
    """A saved observation, as stored."""
    id: int
    merchant_id: Optional[int] = None
    merchant_name: Optional[str] = None
    merchant_domain: Optional[str] = None

    product_query: str
    market: Optional[str] = None
    location_resolved: Optional[str] = None

    product_name: Optional[str] = None
    observed_size: Optional[str] = None
    size_confirmed: bool = False
    product_status: str
    price_status: str
    verification_reason: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None

    source_type: Optional[str] = None
    source_url: Optional[str] = None
    source_domain: Optional[str] = None
    discovery_method: Optional[str] = None
    page_type: Optional[str] = None
    evidence_scope: str = "catalog"
    inventory_confirmed: bool = False
    match_method: str = "product_identity"
    match_reason: Optional[str] = None
    merchant_match_status: str = "matched"
    snippet: Optional[str] = None
    observed_at: datetime


class ProductObservationListResponse(BaseModel):
    """Saved product observations, reusable by later modules."""
    total: int
    observations: List[ProductObservationRecord]
