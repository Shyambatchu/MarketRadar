from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class PriceAlert(BaseModel):
    """One detected change, with the evidence that supports it.

    ``type``:
      price_increase | price_decrease -- two distinct verified readings at one
        merchant in one context, differing by at least the threshold;
      new_offer -- a merchant first priced in the latest run of a context that
        had earlier runs;
      not_observed_in_latest -- priced in an earlier run, absent from the
        latest. Absence from one search is not proof the offer ended;
      outlier -- a latest price far from the context's median (MAD test);
      price_dispersion -- latest prices across merchants spread wider than
        the threshold;
      conflicting_prices -- one merchant, one run, different verified prices.
    """
    type: str
    severity: str  # info | warning
    confidence: str  # high | medium | low
    product: str
    merchant: Optional[str] = None
    merchant_id: Optional[int] = None
    market: Optional[str] = None
    location: Optional[str] = None
    currency: Optional[str] = None
    previous_price: Optional[float] = None
    current_price: Optional[float] = None
    change_absolute: Optional[float] = None
    change_percent: Optional[float] = None
    previous_observed_at: Optional[datetime] = None
    observed_at: Optional[datetime] = None
    explanation: str
    record_ids: List[int] = []
    source_urls: List[str] = []


class PriceAlertThresholds(BaseModel):
    min_change_percent: float
    outlier_mad_k: float
    dispersion_min_percent: float
    min_merchants_for_outliers: int


class PriceAlertResponse(BaseModel):
    generated_at: datetime
    thresholds: PriceAlertThresholds
    contexts_examined: int = 0
    verified_observations: int = 0
    total: int = 0
    alerts: List[PriceAlert] = []
    detail: Optional[str] = None
