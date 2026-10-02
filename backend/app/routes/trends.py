from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.trend import (
    MerchantPresenceResponse, TrendListResponse, TrendSummaryResponse,
)
from app.services.trends_service import TrendsService

router = APIRouter()


def get_trends_service(db: Session = Depends(get_db)) -> TrendsService:
    """Trends reads the observation history and nothing else.

    No SerpApi key is required and no provider is called, so there is no 503
    path here and no credit is ever spent.
    """
    return TrendsService(db=db)


@router.get("/summary", response_model=TrendSummaryResponse)
def trends_summary(service: TrendsService = Depends(get_trends_service)):
    """What history exists and what can honestly be compared."""
    return service.summary()


@router.get("/prices", response_model=TrendListResponse)
def price_trends(
    q: Optional[str] = None,
    market: Optional[str] = None,
    location: Optional[str] = None,
    service: TrendsService = Depends(get_trends_service),
):
    """Movement in verified prices, per product, merchant and place.

    Unverified prices are excluded: one was never established as this
    product's price, so a movement built from it would be an artefact.
    """
    return service.price_trends(product_query=q, market=market, location=location)


@router.get("/availability", response_model=TrendListResponse)
def availability_trends(
    q: Optional[str] = None,
    market: Optional[str] = None,
    location: Optional[str] = None,
    service: TrendsService = Depends(get_trends_service),
):
    """Movement in product status at a merchant over time."""
    return service.availability_trends(product_query=q, market=market,
                                       location=location)


@router.get("/visibility", response_model=TrendListResponse)
def visibility_trends(
    market: Optional[str] = None,
    metric: str = "position",
    location: Optional[str] = None,
    service: TrendsService = Depends(get_trends_service),
):
    """Movement in merchant position, rating or review count."""
    try:
        return service.visibility_trends(market=market, metric=metric,
                                         location=location)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/merchants", response_model=MerchantPresenceResponse)
def merchant_presence(
    market: Optional[str] = None,
    location: Optional[str] = None,
    service: TrendsService = Depends(get_trends_service),
):
    """When each business was first and last seen in a market and location."""
    return service.merchant_presence(market=market, location=location)
