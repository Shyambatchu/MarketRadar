from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TrendPoint(BaseModel):
    """One distinct measurement.

    ``observation_count`` is how many stored observations collapsed into this
    point. Re-running a search inside the response cache window returns
    byte-identical data, so several observations can describe a single
    measurement; counting them as separate samples would invent history.
    """
    value: Optional[float] = None
    label: Optional[str] = None
    observed_at: datetime
    observation_count: int = 1


class TrendSeries:
    """Declared below as a Pydantic model; see ``TrendSeriesModel``."""


class TrendSeriesModel(BaseModel):
    """Movement of one metric for one subject, within one comparable context.

    Series are never merged across contexts. A merchant's position in one
    market and location is not comparable with its position in another, and a
    product's price at one merchant is not comparable with another's.

    ``status``:

    * ``trend``                -- two or more distinct measurements
    * ``insufficient_history`` -- fewer than two; no direction is claimed
    * ``no_data``              -- nothing recorded for this metric

    A single measurement observed repeatedly is ``insufficient_history``, never
    "stable": we have not watched it hold, we have watched one reading.
    """
    subject: str
    subject_id: Optional[int] = None
    metric: str                       # price | position | rating | reviews | availability
    context: Optional[str] = None     # market / location / merchant this belongs to

    status: str = "no_data"
    direction: Optional[str] = None   # up | down | flat | unknown
    change_absolute: Optional[float] = None
    change_percent: Optional[float] = None

    first_value: Optional[float] = None
    last_value: Optional[float] = None
    first_observed_at: Optional[datetime] = None
    last_observed_at: Optional[datetime] = None
    observation_span_hours: Optional[float] = None

    raw_observations: int = 0
    distinct_points: int = 0
    points: List[TrendPoint] = []

    # Why no direction could be claimed, when none was.
    detail: Optional[str] = None


class MerchantPresence(BaseModel):
    """When a business was first and last seen in a market and location."""
    merchant: str
    merchant_id: Optional[int] = None
    domain: Optional[str] = None
    market: Optional[str] = None
    location: Optional[str] = None
    status: str                       # merchant identity status, carried through
    first_seen_at: datetime
    last_seen_at: datetime
    observation_count: int = 1
    distinct_searches: int = 1
    # present_in_latest tells you whether the most recent search of this
    # context still found it. False is not proof it has gone: a search may
    # simply have returned a different slice.
    present_in_latest: bool = True


class ContextSummary(BaseModel):
    """One comparable context and how much history it holds."""
    market: Optional[str] = None
    location: Optional[str] = None
    source: str                       # competitors | products
    merchants: int = 0
    observations: int = 0
    distinct_searches: int = 0
    first_observed_at: Optional[datetime] = None
    last_observed_at: Optional[datetime] = None
    span_hours: Optional[float] = None
    analyzable: bool = False
    detail: Optional[str] = None


class TrendSummaryResponse(BaseModel):
    """What history exists, and what can honestly be derived from it.

    Derived entirely from observations already stored by Market Research,
    Competitors and Products. No provider request is made and no SerpApi credit
    is spent.
    """
    generated_at: datetime
    # Nothing here is written back: trends are derived from the observation
    # history and never become the source of truth.
    persisted: bool = False

    competitor_observations: int = 0
    product_observations: int = 0
    merchants_tracked: int = 0
    verified_price_observations: int = 0

    contexts: List[ContextSummary] = []
    analyzable_contexts: int = 0
    # Set when history exists but nothing can yet be compared.
    insufficient_history: bool = True
    detail: Optional[str] = None


class TrendListResponse(BaseModel):
    generated_at: datetime
    persisted: bool = False
    total: int = 0
    analyzable: int = 0
    insufficient_history: int = 0
    series: List[TrendSeriesModel] = []
    detail: Optional[str] = None


class MerchantPresenceResponse(BaseModel):
    generated_at: datetime
    persisted: bool = False
    total: int = 0
    contexts: List[ContextSummary] = []
    merchants: List[MerchantPresence] = []
    detail: Optional[str] = None
