from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class StageStatus(BaseModel):
    """Explicit per-stage outcome.

    A failed provider call must never be reported as "0 results found"
    (spec 50 / 76): ok | degraded | error | skipped.
    """
    stage: str
    status: str
    detail: Optional[str] = None
    results_count: Optional[int] = None


class LocalPriceObservation(BaseModel):
    merchant: str
    merchant_id: Optional[str] = None
    merchant_name: Optional[str] = None
    merchant_domain: Optional[str] = None
    product_name: str
    normalized_product_name: Optional[str] = None
    brand: Optional[str] = None
    variant: Optional[str] = None
    size: Optional[str] = None
    price: Optional[float] = None
    currency: str = "USD"
    availability: Optional[str] = None
    source_type: str
    source_domain: Optional[str] = None
    source_url: Optional[str] = None
    discovery_method: Optional[str] = None
    observed_at: datetime
    snippet_text: Optional[str] = None
    verification_reason: Optional[str] = None
    verification_status: str = "not_verified"

    # What this evidence actually covers.
    # catalog            -> the merchant's catalogue lists the product
    # store_inventory    -> this physical store stocks it
    # marketplace_listing-> a shopping listing attributed to this merchant
    evidence_scope: str = "catalog"
    inventory_confirmed: bool = False
    page_type: Optional[str] = None

    distance: Optional[float] = None
    difference: Optional[float] = None
    is_reference_store: bool = False
    match_type: str = "exact"
    match_method: str = "unmatched"
    match_confidence: str = "unmatched"
    merchant_match_status: str = "unmatched"
    source: str


class NearbyMerchantStatus(BaseModel):
    merchant: str
    address: Optional[str] = None
    distance: float
    website: Optional[str] = None
    place_id: Optional[str] = None

    product_status: str
    price_status: str

    product_name: Optional[str] = None
    product_size: Optional[str] = None
    product_variant: Optional[str] = None

    verification_reason: Optional[str] = None
    price: Optional[float] = None
    price_source: Optional[str] = None
    source_domain: Optional[str] = None
    source_url: Optional[str] = None

    evidence_scope: Optional[str] = None
    inventory_confirmed: bool = False
    merchant_match_status: str = "unmatched"


class ApiUsageReport(BaseModel):
    external_calls_used: int
    merchant_discovery_used: int
    website_provider_used: int
    shopping_used: int
    cache_hits: int


class SearchCenter(BaseModel):
    name: str
    latitude: float
    longitude: float
    resolution_method: Optional[str] = None


class LocalPriceSearchResponse(BaseModel):
    searched_product: str
    searched_area: str
    searched_radius: int
    search_center: Optional[SearchCenter] = None
    product_name: str
    area: str
    radius: int

    lowest_price: Optional[float] = None
    average_price: Optional[float] = None
    highest_price: Optional[float] = None
    # Statistics cover verified observations only (spec 27). When the request
    # named no size, several sizes may qualify -- surfaced, never hidden.
    verified_sizes: List[str] = []
    mixed_size_statistics: bool = False

    nearby_merchants_discovered: int = 0
    product_evidence_found: int = 0
    product_evidence_not_found: int = 0
    product_evidence_unknown: int = 0
    price_unavailable_count: int = 0

    # --- funnel counters -------------------------------------------------
    # website_results_found: indexed rows confirmed to be served by the
    #   merchant's own domain (off-domain fallback rows are excluded).
    website_results_found: int = 0
    website_off_domain_rejected: int = 0
    website_listing_pages: int = 0
    shopping_results_found: int = 0
    # candidate_product_matches / exact_product_matches / merchant_matches are
    # cross-source totals (spec 29). Per-source counters below keep the
    # invariant checkable.
    candidate_product_matches: int = 0
    exact_product_matches: int = 0
    merchant_matches: int = 0
    website_candidates: int = 0
    website_exact_matches: int = 0
    website_merchant_matches: int = 0
    shopping_candidates: int = 0
    shopping_exact_matches: int = 0
    shopping_merchant_matches: int = 0
    merchant_uncertain_count: int = 0
    verified_local_prices: int = 0

    stages: List[StageStatus] = []

    reference_price: Optional[float] = None
    reference_store: Optional[NearbyMerchantStatus] = None

    nearby_merchants: List[NearbyMerchantStatus]
    verified_price_observations: List[LocalPriceObservation]
    api_usage: Optional[ApiUsageReport] = None
