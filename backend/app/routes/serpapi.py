import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.routes.validation import MAX_RESULTS_PER_SEARCH, require_range
from app.config import settings
from app.services.serpapi_organic_service import (
    SerpApiOrganicService, SerpApiLimitExceededError, SerpApiProviderError,
)
from app.services.location_service import LocationResolutionError
from app.services.serpapi_account import fetch_account_usage
from app.services.usage_service import usage_breakdown
from typing import List
from app.schemas.serpapi_schemas import SerpSearchResponseSchema, BatchSearchRequest, BatchSearchResponse, UsageStatsResponse, RecentSearchSchema

router = APIRouter()
logger = logging.getLogger("routes.serpapi")

def get_organic_service(db: Session = Depends(get_db)):
    if not settings.SERPAPI_API_KEY:
        raise HTTPException(status_code=503, detail="SerpApi key not configured.")
    return SerpApiOrganicService(api_key=settings.SERPAPI_API_KEY, db=db)

@router.get("/search", response_model=SerpSearchResponseSchema)
def search_organic(
    q: str, 
    location: str = None, 
    num: int = 10,
    hl: str = "en",
    gl: str = "us",
    google_domain: str = "google.com",
    service: SerpApiOrganicService = Depends(get_organic_service)
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query 'q' is required.")
    require_range("num", num, 1, MAX_RESULTS_PER_SEARCH)

    try:
        # Market settings are request parameters, not fixed to one country.
        results = service.search_google(query=q, location=location, num=num,
                                        hl=hl, gl=gl, google_domain=google_domain)
        return results
    except LocationResolutionError as e:
        # The location never reaches the provider unresolved, so the user gets
        # a readable message instead of the provider's
        # "Unsupported `<location>` location - location parameter."
        raise HTTPException(status_code=422, detail=str(e))
    except SerpApiLimitExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except SerpApiProviderError as e:
        # 502: the provider failed. Never reported as a search returning nothing.
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        # Internal detail (SQL, stack text) is logged, never returned.
        logger.exception("market research search failed")
        raise HTTPException(status_code=500,
                            detail="The search could not be completed. Try again in a moment.")

@router.post("/search/batch", response_model=BatchSearchResponse)
def batch_search(
    req: BatchSearchRequest,
    service: SerpApiOrganicService = Depends(get_organic_service)
):
    if len(req.queries) > 20:
        raise HTTPException(status_code=400, detail="Batch size limited to 20 queries.")
        
    results = []
    failed = 0

    # One unresolvable location invalidates every query in the batch, so it is
    # reported once rather than counted as N opaque failures.
    if req.location:
        try:
            service.resolver.resolve(req.location)
        except LocationResolutionError as e:
            raise HTTPException(status_code=422, detail=str(e))

    errors = []
    for q in req.queries:
        try:
            res = service.search_google(query=q, location=req.location)
            results.append(res)
        except SerpApiLimitExceededError as e:
            # The budget is spent: the remaining queries would all fail too.
            raise HTTPException(status_code=429, detail=str(e))
        except SerpApiProviderError as e:
            failed += 1
            errors.append({"query": q, "detail": str(e)})
        except Exception:
            logger.exception("batch search query failed")
            failed += 1
            errors.append({"query": q, "detail": "The search could not be completed."})

    return {
        "total_requested": len(req.queries),
        "successful": len(results),
        "failed": failed,
        "errors": errors,
        "results": results
    }

@router.get("/usage", response_model=UsageStatsResponse)
def get_usage(db: Session = Depends(get_db)):
    """Local request history plus SerpApi's own account quota.

    Runs no search: local rows are read from the database and the quota comes
    from SerpApi's account endpoint, so asking about usage costs nothing. A
    missing key or an unreachable account endpoint leaves the account fields
    null rather than failing the request -- usage reporting is not a gate on
    anything, and there is no application-level budget to enforce (spec 34).
    """
    service = SerpApiOrganicService(api_key=settings.SERPAPI_API_KEY, db=db)
    return service.get_usage_stats()

@router.get("/recent", response_model=List[RecentSearchSchema])
def get_recent_searches(db: Session = Depends(get_db)):
    service = SerpApiOrganicService(api_key=settings.SERPAPI_API_KEY, db=db)
    return service.get_recent_searches()


@router.get("/usage/breakdown")
def get_usage_breakdown(db: Session = Depends(get_db)):
    """Usage per engine and feature, monthly spend against the optional budget,
    and a cost estimate whose basis (plan, source, date) is stated. No search."""
    return usage_breakdown(db, fetch_account_usage(settings.SERPAPI_API_KEY))
