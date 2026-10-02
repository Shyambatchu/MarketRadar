from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.serpapi_schemas import LocationResolutionSchema


class StageStatus(BaseModel):
    """Explicit per-stage outcome.

    Same contract as the Price Intelligence funnel: a failed provider call is
    never reported as "0 competitors found". ok | degraded | error | skipped.
    """
    stage: str
    status: str
    detail: Optional[str] = None
    results_count: Optional[int] = None


class CompetitorEvidence(BaseModel):
    """One recorded reason to believe a business competes here.

    Every field is something a provider returned or the matcher decided.
    Nothing is inferred, and anything unknown stays null.
    """
    source_type: str                  # local | organic | merchant_website
    source_url: Optional[str] = None
    source_domain: Optional[str] = None
    discovery_method: str             # google_maps_local | google_organic
    entity_type: str                  # business | directory | social | ...
    observed_at: datetime

    match_method: str = "new"
    match_confidence: str = "unmatched"
    status: str = "discovered"
    reason: Optional[str] = None

    position: Optional[int] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    title: Optional[str] = None
    snippet: Optional[str] = None


class Competitor(BaseModel):
    """A business identified as competing in the searched market and place."""
    id: Optional[int] = None
    name: str
    normalized_name: Optional[str] = None
    domain: Optional[str] = None
    website: Optional[str] = None

    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_id: Optional[str] = None

    # discovered | verified | uncertain | rejected
    status: str = "discovered"
    # business | directory | social | article | marketplace | unknown
    entity_type: str = "unknown"
    match_method: str = "new"
    match_confidence: str = "unmatched"
    status_reason: Optional[str] = None

    # Best signals observed, as reported by the provider.
    rating: Optional[float] = None
    reviews: Optional[int] = None
    best_position: Optional[int] = None

    # ---- discovery context ---------------------------------------------
    # Which searches found this business. A saved list spans many markets and
    # places, so a row is meaningless without the context that produced it.
    # Every market/location it has been seen in is kept, because the point of
    # the observation history is that it is not overwritten.
    market: Optional[str] = None
    location_requested: Optional[str] = None
    location_resolved: Optional[str] = None
    markets: List[str] = []
    locations: List[str] = []

    # local | organic, from the observations actually recorded. Never a
    # persistence state -- "saved" is not a discovery source.
    discovery_sources: List[str] = []
    discovery_methods: List[str] = []

    # True when a provider gave us a real position for this business: an
    # address or coordinates. Organic evidence carries none, which is why such
    # a business stays "discovered" and its location reads as unverified.
    has_location_evidence: bool = False

    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    evidence_count: int = 0
    evidence: List[CompetitorEvidence] = []


class RejectedResult(BaseModel):
    """A result that was not a business, retained so nothing vanishes silently."""
    title: Optional[str] = None
    url: Optional[str] = None
    domain: Optional[str] = None
    entity_type: str
    reason: str
    source_type: str


class CompetitorSearchResponse(BaseModel):
    # ---- what was asked -------------------------------------------------
    market: str
    query: str
    effective_query: str
    location_requested: Optional[str] = None
    location_resolved: Optional[str] = None
    location_resolution: Optional[LocationResolutionSchema] = None

    # ---- provider outcome ----------------------------------------------
    # success | no_results. A provider failure is a non-200 response, so it can
    # never arrive here looking like an empty result set.
    provider_status: str = "success"
    cache_hit: bool = False
    stages: List[StageStatus] = []

    # ---- funnel counters, each meaning one distinct thing ---------------
    local_results_found: int = 0
    organic_results_found: int = 0
    business_candidates: int = 0
    rejected_non_business: int = 0
    competitors_discovered: int = 0
    competitors_verified: int = 0
    competitors_uncertain: int = 0
    duplicates_merged: int = 0
    new_competitors: int = 0

    competitors: List[Competitor] = []
    rejected_results: List[RejectedResult] = []


class CompetitorListResponse(BaseModel):
    """Saved competitors, reusable by later modules."""
    total: int
    competitors: List[Competitor]
