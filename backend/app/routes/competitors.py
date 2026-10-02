from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database.connection import get_db
from app.schemas.competitor import (
    Competitor, CompetitorListResponse, CompetitorSearchResponse,
)
from app.services.competitor_service import CompetitorService
from app.services.location_service import LocationResolutionError
from app.services.serpapi_organic_service import (
    SerpApiOrganicService, SerpApiLimitExceededError, SerpApiNotConfiguredError,
    SerpApiProviderError,
)

router = APIRouter()


def get_competitor_service(db: Session = Depends(get_db)) -> CompetitorService:
    if not settings.SERPAPI_API_KEY:
        raise HTTPException(status_code=503, detail="SerpApi key not configured.")
    organic = SerpApiOrganicService(api_key=settings.SERPAPI_API_KEY, db=db)
    return CompetitorService(db=db, organic_service=organic)


@router.get("/search", response_model=CompetitorSearchResponse)
def competitors_search(
    market: str = "",
    q: str = "",
    location: Optional[str] = None,
    hl: str = "en",
    gl: str = "us",
    num: int = 20,
    service: CompetitorService = Depends(get_competitor_service),
):
    """Discover competitors for a market and place.

    Status codes carry meaning the body cannot: 422 is a location with no
    provider-supported equivalent, 502 is a provider that failed. Neither is
    ever reported as "no competitors found", which is what a 200 with an empty
    list means.
    """
    try:
        return service.discover(market=market, query=q, location=location,
                                hl=hl, gl=gl, num=num)
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


@router.get("", response_model=CompetitorListResponse)
@router.get("/", response_model=CompetitorListResponse)
def list_competitors(
    market: Optional[str] = None,
    location: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Saved competitors. Reads the database only -- no provider request."""
    service = CompetitorService(db=db, organic_service=None)
    total, competitors = service.list_saved(
        market=market, location_resolved=location, status=status, limit=limit)
    return CompetitorListResponse(total=total, competitors=competitors)


@router.get("/{competitor_id}", response_model=Competitor)
def get_competitor(competitor_id: int, db: Session = Depends(get_db)):
    """One competitor with its full discovery evidence. No provider request."""
    service = CompetitorService(db=db, organic_service=None)
    competitor = service.get_saved(competitor_id)
    if competitor is None:
        raise HTTPException(status_code=404, detail="Competitor not found.")
    return competitor
