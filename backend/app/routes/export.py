"""CSV exports of stored evidence.

Each export is produced by the same service call the matching page uses, with
the same filters, so a downloaded file always matches what was on screen. They
read the database only: no provider request, no credit.

CSV rather than a spreadsheet format: it opens in Excel, Sheets and Numbers
without adding a dependency, and is what a reviewer can audit line by line.
"""
import csv
import io
import json
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.routes.validation import MAX_LIST_LIMIT, require_range
from app.services.competitor_service import CompetitorService
from app.services.opportunity_service import OpportunityService
from app.services.price_change_service import PriceChangeService
from app.services.product_service import ProductService
from app.services.trends_service import TrendsService

router = APIRouter()

# Exports may be larger than a page of the UI, but are still bounded.
MAX_EXPORT_ROWS = MAX_LIST_LIMIT * 20


def _csv_response(name: str, header: List[str], rows: Iterable[List]) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        writer.writerow(["" if v is None else _cell(v) for v in row])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # A UTF-8 BOM so Excel reads non-ASCII names and currency symbols correctly.
    data = "﻿" + buffer.getvalue()
    return StreamingResponse(
        iter([data]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition":
                 'attachment; filename="marketradar-' + name + "-" + stamp + '.csv"'})


def _cell(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value)
    text = str(value)
    # Neutralise spreadsheet formula injection from provider-supplied text.
    return "'" + text if text[:1] in ("=", "+", "-", "@") and not _is_number(text) else text


def _is_number(text: str) -> bool:
    try:
        float(text)
        return True
    except ValueError:
        return False


@router.get("/competitors.csv")
def export_competitors(market: Optional[str] = None, location: Optional[str] = None,
                       status: Optional[str] = None, review_status: Optional[str] = None,
                       limit: int = MAX_EXPORT_ROWS, db: Session = Depends(get_db)):
    require_range("limit", limit, 1, MAX_EXPORT_ROWS)
    _, competitors = CompetitorService(db=db, organic_service=None).list_saved(
        market=market, location_resolved=location, status=status, limit=limit,
        review_status=review_status)
    return _csv_response("competitors", [
        "id", "name", "display_name", "domain", "website", "address", "status",
        "status_reason", "review_status", "review_note", "entity_type",
        "match_method", "match_confidence", "rating", "reviews", "best_position",
        "markets", "locations", "discovery_sources", "evidence_count",
        "first_seen_at", "last_seen_at",
    ], ([c.id, c.name, c.display_name, c.domain, c.website, c.address, c.status,
         c.status_reason, c.review_status, c.review_note, c.entity_type,
         c.match_method, c.match_confidence, c.rating, c.reviews, c.best_position,
         c.markets, c.locations, c.discovery_sources, c.evidence_count,
         c.first_seen_at, c.last_seen_at] for c in competitors))


@router.get("/products.csv")
def export_products(q: Optional[str] = None, market: Optional[str] = None,
                    merchant_id: Optional[int] = None,
                    product_status: Optional[str] = None,
                    limit: int = MAX_EXPORT_ROWS, db: Session = Depends(get_db)):
    require_range("limit", limit, 1, MAX_EXPORT_ROWS)
    _, rows = ProductService(db=db, competitor_service=None).list_saved(
        product_query=q, market=market, merchant_id=merchant_id,
        product_status=product_status, limit=limit)
    return _csv_response("product-observations", [
        "id", "observed_at", "product_query", "market", "location", "merchant",
        "merchant_domain", "product_name", "observed_size", "product_status",
        "price_status", "verification_reason", "price", "currency", "source_type",
        "source_url", "page_type", "evidence_scope", "inventory_confirmed",
    ], ([r.id, r.observed_at, r.product_query, r.market, r.location_resolved,
         r.merchant_name, r.merchant_domain, r.product_name, r.observed_size,
         r.product_status, r.price_status, r.verification_reason, r.price,
         r.currency, r.source_type, r.source_url, r.page_type, r.evidence_scope,
         r.inventory_confirmed] for r in rows))


