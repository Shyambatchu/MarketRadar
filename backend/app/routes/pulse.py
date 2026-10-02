from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.pulse import MarketPulseOptionsResponse, MarketPulseResponse
from app.services.pulse_service import MarketPulseService

router = APIRouter()


def get_pulse_service(db: Session = Depends(get_db)) -> MarketPulseService:
    """Market Pulse reads the observation history and nothing else.

    No SerpApi key is required and no provider is called, so there is no 503
    path here and no credit is ever spent.
    """
    return MarketPulseService(db=db)


@router.get("/market-pulse/options", response_model=MarketPulseOptionsResponse)
def market_pulse_options(service: MarketPulseService = Depends(get_pulse_service)):
    """Markets and locations this installation has actually observed.

    The page offers these as choices so a selection always refers to real
    history; no market category is invented.
    """
    return service.options()


@router.get("/market-pulse", response_model=MarketPulseResponse)
def market_pulse(
    market: Optional[str] = None,
    location: Optional[str] = None,
    service: MarketPulseService = Depends(get_pulse_service),
):
    """A factual snapshot of one market and location.

    Deliberately one endpoint rather than six (summary / competitors /
    products / prices / visibility / trends). Every section derives from the
    same two filtered row sets, so splitting them would mean re-querying the
    same rows per section, and -- the reason that matters -- would let a client
    render one market's competitors beside another market's products. Returning
    them together with a single shared ``context`` makes that mismatch
    impossible by construction.

    The response reports what was observed and how strongly it is evidenced. It
    draws no conclusions.
    """
    return service.snapshot(market=market, location=location)
