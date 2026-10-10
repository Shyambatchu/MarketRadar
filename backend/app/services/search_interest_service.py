"""Relative search interest from Google Trends (SerpApi ``google_trends``).

What the numbers are -- and are not
-----------------------------------
Google Trends reports interest on a 0-100 scale *relative to the peak within
one request*: the terms compared, the geography and the time range. 100 is the
busiest point of that request, not a quantity. So:

* values are only comparable inside one request (stored with a
  ``request_key``), never across requests;
* they are not search volume, market share, revenue or sales;
* a "change" here is a change in relative interest between the start and the
  end of the range, computed only when enough complete points exist.

Each call costs one search credit unless served from cache (24 h here; SerpApi
itself caches Trends for 1 h).
"""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.trend_observation import TrendObservation
from app.services.api_budget import ApiBudgetManager
from app.services.serpapi_organic_service import (
    SerpApiNotConfiguredError, SerpApiProviderError,
)

DISCLAIMER = ("Google Trends interest is relative (0-100, scaled to the peak of "
              "this comparison, place and period). It is not search volume, "
              "market share or sales, and is only comparable within one request.")

MAX_TERMS = 5          # provider limit for TIMESERIES
MAX_TERM_LENGTH = 100  # provider limit per query
CACHE_TTL_HOURS = 24
# Fewest complete points before a start-vs-end change is reported at all.
MIN_POINTS_FOR_CHANGE = 8

DATE_PRESETS = {"now 1-H", "now 4-H", "now 1-d", "now 7-d", "today 1-m",
                "today 3-m", "today 12-m", "today 5-y", "all"}
_CUSTOM_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2})? \d{4}-\d{2}-\d{2}(T\d{2})?$")
_GEO_RE = re.compile(r"^[A-Z]{2}(-[A-Z0-9]{1,3}){0,2}$")
REGION_LEVELS = {"COUNTRY", "REGION", "DMA", "CITY"}


def parse_terms(raw: str) -> List[str]:
    terms = [t.strip() for t in (raw or "").split(",") if t.strip()]
    seen, out = set(), []
    for t in terms:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def validate(terms: List[str], geo: str, date: str, max_terms: int = MAX_TERMS) -> None:
    """ValueError for anything the provider would reject, before any credit."""
    if not terms:
        raise ValueError("Provide at least one search term.")
    if len(terms) > max_terms:
        raise ValueError("At most " + str(max_terms) + " terms can be compared in one request.")
    for t in terms:
        if len(t) > MAX_TERM_LENGTH:
            raise ValueError("Each term must be at most " + str(MAX_TERM_LENGTH) + " characters.")
    if geo and not _GEO_RE.match(geo):
        raise ValueError("geo must be a country or subdivision code such as 'US', 'US-NJ' or "
                         "'IN', or empty for worldwide.")
    if date not in DATE_PRESETS and not _CUSTOM_DATE_RE.match(date or ""):
        raise ValueError("date must be one of " + ", ".join(sorted(DATE_PRESETS))
                         + " or a range 'YYYY-MM-DD YYYY-MM-DD'.")


