from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.analyst import AnalystResponse
from app.services.analyst_service import AnalystService

router = APIRouter()


def get_analyst_service(db: Session = Depends(get_db)) -> AnalystService:
    """The analyst reads a Market Pulse snapshot and nothing else.

    No SerpApi key is required and no provider search is made, so there is no
    503 path here and no credit is ever spent. An AI provider is optional: its
    absence withholds the narrative summary, not the analysis.
    """
    return AnalystService(db=db)


@router.get("/analysis", response_model=AnalystResponse)
def analyst_analysis(
    market: Optional[str] = None,
    location: Optional[str] = None,
    include_summary: bool = True,
    service: AnalystService = Depends(get_analyst_service),
):
    """Evidence-grounded analysis of one market and location.

    Every factual statement is computed from the Market Pulse snapshot by code
    and carries an evidence reference back to the records behind it. The only
    text a language model produces is ``summary``, and it is validated before
    being returned -- a summary asserting an unsupported conclusion, or citing
    a figure absent from the computed facts, is withheld with the reason given.

    ``include_summary=false`` skips the provider entirely and returns the
    factual analysis alone.
    """
    return service.analyse(market=market, location=location,
                           include_summary=include_summary)
