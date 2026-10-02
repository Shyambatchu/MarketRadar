from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime

class SerpSearchResultSchema(BaseModel):
    position: Optional[int]
    title: Optional[str]
    link: Optional[str]
    displayed_link: Optional[str]
    snippet: Optional[str]
    domain: Optional[str]
    result_type: str = "organic"

class SerpLocalResultSchema(BaseModel):
    position: Optional[int]
    title: Optional[str]
    type: Optional[str]
    rating: Optional[float]
    reviews: Optional[int]
    address: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    place_id: Optional[str]
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class LocationResolutionSchema(BaseModel):
    """How a user-entered location was mapped to a provider-supported one."""
    requested: str
    canonical_name: str
    country_code: Optional[str] = None
    target_type: Optional[str] = None
    matched_candidate: Optional[str] = None
    ambiguous: bool = False
    alternatives: List[str] = []


class SerpSearchResponseSchema(BaseModel):
    query: str
    # location is what the user asked for; resolved_location is what the
    # provider was actually given.
    location: Optional[str]
    resolved_location: Optional[str] = None
    location_resolution: Optional[LocationResolutionSchema] = None
    engine: str
    searched_at: datetime
    cache_hit: bool
    # success | no_results. A failed provider request never returns 200, so it
    # can never arrive here disguised as an empty result set.
    provider_status: str = "success"
    results: List[SerpSearchResultSchema]
    local_results: Optional[List[SerpLocalResultSchema]] = None

class BatchSearchRequest(BaseModel):
    queries: List[str]
    location: Optional[str] = None
    engine: str = "google"

class BatchSearchResponse(BaseModel):
    total_requested: int
    successful: int
    failed: int
    results: List[SerpSearchResponseSchema]

class UsageStatsResponse(BaseModel):
    """Local request history plus SerpApi's authoritative account quota.

    The two are kept apart on purpose. ``local_*`` is what this application
    observed itself doing and is NOT a quota. Everything else comes verbatim
    from SerpApi's account endpoint, which is the only authority on what
    remains -- and is ``None`` when it cannot be read, so the UI renders
    "Unavailable" instead of a blank or an invented number. No daily limit or
    daily allowance exists anywhere in this response (spec 34).
    """
    local_requests_recorded: int
    local_credits_used: int
    local_failed_requests: int
    local_cache_hits: int

    account_quota_available: bool = False
    account_quota_detail: Optional[str] = None

    plan_name: Optional[str] = None
    account_status: Optional[str] = None
    plan_renewal_date: Optional[str] = None
    searches_per_month: Optional[int] = None
    plan_searches_left: Optional[int] = None
    extra_credits: Optional[int] = None
    total_searches_left: Optional[int] = None
    this_month_usage: Optional[int] = None
    this_hour_searches: Optional[int] = None
    account_rate_limit_per_hour: Optional[int] = None

class RecentSearchSchema(BaseModel):
    id: int
    query: str
    location: Optional[str]
    searched_at: datetime
    organic_count: int
    local_count: int
