"""Single registration point for every ORM model.

``Base.metadata.create_all()`` only creates tables for models that have been
imported by the time it runs. This package was empty, so a model's table existed
only if some service happened to import it -- ``merchants`` survived as a
leftover from code that no longer imports it, while ``businesses``, ``products``,
``trend_observations`` and ``market_events`` had no tables at all despite their
models existing. The failure mode was a runtime "no such table", not a startup
error, so it stayed invisible.

Importing every model here makes registration explicit and keeps the next
module from tripping over the same thing.
"""
from app.models.business import Business
from app.models.competitor import CompetitorObservation
from app.models.market_event import MarketEvent
from app.models.market_observation import MarketObservation
from app.models.merchant import Merchant
from app.models.product import Product
from app.models.product_observation import ProductObservation
from app.models.serpapi_models import (
    ApiUsage, SearchCache, SerpLocalResult, SerpSearch, SerpSearchResult,
)
from app.models.trend_observation import TrendObservation

__all__ = [
    "ApiUsage", "Business", "CompetitorObservation", "MarketEvent",
    "MarketObservation", "Merchant", "Product", "ProductObservation",
    "SearchCache",
    "SerpLocalResult", "SerpSearch", "SerpSearchResult", "TrendObservation",
]
