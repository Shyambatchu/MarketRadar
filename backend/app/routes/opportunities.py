"""Opportunities: ranked, explainable leads built from stored evidence.

No endpoint here makes a provider request or spends a credit.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.routes.validation import MAX_LIST_LIMIT, require_range
from app.services.opportunity_service import (
    DISCLAIMER, FORMULA, STATUSES, OpportunityService, to_dict, weights,
)

router = APIRouter()


class OpportunityUpdate(BaseModel):
    status: Optional[str] = None
    note: Optional[str] = None


@router.get("/method")
def scoring_method():
    """The formula, the active weights and what the score is not."""
    return {"formula": FORMULA, "weights": weights(), "statuses": sorted(STATUSES),
            "disclaimer": DISCLAIMER}


@router.get("/sources")
def opportunity_sources(market: Optional[str] = None, location: Optional[str] = None,
                        db: Session = Depends(get_db)):
    """How much evidence each opportunity source has, and what it yields."""
    return OpportunityService(db).sources(market=market, location=location)


@router.get("")
@router.get("/")
def list_opportunities(status: Optional[str] = None, market: Optional[str] = None,
                       location: Optional[str] = None, min_score: Optional[float] = None,
                       limit: int = 100, db: Session = Depends(get_db)):
    """Saved opportunities, best score first. Dismissed ones only on request."""
    require_range("limit", limit, 1, MAX_LIST_LIMIT)
    if status and status not in STATUSES:
        raise HTTPException(status_code=400, detail="Unknown status.")
    rows = OpportunityService(db).list(status=status, market=market, location=location,
                                       min_score=min_score, limit=limit)
    return {"total": len(rows), "disclaimer": DISCLAIMER,
            "opportunities": [to_dict(r) for r in rows]}


@router.post("/refresh")
def refresh_opportunities(market: Optional[str] = None, location: Optional[str] = None,
                          db: Session = Depends(get_db)):
    """Rebuild opportunities from current evidence. Review statuses are kept."""
    service = OpportunityService(db)
    refreshed = service.refresh(market=market, location=location)
    rows = service.list(market=market, location=location)
    return {"refreshed": len(refreshed), "total": len(rows), "disclaimer": DISCLAIMER,
            "opportunities": [to_dict(r) for r in rows]}


@router.patch("/{opportunity_id}")
def update_opportunity(opportunity_id: int, update: OpportunityUpdate,
                       db: Session = Depends(get_db)):
    """Save, dismiss, mark reviewed, or annotate an opportunity (audited)."""
    try:
        row = OpportunityService(db).update(opportunity_id, status=update.status,
                                            note=update.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if row is None:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    return to_dict(row)
