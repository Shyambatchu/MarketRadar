"""Saved reports and saved searches. No provider request, no credit."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.report import Report
from app.models.saved_search import SavedSearch
from app.services.report_service import create_report, render_html, summary

router = APIRouter()

SAVED_SEARCH_MODULES = {"research", "competitors", "products", "prices", "interest", "news"}


class ReportRequest(BaseModel):
    market: Optional[str] = None
    location: Optional[str] = None
    title: Optional[str] = None


class SavedSearchRequest(BaseModel):
    module: str
    query: str
    market: Optional[str] = None
    location: Optional[str] = None
    label: Optional[str] = None


@router.post("/reports")
def generate_report(request: ReportRequest, db: Session = Depends(get_db)):
    """Capture an evidence snapshot for a market and location as a report."""
    return summary(create_report(db, request.market, request.location, request.title))


@router.get("/reports")
def list_reports(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.query(Report).order_by(Report.created_at.desc(), Report.id.desc()).limit(
        max(1, min(limit, 200))).all()
    return {"total": len(rows), "reports": [summary(r) for r in rows]}


@router.get("/reports/{report_id}.html", response_class=HTMLResponse)
def report_html(report_id: int, db: Session = Depends(get_db)):
    """Print-ready report. Use the browser's Save as PDF for a PDF copy."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return HTMLResponse(render_html(report))


@router.delete("/reports/{report_id}", status_code=204)
def delete_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    db.delete(report)
    db.commit()


@router.get("/saved-searches")
def list_saved_searches(module: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(SavedSearch)
    if module:
        query = query.filter(SavedSearch.module == module)
    rows = query.order_by(SavedSearch.created_at.desc(), SavedSearch.id.desc()).all()
    return {"total": len(rows), "saved_searches": [
        {"id": r.id, "module": r.module, "label": r.label, "query": r.query,
         "market": r.market, "location": r.location, "created_at": r.created_at}
        for r in rows]}


@router.post("/saved-searches")
def save_search(request: SavedSearchRequest, db: Session = Depends(get_db)):
    if request.module not in SAVED_SEARCH_MODULES:
        raise HTTPException(status_code=400, detail="module must be one of: "
                            + ", ".join(sorted(SAVED_SEARCH_MODULES)) + ".")
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="A query is required.")
    location = (request.location or "").strip() or None
    existing = db.query(SavedSearch).filter(
        SavedSearch.module == request.module, SavedSearch.query == query,
        SavedSearch.location.is_(None) if location is None else SavedSearch.location == location
    ).first()
    if existing:
        return {"id": existing.id, "created": False}
    row = SavedSearch(module=request.module, query=query, location=location,
                      market=(request.market or "").strip() or None,
                      label=(request.label or "").strip() or None)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This search is already saved.")
    return {"id": row.id, "created": True}


@router.delete("/saved-searches/{search_id}", status_code=204)
def delete_saved_search(search_id: int, db: Session = Depends(get_db)):
    row = db.query(SavedSearch).filter(SavedSearch.id == search_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Saved search not found.")
    db.delete(row)
    db.commit()
