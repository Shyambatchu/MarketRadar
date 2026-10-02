from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.trend import TrendSeriesModel


class MarketOption(BaseModel):
    """A market and location actually present in the observation history.

    Offered as a choice so the user selects something that exists, rather than
    typing a market this installation has never observed. Categories are never
    invented.
    """
    market: Optional[str] = None
    location: Optional[str] = None
    competitor_observations: int = 0
    product_observations: int = 0
    merchants: int = 0
    first_observed_at: Optional[datetime] = None
    last_observed_at: Optional[datetime] = None


class MarketContext(BaseModel):
    """What the snapshot covers. Present on every section so two sections can
    never be read as describing the same thing when they do not."""
    market: Optional[str] = None
    location: Optional[str] = None
    first_observed_at: Optional[datetime] = None
    last_observed_at: Optional[datetime] = None
    observation_span_hours: Optional[float] = None
    distinct_searches: int = 0

    merchants: int = 0
    competitor_observations: int = 0
    product_observations: int = 0


class CompetitorEntry(BaseModel):
    """A business observed in this market and location."""
    merchant_id: Optional[int] = None
    name: str
    domain: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None

    # verified | discovered | uncertain | rejected -- evidence strength, never
    # a judgement about the business.
    status: str = "discovered"
    entity_type: str = "unknown"
    discovery_sources: List[str] = []
    discovery_methods: List[str] = []

    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    observation_count: int = 0
    distinct_searches: int = 0

    present_in_latest: bool = True
    # Stated in full so absence is never read as closure.
    presence_note: Optional[str] = None
    has_location_evidence: bool = False


class ProductEntry(BaseModel):
    """A product observed at a merchant in this context."""
    observation_id: int
    merchant_id: Optional[int] = None
    merchant: Optional[str] = None
    merchant_domain: Optional[str] = None

    product_query: str
    product_name: Optional[str] = None
    observed_size: Optional[str] = None
    size_confirmed: bool = False

    # found | not_found | unknown
    product_status: str = "unknown"
    # verified | unavailable | unknown
    price_status: str = "unknown"
    verification_reason: Optional[str] = None

    evidence_scope: str = "catalog"
    inventory_confirmed: bool = False
    source_url: Optional[str] = None
    source_domain: Optional[str] = None
    page_type: Optional[str] = None
    observed_at: datetime


class PriceEntry(BaseModel):
    """A verified price observation. Unverified prices never appear here."""
    observation_id: int
    merchant: Optional[str] = None
    merchant_id: Optional[int] = None
    product_name: Optional[str] = None
    product_query: str
    observed_size: Optional[str] = None
    price: float
    currency: Optional[str] = None
    source_url: Optional[str] = None
    source_domain: Optional[str] = None
    evidence_scope: str = "catalog"
    inventory_confirmed: bool = False
    observed_at: datetime


class PriceStatistics(BaseModel):
    """Only populated when enough *distinct* measurements exist.

    A single price read repeatedly is one measurement. Averaging it would
    present a sample size of one as if it were a market rate.
    """
    distinct_measurements: int = 0
    sufficient: bool = False
    lowest: Optional[float] = None
    highest: Optional[float] = None
    average: Optional[float] = None
    currency: Optional[str] = None
    detail: Optional[str] = None


class VisibilityEntry(BaseModel):
    """Position, rating and review count as the provider reported them."""
    merchant_id: Optional[int] = None
    merchant: str
    domain: Optional[str] = None
    best_position: Optional[int] = None
    latest_position: Optional[int] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    observed_at: Optional[datetime] = None
    observation_count: int = 0


class DataQuality(BaseModel):
    """Counts by evidence state, so nothing is silently read as negative."""
    competitors_verified: int = 0
    competitors_discovered: int = 0
    competitors_uncertain: int = 0

    products_found: int = 0
    products_not_found: int = 0
    products_unknown: int = 0

    prices_verified: int = 0
    prices_unavailable: int = 0
    prices_unknown: int = 0

    trend_series: int = 0
    trend_series_with_direction: int = 0
    trend_series_insufficient_history: int = 0

    notes: List[str] = []


class MarketPulseResponse(BaseModel):
    """A factual snapshot of one market and location.

    Read-only and derived: every figure comes from observations Competitors and
    Products already stored. No provider request is made, no SerpApi credit is
    spent, and nothing is written back.

    The response states what was observed and how strongly it is evidenced. It
    draws no conclusions: no market is "growing", no competitor is "winning",
    and a business absent from the latest search has not "disappeared".
    """
    generated_at: datetime
    persisted: bool = False

    context: MarketContext
    competitors: List[CompetitorEntry] = []
    products: List[ProductEntry] = []
    prices: List[PriceEntry] = []
    price_statistics: PriceStatistics = PriceStatistics()
    visibility: List[VisibilityEntry] = []
    trends: List[TrendSeriesModel] = []
    data_quality: DataQuality = DataQuality()

    has_data: bool = False
    detail: Optional[str] = None


class MarketPulseOptionsResponse(BaseModel):
    """The markets and locations this installation has actually observed."""
    generated_at: datetime
    total: int = 0
    options: List[MarketOption] = []
    detail: Optional[str] = None