@router.get("/prices.csv")
def export_verified_prices(q: Optional[str] = None, market: Optional[str] = None,
                           limit: int = MAX_EXPORT_ROWS, db: Session = Depends(get_db)):
    """Verified price observations only -- the figures statistics are built on."""
    require_range("limit", limit, 1, MAX_EXPORT_ROWS)
    _, rows = ProductService(db=db, competitor_service=None).list_saved(
        product_query=q, market=market, limit=limit)
    verified = [r for r in rows if r.price_status == "verified" and r.price is not None]
    return _csv_response("verified-prices", [
        "id", "observed_at", "product_query", "market", "location", "merchant",
        "product_name", "observed_size", "price", "currency", "source_type", "source_url",
    ], ([r.id, r.observed_at, r.product_query, r.market, r.location_resolved,
         r.merchant_name, r.product_name, r.observed_size, r.price, r.currency,
         r.source_type, r.source_url] for r in verified))


@router.get("/price-alerts.csv")
def export_price_alerts(q: Optional[str] = None, market: Optional[str] = None,
                        location: Optional[str] = None, db: Session = Depends(get_db)):
    result = PriceChangeService(db).detect(product_query=q, market=market, location=location)
    return _csv_response("price-alerts", [
        "type", "severity", "confidence", "product", "merchant", "market", "location",
        "currency", "previous_price", "current_price", "change_absolute",
        "change_percent", "previous_observed_at", "observed_at", "explanation",
        "record_ids", "source_urls",
    ], ([a.type, a.severity, a.confidence, a.product, a.merchant, a.market, a.location,
         a.currency, a.previous_price, a.current_price, a.change_absolute,
         a.change_percent, a.previous_observed_at, a.observed_at, a.explanation,
         a.record_ids, a.source_urls] for a in result.alerts))


@router.get("/trends.csv")
def export_trends(signal: str = "prices", q: Optional[str] = None,
                  market: Optional[str] = None, location: Optional[str] = None,
                  metric: str = "position", db: Session = Depends(get_db)):
    """One row per collapsed measurement point of every series."""
    service = TrendsService(db=db)
    if signal == "prices":
        result = service.price_trends(product_query=q, market=market, location=location)
    elif signal == "availability":
        result = service.availability_trends(product_query=q, market=market,
                                             location=location)
    elif signal == "visibility":
        try:
            result = service.visibility_trends(market=market, metric=metric,
                                               location=location)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(status_code=400,
                            detail="signal must be prices, availability or visibility.")

    def rows():
        for s in result.series:
            for p in s.points:
                yield [s.subject, s.metric, s.context, s.status, s.direction,
                       p.observed_at, p.value, p.label, p.observation_count]

    return _csv_response("trends-" + signal, [
        "subject", "metric", "context", "series_status", "series_direction",
        "observed_at", "value", "label", "observation_count",
    ], rows())


@router.get("/opportunities.csv")
def export_opportunities(status: Optional[str] = None, market: Optional[str] = None,
                         location: Optional[str] = None, db: Session = Depends(get_db)):
    rows = OpportunityService(db).list(status=status, market=market, location=location,
                                       limit=MAX_EXPORT_ROWS)

    def lines():
        for r in rows:
            b = json.loads(r.breakdown or "{}")
            e = json.loads(r.evidence or "{}")
            inputs = b.get("inputs") or {}
            yield [r.id, r.score, r.title, r.category, r.market, r.location, r.status,
                   r.confidence, inputs.get("impact"), inputs.get("confidence"),
                   inputs.get("freshness"), inputs.get("relevance"), b.get("missing"),
                   r.suggested_action, e.get("source_urls"), r.evidence_observed_at,
                   r.created_at]

    return _csv_response("opportunities", [
        "id", "score", "title", "category", "market", "location", "status",
        "confidence", "impact", "confidence_input", "freshness", "relevance",
        "missing_inputs", "suggested_action", "source_urls", "evidence_observed_at",
        "created_at",
    ], lines())
