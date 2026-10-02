from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class PriceObservation(BaseModel):
    product_name: str
    product_id: Optional[str] = None
    merchant: Optional[str] = None
    price: Optional[float] = None
    old_price: Optional[float] = None
    currency: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    delivery: Optional[str] = None
    product_link: Optional[str] = None
    snippet: Optional[str] = None
    position: Optional[int] = None
    source: str
    query: str
    location: Optional[str] = None
    observed_at: datetime

class PriceSearchResponse(BaseModel):
    query: str
    location: Optional[str] = None
    total_results: int
    observations: List[PriceObservation]
    source: str
    observed_at: datetime
