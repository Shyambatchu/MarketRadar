"""SerpApi usage: what this installation spent, where, and an estimate of cost.

Everything here is read from ``api_usage`` (what the app recorded itself) and,
optionally, SerpApi's free account endpoint. No search is made.

The cost figure is an *estimate*: SerpApi bills a monthly plan, not per search,
so "cost per search" is the plan price divided by its search allowance. The
price table below was copied from the published pricing page and is labelled
with its source and the date it was read, so a stale figure is visible as such.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.services.api_budget import credits_used_this_month

PRICING_SOURCE = "https://serpapi.com/pricing"
PRICING_RETRIEVED = "2026-10-10"
# plan name (lower case) -> (USD per month, searches per month)
PUBLISHED_PLANS = {
    "free": (0.0, 250),
    "free plan": (0.0, 250),
    "starter": (25.0, 1000),
    "developer": (75.0, 5000),
    "production": (150.0, 15000),
    "big data": (275.0, 30000),
    "searcher": (725.0, 100000),
    "volume": (1475.0, 250000),
}

# Endpoint labels recorded by ApiBudgetManager, mapped to the SerpApi engine
# and the MarketRadar feature that spends them.
ENDPOINT_LABELS = {
    "google_organic": ("google", "Market Research / Competitors"),
    "merchant_website_indexed": ("google", "Products / Price Intelligence (merchant catalogues)"),
    "google_maps": ("google_maps", "Price Intelligence (geocode, nearby merchants)"),
    "google_shopping": ("google_shopping", "Price Intelligence (shopping offers)"),
    "google_trends": ("google_trends", "Search Interest"),
    "google_news": ("google_news", "Market News"),
}


def _plan_rate(account: Dict[str, Any]) -> Dict[str, Any]:
    if settings.SERPAPI_PLAN_MONTHLY_PRICE_USD is not None and \
            settings.SERPAPI_PLAN_SEARCHES_PER_MONTH:
        price, searches = (settings.SERPAPI_PLAN_MONTHLY_PRICE_USD,
                           settings.SERPAPI_PLAN_SEARCHES_PER_MONTH)
        basis = "configured (SERPAPI_PLAN_MONTHLY_PRICE_USD / SERPAPI_PLAN_SEARCHES_PER_MONTH)"
    else:
        plan = (account.get("plan_name") or "").strip().lower()
        if plan not in PUBLISHED_PLANS:
            return {"cost_per_search_usd": None, "cost_basis": (
                "Plan '" + (account.get("plan_name") or "unknown") + "' is not in the "
                "published table; set SERPAPI_PLAN_MONTHLY_PRICE_USD and "
                "SERPAPI_PLAN_SEARCHES_PER_MONTH to estimate cost.")}
        price, searches = PUBLISHED_PLANS[plan]
        basis = ("published price for plan '" + account.get("plan_name") + "', "
                 + PRICING_SOURCE + " retrieved " + PRICING_RETRIEVED)
    return {"cost_per_search_usd": round(price / searches, 5) if searches else None,
            "cost_basis": basis, "plan_monthly_price_usd": price,
            "plan_searches_per_month": searches}


def usage_breakdown(db: Session, account: Dict[str, Any]) -> Dict[str, Any]:
    rows = db.execute(text(
        "SELECT endpoint, COUNT(*), COALESCE(SUM(credits_used), 0),"
        " COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0),"
        " AVG(response_time), MAX(timestamp)"
        " FROM api_usage GROUP BY endpoint ORDER BY 3 DESC")).fetchall()
    daily = db.execute(text(
        "SELECT substr(timestamp, 1, 10) AS day, COALESCE(SUM(credits_used), 0),"
        " COUNT(*) FROM api_usage GROUP BY day ORDER BY day DESC LIMIT 30")).fetchall()

    rate = _plan_rate(account)
    per_search = rate.get("cost_per_search_usd")
    by_endpoint: List[Dict[str, Any]] = []
    for endpoint, requests, credits, failed, avg_rt, last in rows:
        engine, feature = ENDPOINT_LABELS.get(endpoint, (endpoint, endpoint))
        by_endpoint.append({
            "endpoint": endpoint, "engine": engine, "feature": feature,
            "requests": int(requests), "credits_used": int(credits),
            "failed_requests": int(failed),
            "avg_response_seconds": round(avg_rt, 2) if avg_rt is not None else None,
            "last_request_at": last,
            "estimated_cost_usd": round(credits * per_search, 2) if per_search is not None else None,
        })

    month = credits_used_this_month(db)
    budget = settings.SERPAPI_MONTHLY_BUDGET
    return {
        "generated_at": datetime.now(timezone.utc),
        "credits_used_this_month": month,
        "monthly_budget": budget,
        "budget_remaining": max(budget - month, 0) if budget else None,
        "budget_exhausted": bool(budget and month >= budget),
        "estimated_cost_this_month_usd": round(month * per_search, 2) if per_search is not None else None,
        "pricing_source": PRICING_SOURCE,
        "pricing_retrieved": PRICING_RETRIEVED,
        "by_endpoint": by_endpoint,
        "daily": [{"day": d, "credits_used": int(c), "requests": int(n)} for d, c, n in daily],
        **rate,
    }
