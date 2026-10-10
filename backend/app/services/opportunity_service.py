"""Opportunity scoring: rank evidence-backed leads with a transparent formula.

    score = 100 x (w_impact x impact + w_confidence x confidence
                   + w_freshness x freshness + w_relevance x relevance)

Every input is normalised to [0, 1] and the weights are normalised to sum to 1,
so the score lies in [0, 100]. Inputs, in plain terms:

* **impact** -- how large the underlying signal is. Price gap: spread / 50%
  (capped at 1). Competitor price move: |change| / 20%. New offer: 0.3 (a fact
  of presence, not a magnitude). Rising search interest: change / 100%.
* **confidence** -- half the source's own confidence label (high 1.0, medium
  0.6, low 0.3) and half the number of independent supporting observations
  (n / 4, capped at 1).
* **freshness** -- 0.5 ^ (age in days / half-life), from the newest supporting
  observation.
* **relevance** -- 1.0 for a business the user confirmed as a competitor, 0.6
  for an unreviewed one, 0.7 for a market-wide signal with no business
  attached. A business the user rejected produces no opportunity at all.

A missing input contributes 0 and is listed in ``breakdown.missing``; it is
never guessed. The score orders leads for review. It is not a probability of
commercial success and has not been validated against outcomes.

Opportunities are rebuilt from stored evidence on refresh (no provider
request, no credit). The same lead keeps its id and its review status.
"""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.audit_event import AuditEvent
from app.models.merchant import Merchant
from app.models.opportunity import Opportunity
from app.models.product_observation import ProductObservation
from app.models.trend_observation import TrendObservation
from app.services.price_change_service import PriceChangeService
from app.services.search_interest_service import relative_change
from app.services.trends_service import _aware

STATUSES = {"new", "saved", "reviewed", "dismissed"}
CONFIDENCE_VALUE = {"high": 1.0, "medium": 0.6, "low": 0.3}
RISING_INTEREST_MIN_PERCENT = 20.0

FORMULA = ("score = 100 x (w_impact x impact + w_confidence x confidence + "
           "w_freshness x freshness + w_relevance x relevance); inputs in [0,1], "
           "weights normalised to sum to 1. A missing input contributes 0.")
DISCLAIMER = ("The score ranks leads for review. It is not a probability of "
              "commercial success and has not been validated against outcomes.")


def weights() -> Dict[str, float]:
    raw = {"impact": settings.OPPORTUNITY_WEIGHT_IMPACT,
           "confidence": settings.OPPORTUNITY_WEIGHT_CONFIDENCE,
           "freshness": settings.OPPORTUNITY_WEIGHT_FRESHNESS,
           "relevance": settings.OPPORTUNITY_WEIGHT_RELEVANCE}
    raw = {k: max(v, 0.0) for k, v in raw.items()}
    total = sum(raw.values()) or 1.0
    return {k: round(v / total, 4) for k, v in raw.items()}


def freshness(observed_at: Optional[datetime], now: datetime) -> Optional[float]:
    if observed_at is None:
        return None
    age_days = max((now - _aware(observed_at)).total_seconds() / 86400.0, 0.0)
    return round(0.5 ** (age_days / settings.OPPORTUNITY_FRESHNESS_HALF_LIFE_DAYS), 4)


def score(inputs: Dict[str, Optional[float]]) -> Dict[str, Any]:
    w = weights()
    contributions, missing = {}, []
    for name, weight in w.items():
        value = inputs.get(name)
        if value is None:
            missing.append(name)
            value = 0.0
        value = min(max(value, 0.0), 1.0)
        inputs[name] = value if name not in missing else None
        contributions[name] = round(100 * weight * value, 2)
    return {"score": round(sum(contributions.values()), 1), "inputs": inputs,
            "weights": w, "contributions": contributions, "missing": missing,
            "formula": FORMULA}


