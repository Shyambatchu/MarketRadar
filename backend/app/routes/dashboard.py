"""Executive dashboard: one read of what exists, what changed and system health.

Every figure is a count or a reading of stored rows; nothing is estimated and
no provider is called. Filters narrow the evidence sections; usage and health
are installation-wide by nature.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database.connection import get_db
from app.models.competitor import CompetitorObservation
from app.models.merchant import Merchant
from app.models.news_article import NewsArticle
from app.models.opportunity import Opportunity
from app.models.product_observation import ProductObservation
from app.models.report import Report
from app.models.serpapi_models import SerpSearch
from app.models.trend_observation import TrendObservation
from app.routes.validation import require_range
from app.services.ai_provider import get_ai_provider
from app.services.api_budget import credits_used_this_month
from app.services.opportunity_service import to_dict
from app.services.price_change_service import PriceChangeService
from app.services.trends_service import _aware

router = APIRouter()


@router.get("/dashboard")
def dashboard(market: Optional[str] = None, location: Optional[str] = None,
              days: Optional[int] = None, db: Session = Depends(get_db)):
    if days is not None:
        require_range("days", days, 1, 3650)
    since = datetime.now(timezone.utc) - timedelta(days=days) if days else None

    comp = db.query(CompetitorObservation)
    prod = db.query(ProductObservation)
    if market:
        comp = comp.filter(CompetitorObservation.market == market)
        prod = prod.filter(ProductObservation.market == market)
    if location:
        comp = comp.filter(CompetitorObservation.location_resolved == location)
        prod = prod.filter(ProductObservation.location_resolved == location)
    if since:
        comp = comp.filter(CompetitorObservation.observed_at >= since)
        prod = prod.filter(ProductObservation.observed_at >= since)

    comp_rows = comp.all()
    prod_rows = prod.all()
    merchant_ids = {r.merchant_id for r in comp_rows + prod_rows if r.merchant_id}
    times = [_aware(r.observed_at) for r in comp_rows + prod_rows if r.observed_at]

    alerts = PriceChangeService(db).detect(market=market, location=location)
    recent_alerts = [a for a in alerts.alerts
                     if not since or (a.observed_at and _aware(a.observed_at) >= since)]

    opp_query = db.query(Opportunity).filter(Opportunity.status != "dismissed")
    if market:
        opp_query = opp_query.filter(Opportunity.market == market)
    if location:
        opp_query = opp_query.filter(Opportunity.location == location)
    opportunities = opp_query.order_by(Opportunity.score.desc()).limit(5).all()

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    failures = db.execute(text(
        "SELECT COUNT(*), COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0)"
        " FROM api_usage WHERE timestamp >= :since"),
        {"since": week_ago.strftime("%Y-%m-%d %H:%M:%S")}).first()

    last_news = db.query(func.max(NewsArticle.last_seen_at)).scalar()
    last_interest = db.query(func.max(TrendObservation.observed_at)).filter(
        TrendObservation.request_key.isnot(None)).scalar()
    budget = settings.SERPAPI_MONTHLY_BUDGET
    month = credits_used_this_month(db)

    return {
        "generated_at": datetime.now(timezone.utc),
        "filters": {"market": market, "location": location, "days": days},
        "counts": {
            "competitors": len({r.merchant_id for r in comp_rows if r.merchant_id}),
            "businesses": len(merchant_ids),
            "confirmed_competitors": db.query(Merchant).filter(
                Merchant.id.in_(merchant_ids), Merchant.review_status == "confirmed").count()
            if merchant_ids else 0,
            "products_found": sum(1 for r in prod_rows if r.product_status == "found"),
            "verified_prices": sum(1 for r in prod_rows if r.price_status == "verified"),
            "competitor_observations": len(comp_rows),
            "product_observations": len(prod_rows),
            "markets": len({(r.market, r.location_resolved) for r in comp_rows + prod_rows}),
        },
        "freshness": {
            "first_observed_at": min(times) if times else None,
            "last_observed_at": max(times) if times else None,
            "last_news_collected_at": last_news,
            "last_search_interest_collected_at": last_interest,
        },
        "recent_changes": [a.model_dump() for a in recent_alerts[:8]],
        "recent_changes_total": len(recent_alerts),
        "top_opportunities": [to_dict(o) for o in opportunities],
        "recent_reports": [{"id": r.id, "title": r.title, "created_at": r.created_at}
                           for r in db.query(Report).order_by(Report.created_at.desc())
                           .limit(5).all()],
        "recent_searches": [{"query": s.query, "location": s.location,
                             "searched_at": s.searched_at, "cache_hit": s.cache_hit}
                            for s in db.query(SerpSearch).order_by(
                                SerpSearch.searched_at.desc()).limit(5).all()],
        "health": {
            "serpapi_configured": bool(settings.SERPAPI_API_KEY),
            "ai_provider_configured": get_ai_provider().is_configured(),
            "requests_last_7_days": int(failures[0] or 0),
            "failed_requests_last_7_days": int(failures[1] or 0),
            "credits_used_this_month": month,
            "monthly_budget": budget,
            "budget_remaining": max(budget - month, 0) if budget else None,
        },
    }
