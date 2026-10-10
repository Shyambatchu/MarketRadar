import logging

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.schemas.price import PriceSearchResponse, PriceObservation
from app.services.serpapi_service import SerpApiService, SerpApiNotConfiguredError
from app.services.normalization_service import NormalizationService
from app.services.intelligence_service import IntelligenceService
from app.database.connection import get_db
from app.config import settings
from app.schemas.local_price import LocalPriceSearchResponse
from app.schemas.price_change import PriceAlertResponse
from app.services.price_change_service import PriceChangeService
from app.services.live_price_service import (
    LivePriceService, LocationResolutionError, SerpApiProviderError,
)

# Upper bound on the search radius, in miles. Beyond this a "local" price is
# no longer local, and the merchant fan-out (one credit each) grows unbounded.
MAX_RADIUS_MILES = 100


router = APIRouter()
logger = logging.getLogger("routes.prices")

def get_serpapi_service(db: Session = Depends(get_db)):
    return SerpApiService(api_key=settings.SERPAPI_API_KEY, db=db)

def get_normalization_service():
    return NormalizationService()

def get_intelligence_service():
    return IntelligenceService()

@router.get("/search", response_model=PriceSearchResponse)
def prices_search(
    q: str, 
    location: Optional[str] = None,
    serpapi_service: SerpApiService = Depends(get_serpapi_service),
    normalization_service: NormalizationService = Depends(get_normalization_service),
    intelligence_service: IntelligenceService = Depends(get_intelligence_service),
    db: Session = Depends(get_db)
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required.")

    try:
        raw_results = serpapi_service.search_google_shopping(query=q, location=location)
    except SerpApiNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except SerpApiProviderError as e:
        # The provider failed: 502, never a generic server error.
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        logger.exception("shopping price search failed")
        raise HTTPException(status_code=500, detail="Unable to retrieve market data. Try again in a moment.")

    observations = normalization_service.normalize_market_observation(
        raw_data=raw_results, 
        query=q, 
        location=location
    )

    # Persist the newly fetched observations
    intelligence_service.save_observations(db, observations)

    return PriceSearchResponse(
        query=q,
        location=location,
        total_results=len(observations),
        observations=observations,
        source="serpapi_google_shopping",
        observed_at=datetime.now(timezone.utc)
    )

@router.get("/history")
def get_price_history(
    product_name: str,
    intelligence_service: IntelligenceService = Depends(get_intelligence_service),
    db: Session = Depends(get_db)
):
    if not product_name.strip():
        raise HTTPException(status_code=400, detail="product_name is required.")
    
    history = intelligence_service.get_history(db, product_name)
    return {"product_name": product_name, "history": history}

@router.get("/changes")
def get_price_changes(
    product_name: str,
    intelligence_service: IntelligenceService = Depends(get_intelligence_service),
    db: Session = Depends(get_db)
):
    if not product_name.strip():
        raise HTTPException(status_code=400, detail="product_name is required.")
    
    return intelligence_service.get_changes(db, product_name)

@router.get("/local", response_model=LocalPriceSearchResponse)
def local_prices_search(
    product: str,
    area: str,
    # Defaulted so a missing radius gets our own 400; FastAPI's 422 is
    # reserved here for a location that cannot be resolved.
    radius: Optional[int] = None,
    reference_store: Optional[str] = None,
    hl: str = "en",
    gl: Optional[str] = None,
    db: Session = Depends(get_db)
):
    if not product.strip():
        raise HTTPException(status_code=400, detail="Product parameter 'product' is required.")
    if not area.strip():
        raise HTTPException(status_code=400, detail="Area parameter 'area' is required.")
    if radius is None or not 0 < radius <= MAX_RADIUS_MILES:
        raise HTTPException(
            status_code=400,
            detail="Radius must be between 1 and " + str(MAX_RADIUS_MILES) + " miles.")
    if not settings.SERPAPI_API_KEY:
        raise HTTPException(status_code=503, detail="SerpApi key not configured.")

    service = LivePriceService(api_key=settings.SERPAPI_API_KEY)
    try:
        return service.fetch_real_data(
            product=product, area=area, radius=radius, db=db,
            reference_merchant_name=reference_store, hl=hl, gl=gl,
        )
    except LocationResolutionError as e:
        # Never substitute a guessed search centre: a wrong centre silently
        # corrupts discovery, distance, radius filtering and cache identity.
        raise HTTPException(status_code=422, detail=str(e))
    except SerpApiProviderError as e:
        # The provider failed; never reported as a location problem.
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/alerts", response_model=PriceAlertResponse)
def price_alerts(
    q: Optional[str] = None,
    market: Optional[str] = None,
    location: Optional[str] = None,
    min_change_percent: Optional[float] = None,
    outlier_mad_k: Optional[float] = None,
    dispersion_min_percent: Optional[float] = None,
    db: Session = Depends(get_db),
):
    """Detected price changes over stored verified observations.

    Reads the database only -- no provider request, no credit. Thresholds
    default to the configured values and can be overridden per request.
    """
    for name, value in (("min_change_percent", min_change_percent),
                        ("outlier_mad_k", outlier_mad_k),
                        ("dispersion_min_percent", dispersion_min_percent)):
        if value is not None and value < 0:
            raise HTTPException(status_code=400, detail="'" + name + "' must not be negative.")
    return PriceChangeService(db).detect(
        product_query=q, market=market, location=location,
        min_change_percent=min_change_percent, outlier_mad_k=outlier_mad_k,
        dispersion_min_percent=dispersion_min_percent)