class OpportunityService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    def refresh(self, market: Optional[str] = None,
                location: Optional[str] = None) -> List[Opportunity]:
        now = datetime.now(timezone.utc)
        candidates = self._price_candidates(market, location, now)
        candidates += self._interest_candidates(market, now)

        seen = []
        for c in candidates:
            row = self.db.query(Opportunity).filter(
                Opportunity.fingerprint == c["fingerprint"]).first()
            if row is None:
                row = Opportunity(fingerprint=c["fingerprint"], status="new")
                self.db.add(row)
            for field in ("title", "category", "market", "location", "product",
                          "merchant_id", "confidence", "relevance_note",
                          "suggested_action", "evidence_observed_at"):
                setattr(row, field, c[field])
            row.score = c["breakdown"]["score"]
            row.breakdown = json.dumps(c["breakdown"])
            row.evidence = json.dumps(c["evidence"])
            row.updated_at = now
            seen.append(row)
        self.db.commit()
        return seen

    def _review(self, merchant_id: Optional[int]):
        if not merchant_id:
            return None, 0.7, "Market-wide signal; no single business attached."
        merchant = self.db.query(Merchant).filter(Merchant.id == merchant_id).first()
        review = merchant.review_status if merchant else None
        if review == "rejected":
            return merchant, None, None
        if review == "confirmed":
            return merchant, 1.0, "Involves a business you confirmed as a competitor."
        return merchant, 0.6, "Involves a business not yet reviewed as a competitor."

    def _price_candidates(self, market, location, now) -> List[Dict[str, Any]]:
        alerts = PriceChangeService(self.db).detect(market=market, location=location).alerts
        out = []
        for a in alerts:
            if a.type == "price_dispersion":
                impact = min((a.change_percent or 0) / 50.0, 1.0)
                category, title = "price_gap", (
                    "Price gap of " + str(a.change_percent) + "% for " + a.product)
                action = ("Compare the lowest and highest offers (sizes, variants, "
                          "shipping) before deciding where to position on price.")
            elif a.type == "price_decrease":
                impact = min(abs(a.change_percent or 0) / 20.0, 1.0)
                category, title = "competitor_price_move", (
                    (a.merchant or "A competitor") + " cut the price of " + a.product
                    + " by " + str(abs(a.change_percent)) + "%")
                action = "Check whether the cut is a promotion and how it compares to yours."
            elif a.type == "price_increase":
                impact = min(abs(a.change_percent or 0) / 20.0, 1.0)
                category, title = "pricing_headroom", (
                    (a.merchant or "A competitor") + " raised the price of " + a.product
                    + " by " + str(a.change_percent) + "%")
                action = "Investigate whether there is room to adjust your own price."
            elif a.type == "new_offer":
                impact = 0.3
                category, title = "new_competitor_offer", (
                    (a.merchant or "A merchant") + " newly offers " + a.product)
                action = "Review the new offer and whether it targets your customers."
            else:
                continue
            merchant, relevance, note = self._review(
                a.merchant_id if category != "price_gap" else None)
            if relevance is None:
                continue  # the user rejected this business as a competitor
            observed = a.observed_at
            conf = 0.5 * CONFIDENCE_VALUE.get(a.confidence, 0.3) + \
                0.5 * min(len(a.record_ids) / 4.0, 1.0)
            breakdown = score({"impact": round(impact, 4), "confidence": round(conf, 4),
                               "freshness": freshness(observed, now),
                               "relevance": relevance})
            out.append({
                "fingerprint": "|".join(str(p) for p in (
                    category, a.product.lower(), a.merchant_id or "", a.market or "",
                    a.location or "", a.currency or "")),
                "title": title, "category": category, "market": a.market,
                "location": a.location, "product": a.product,
                "merchant_id": a.merchant_id, "confidence": a.confidence,
                "relevance_note": note, "suggested_action": action,
                "evidence_observed_at": observed, "breakdown": breakdown,
                "evidence": {"record_ids": a.record_ids, "source_urls": a.source_urls,
                             "explanation": a.explanation, "source": "price_alerts"},
            })
        return out

    def _interest_candidates(self, market, now) -> List[Dict[str, Any]]:
        """Rising relative search interest from stored Google Trends requests."""
        query = self.db.query(TrendObservation).filter(
            TrendObservation.request_key.isnot(None),
            TrendObservation.data_type == "TIMESERIES")
        if market:
            query = query.filter(TrendObservation.keyword.ilike(market))
        series: Dict[tuple, List] = {}
        for row in query.all():
            series.setdefault((row.request_key, row.keyword), []).append(row)

        latest_per_term: Dict[str, tuple] = {}
        for (key, term), rows in series.items():
            collected = max(_aware(r.observed_at) for r in rows if r.observed_at)
            if term.lower() not in latest_per_term or collected > latest_per_term[term.lower()][0]:
                latest_per_term[term.lower()] = (collected, key, term, rows)

        out = []
        for collected, key, term, rows in latest_per_term.values():
            rows = sorted((r for r in rows if not r.partial and r.point_at),
                          key=lambda r: _aware(r.point_at))
            change = relative_change([r.interest_value for r in rows])
            if change is None or change < RISING_INTEREST_MIN_PERCENT:
                continue
            region = rows[0].region or "worldwide"
            breakdown = score({
                "impact": round(min(change / 100.0, 1.0), 4),
                # One request is one measurement series from one source.
                "confidence": round(0.5 * CONFIDENCE_VALUE["medium"]
                                    + 0.5 * min(len(rows) / 4.0, 1.0), 4),
                "freshness": freshness(collected, now), "relevance": 0.7})
            out.append({
                "fingerprint": "rising_search_interest|" + term.lower() + "|" + region,
                "title": "Relative search interest in '" + term + "' rose "
                + str(change) + "% (" + region + ", " + (rows[0].timeframe or "") + ")",
                "category": "rising_search_interest", "market": term, "location": region,
                "product": None, "merchant_id": None, "confidence": "medium",
                "relevance_note": "Market-wide signal; Google Trends interest is relative, "
                                  "not search volume or sales.",
                "suggested_action": "Check related queries and news for what is driving "
                                    "the interest before acting on it.",
                "evidence_observed_at": collected, "breakdown": breakdown,
                "evidence": {"record_ids": [r.id for r in rows], "source_urls": [],
                             "explanation": "Mean of the last quarter of points vs the "
                             "first quarter, request " + key + ".",
                             "source": "google_trends"},
            })
        return out

    # ------------------------------------------------------------------
    def sources(self, market: Optional[str] = None,
                location: Optional[str] = None) -> Dict[str, Any]:
        """What evidence exists for each opportunity source, and what it yields.

        Lets the page explain *why* there are (or are not) opportunities and
        which module collects the missing evidence. Reads only; free.
        """
        alerts = PriceChangeService(self.db).detect(market=market, location=location)
        by_type: Dict[str, int] = {}
        for a in alerts.alerts:
            by_type[a.type] = by_type.get(a.type, 0) + 1

        query = self.db.query(ProductObservation).filter(
            ProductObservation.price_status == "verified",
            ProductObservation.price.isnot(None))
        if market:
            query = query.filter(ProductObservation.market == market)
        if location:
            query = query.filter(ProductObservation.location_resolved == location)
        runs: Dict[tuple, set] = {}
        for row in query.all():
            if row.observed_at is None:
                continue
            key = (row.normalized_query, row.market, row.location_resolved)
            runs.setdefault(key, set()).add(_aware(row.observed_at).replace(microsecond=0))

        interest = [c for c in self._interest_candidates(market, datetime.now(timezone.utc))]
        interest_requests = self.db.query(TrendObservation.request_key).filter(
            TrendObservation.request_key.isnot(None),
            TrendObservation.data_type == "TIMESERIES").distinct().count()

        active = self.db.query(Opportunity).filter(Opportunity.status != "dismissed")
        if market:
            active = active.filter(Opportunity.market == market)
        if location:
            active = active.filter(Opportunity.location == location)
        categories: Dict[str, int] = {}
        for o in active.all():
            categories[o.category] = categories.get(o.category, 0) + 1
        last = self.db.query(Opportunity.updated_at).order_by(
            Opportunity.updated_at.desc()).first()

        return {
            "price_evidence": {
                "verified_prices": query.count(),
                "products_tracked": len(runs),
                "products_with_history": sum(1 for r in runs.values() if len(r) >= 2),
                "signals": {
                    "price_moves": by_type.get("price_increase", 0) + by_type.get("price_decrease", 0),
                    "price_gaps": by_type.get("price_dispersion", 0),
                    "new_offers": by_type.get("new_offer", 0),
                },
            },
            "search_interest": {
                "comparisons_collected": interest_requests,
                "rising_terms": len(interest),
            },
            "active_by_category": categories,
            "last_refreshed_at": last[0] if last else None,
        }

    # ------------------------------------------------------------------
    def list(self, status: Optional[str] = None, market: Optional[str] = None,
             location: Optional[str] = None, min_score: Optional[float] = None,
             limit: int = 100) -> List[Opportunity]:
        query = self.db.query(Opportunity)
        if status:
            query = query.filter(Opportunity.status == status)
        else:
            query = query.filter(Opportunity.status != "dismissed")
        if market:
            query = query.filter(Opportunity.market == market)
        if location:
            query = query.filter(Opportunity.location == location)
        if min_score is not None:
            query = query.filter(Opportunity.score >= min_score)
        return query.order_by(Opportunity.score.desc(), Opportunity.id).limit(limit).all()

    def update(self, opportunity_id: int, status: Optional[str] = None,
               note: Optional[str] = None) -> Optional[Opportunity]:
        row = self.db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
        if row is None:
            return None
        changes = {}
        if status is not None:
            if status not in STATUSES:
                raise ValueError("status must be one of: " + ", ".join(sorted(STATUSES)) + ".")
            if status != row.status:
                changes["status"] = [row.status, status]
                row.status = status
        if note is not None and (note.strip() or None) != row.note:
            changes["note"] = [row.note, note.strip() or None]
            row.note = note.strip() or None
        if changes:
            row.updated_at = datetime.now(timezone.utc)
            self.db.add(AuditEvent(entity_type="opportunity", entity_id=row.id,
                                   action="review_updated", detail=json.dumps(changes)))
            self.db.commit()
        return row


def to_dict(row: Opportunity) -> Dict[str, Any]:
    return {
        "id": row.id, "title": row.title, "category": row.category,
        "market": row.market, "location": row.location, "product": row.product,
        "merchant_id": row.merchant_id, "score": row.score,
        "breakdown": json.loads(row.breakdown or "{}"),
        "evidence": json.loads(row.evidence or "{}"), "confidence": row.confidence,
        "relevance_note": row.relevance_note, "suggested_action": row.suggested_action,
        "status": row.status, "note": row.note, "created_at": row.created_at,
        "updated_at": row.updated_at, "evidence_observed_at": row.evidence_observed_at,
    }