def relative_change(values: List[float]) -> Optional[float]:
    """Mean of the last quarter vs the first quarter, as a percentage.

    None when there are too few points, or when the first quarter averages 0
    (any rise from nothing is unbounded, not a percentage).
    """
    if len(values) < MIN_POINTS_FOR_CHANGE:
        return None
    q = max(len(values) // 4, 1)
    start, end = sum(values[:q]) / q, sum(values[-q:]) / q
    if start == 0:
        return None
    return round((end - start) / start * 100.0, 1)


class SearchInterestService:
    def __init__(self, db: Session, api_key: Optional[str]):
        if not api_key:
            raise SerpApiNotConfiguredError("SerpApi key not configured.")
        self.db = db
        self.budget = ApiBudgetManager(db, api_key)

    def _search(self, cache_key: str, params: Dict[str, Any]) -> (Dict, bool):
        hits = self.budget.cache_hits
        data = self.budget.execute_search(cache_key, dict(params, engine="google_trends"),
                                          "google_trends", ttl_hours=CACHE_TTL_HOURS)
        if data is None:
            raise SerpApiProviderError(self.budget.last_error or
                                       "Google Trends did not respond.")
        return data, self.budget.cache_hits > hits

    # ------------------------------------------------------------------
    def interest_over_time(self, terms: List[str], geo: str = "",
                           date: str = "today 12-m", persist: bool = True) -> Dict[str, Any]:
        validate(terms, geo, date)
        q = ",".join(terms)
        request_key = "TIMESERIES|" + q.lower() + "|" + geo + "|" + date
        params = {"q": q, "data_type": "TIMESERIES", "date": date, "tz": "0"}
        if geo:
            params["geo"] = geo
        data, cache_hit = self._search("v1|trends|" + request_key, params)

        timeline = ((data.get("interest_over_time") or {}).get("timeline_data") or [])
        series: Dict[str, List[Dict[str, Any]]] = {t: [] for t in terms}
        for point in timeline if isinstance(timeline, list) else []:
            if not isinstance(point, dict):
                continue
            try:
                at = datetime.fromtimestamp(int(point.get("timestamp")), tz=timezone.utc)
            except (TypeError, ValueError):
                continue
            for value in point.get("values") or []:
                term = _match_term(value.get("query"), terms)
                extracted = value.get("extracted_value")
                if term is None or not isinstance(extracted, (int, float)):
                    continue
                series[term].append({"date": at, "label": point.get("date"),
                                     "value": float(extracted),
                                     "partial": bool(point.get("partial_data"))})

        if persist and not cache_hit:
            # A cached response was already stored when it was first fetched.
            for term, points in series.items():
                for p in points:
                    self.db.add(TrendObservation(
                        keyword=term, region=geo, interest_value=p["value"],
                        period=p["label"], source="serpapi_google_trends",
                        point_at=p["date"], timeframe=date, request_key=request_key,
                        data_type="TIMESERIES", partial=p["partial"]))
            self.db.commit()

        out_series = []
        for term, points in series.items():
            complete = [p["value"] for p in points if not p["partial"]]
            peak = max(points, key=lambda p: p["value"]) if points else None
            change = relative_change(complete)
            out_series.append({
                "term": term, "points": points, "point_count": len(points),
                "average": round(sum(complete) / len(complete), 1) if complete else None,
                "latest": complete[-1] if complete else None,
                "peak_date": peak["date"] if peak else None,
                "relative_change_percent": change,
                "change_detail": None if change is not None else (
                    "Too few complete points (" + str(len(complete)) + ") to compare the "
                    "start and end of the range." if len(complete) < MIN_POINTS_FOR_CHANGE
                    else "Interest at the start of the range was 0, so a percentage "
                         "change is undefined."),
            })
        return {"terms": terms, "geo": geo or None, "date": date,
                "request_key": request_key, "cache_hit": cache_hit,
                "collected_at": datetime.now(timezone.utc), "disclaimer": DISCLAIMER,
                "series": out_series,
                "has_data": any(s["point_count"] for s in out_series)}

    def interest_by_region(self, term: str, geo: str = "", date: str = "today 12-m",
                           region: Optional[str] = None) -> Dict[str, Any]:
        validate([term], geo, date, max_terms=1)
        if region and region not in REGION_LEVELS:
            raise ValueError("region must be one of " + ", ".join(sorted(REGION_LEVELS)) + ".")
        params = {"q": term, "data_type": "GEO_MAP_0", "date": date, "tz": "0"}
        if geo:
            params["geo"] = geo
        if region:
            params["region"] = region
        data, cache_hit = self._search(
            "v1|trends|GEO_MAP_0|" + term.lower() + "|" + geo + "|" + date + "|" + (region or ""),
            params)
        regions = []
        for item in data.get("interest_by_region") or []:
            if isinstance(item, dict) and isinstance(item.get("extracted_value"), (int, float)):
                regions.append({"location": item.get("location"), "geo": item.get("geo"),
                                "value": float(item["extracted_value"])})
        regions.sort(key=lambda r: -r["value"])
        return {"term": term, "geo": geo or None, "date": date, "region": region,
                "cache_hit": cache_hit, "disclaimer": DISCLAIMER, "regions": regions}

    def related_queries(self, term: str, geo: str = "",
                        date: str = "today 12-m") -> Dict[str, Any]:
        validate([term], geo, date, max_terms=1)
        params = {"q": term, "data_type": "RELATED_QUERIES", "date": date, "tz": "0"}
        if geo:
            params["geo"] = geo
        data, cache_hit = self._search(
            "v1|trends|RELATED_QUERIES|" + term.lower() + "|" + geo + "|" + date, params)
        related = data.get("related_queries") or {}

        def items(kind):
            out = []
            for item in related.get(kind) or []:
                if isinstance(item, dict) and item.get("query"):
                    out.append({"query": item["query"], "value_label": item.get("value"),
                                "value": item.get("extracted_value")})
            return out

        return {"term": term, "geo": geo or None, "date": date, "cache_hit": cache_hit,
                "rising": items("rising"), "top": items("top"),
                "detail": "'Rising' values are Google's percentage growth labels "
                          "('Breakout' = very large); 'top' values are relative (0-100)."}


def stored_requests(db: Session, term: Optional[str] = None, limit: int = 20) -> List[Dict]:
    """Previously collected comparisons, newest first. Free."""
    query = db.query(TrendObservation).filter(TrendObservation.request_key.isnot(None))
    if term:
        query = query.filter(TrendObservation.keyword.ilike(term))
    groups: Dict[str, Dict] = {}
    for row in query.order_by(TrendObservation.observed_at.desc()).all():
        g = groups.setdefault(row.request_key, {
            "request_key": row.request_key, "geo": row.region or None,
            "date": row.timeframe, "collected_at": row.observed_at,
            "terms": [], "points": 0})
        if row.keyword not in g["terms"]:
            g["terms"].append(row.keyword)
        g["points"] += 1
    return list(groups.values())[:limit]


def _match_term(query: Optional[str], terms: List[str]) -> Optional[str]:
    if not query:
        return None
    for t in terms:
        if t.lower() == query.lower():
            return t
    return None
