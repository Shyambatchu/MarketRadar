"""Market signals from additional SerpApi engines: Google Trends and Google News.

Live endpoints spend one credit per uncached request; the ``history`` and
``saved`` endpoints read the database only. Status codes follow the rest of
the API: 400 unusable request, 429 budget exhausted, 502 provider failure,
503 no key.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database.connection import get_db
from app.routes.validation import MAX_LIST_LIMIT, require_range
from app.services.news_service import NewsService
from app.services.search_interest_service import (
    DISCLAIMER, SearchInterestService, parse_terms, stored_requests,
)
from app.services.serpapi_organic_service import (
    SerpApiNotConfiguredError, SerpApiProviderError,
)

router = APIRouter()


def _run(call):
    try:
        return call()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SerpApiNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except SerpApiProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))


def _interest(db: Session) -> SearchInterestService:
    return SearchInterestService(db=db, api_key=settings.SERPAPI_API_KEY)


@router.get("/search-interest")
def search_interest(q: str = "", geo: str = "", date: str = "today 12-m",
                    db: Session = Depends(get_db)):
    """Relative interest over time for up to 5 comma-separated terms."""
    return _run(lambda: _interest(db).interest_over_time(parse_terms(q), geo=geo, date=date))


@router.get("/search-interest/regions")
def search_interest_regions(q: str = "", geo: str = "", date: str = "today 12-m",
                            region: Optional[str] = None, db: Session = Depends(get_db)):
    """Relative interest by region for one term."""
    return _run(lambda: _interest(db).interest_by_region(q.strip(), geo=geo, date=date,
                                                         region=region))


@router.get("/search-interest/related")
def search_interest_related(q: str = "", geo: str = "", date: str = "today 12-m",
                            db: Session = Depends(get_db)):
    """Rising and top related queries for one term."""
    return _run(lambda: _interest(db).related_queries(q.strip(), geo=geo, date=date))


@router.get("/search-interest/history")
def search_interest_history(q: Optional[str] = None, db: Session = Depends(get_db)):
    """Comparisons already collected. No provider request."""
    return {"disclaimer": DISCLAIMER, "requests": stored_requests(db, term=q)}


@router.get("/news")
def news(q: str = "", gl: str = "us", hl: str = "en", sort: str = "relevance",
         db: Session = Depends(get_db)):
    """Recent news results for a query, stored as dated, attributed sources."""
    return _run(lambda: NewsService(db, settings.SERPAPI_API_KEY).search(
        q, gl=gl, hl=hl, sort=sort))


@router.get("/news/saved")
def news_saved(q: Optional[str] = None, limit: int = 100, db: Session = Depends(get_db)):
    """Collected news. No provider request."""
    require_range("limit", limit, 1, MAX_LIST_LIMIT)
    return NewsService(db).saved(q=q, limit=limit)
