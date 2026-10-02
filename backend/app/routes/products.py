from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database.connection import get_db
from app.schemas.product import (
    ProductObservationListResponse, ProductObservationRecord,
    ProductSearchResponse,
)
from app.services.competitor_service import CompetitorService
from app.services.location_service import LocationResolutionError
from app.services.product_service import DEFAULT_MAX_MERCHANTS, ProductService
from app.services.serpapi_organic_service import (
    SerpApiLimitExceededError, SerpApiNotConfiguredError, SerpApiOrganicService,
    SerpApiProviderError,
)

router = APIRouter()


def get_product_service(db: Session = Depends(get_db)) -> ProductService:
    if not settings.SERPAPI_API_KEY:
        raise HTTPException(status_code=503, detail="SerpApi key not configured.")
    organic = SerpApiOrganicService(api_key=settings.SERPAPI_API_KEY, db=db)
    competitors = CompetitorService(db=db, organic_service=organic)
    return ProductService(db=db, competitor_service=competitors)


@router.get("/search", response_model=ProductSearchResponse)
def products_search(
    # Defaulted rather than required so a missing query returns our own 400.
    # FastAPI's validation would otherwise return 422, which this API reserves
    # for a location that has no provider-supported equivalent -- a
    # distinction the frontend depends on.
    q: str = "",
    market: str = "",
    location: Optional[str] = None,
    hl: str = "en",
    gl: str = "us",
    max_merchants: int = DEFAULT_MAX_MERCHANTS,
    service: ProductService = Depends(get_product_service),
):
    """Find product evidence across the merchants in a market.

    Status codes carry meaning the body cannot: 422 is a location with no
    provider-supported equivalent, 502 is a provider that failed. Neither is
    ever reported as "product not found" -- that is a 200 whose evidence says
    so explicitly.
    """
    try:
        return service.discover(product=q, market=market, location=location,
                                hl=hl, gl=gl, max_merchants=max_merchants)
    except ValueError as e:
        # An unusable request: rejected before any search runs, so nothing is
        # spent and nothing is persisted.
        raise HTTPException(status_code=400, detail=str(e))
    except LocationResolutionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except SerpApiNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except SerpApiLimitExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except SerpApiProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("", response_model=ProductObservationListResponse)
@router.get("/", response_model=ProductObservationListResponse)
def list_product_observations(
    q: Optional[str] = None,
    market: Optional[str] = None,
    merchant_id: Optional[int] = None,
    product_status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Saved product observations. Reads the database only -- no provider request."""
    service = ProductService(db=db, competitor_service=None)
    total, observations = service.list_saved(
        product_query=q, market=market, merchant_id=merchant_id,
        product_status=product_status, limit=limit)
    return ProductObservationListResponse(total=total, observations=observations)


@router.get("/{observation_id}", response_model=ProductObservationRecord)
def get_product_observation(observation_id: int, db: Session = Depends(get_db)):
    """One saved observation with its full evidence. No provider request."""
    service = ProductService(db=db, competitor_service=None)
    record = service.get_saved(observation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Product observation not found.")
    return record
