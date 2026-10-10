"""Price change detection over stored, verified observations.

Read-only and free: it reads ``product_observations`` and makes no provider
request. Every alert is computed from rows that exist and cites them.

The rules that keep it honest are the ones Trends already follows:

* Only verified prices are read. An unverified figure was never established
  as this product's price, so a "change" built from one would be an artefact.
* A context is one product query in one market and one resolved location, and
  a series is one merchant within it, in one currency. Nothing is compared
  across those boundaries.
* Consecutive identical readings collapse into one measurement. Re-running a
  search inside the response cache window returns the same data; seeing it
  twice is not a second measurement, so it can never produce or hide a change.
* A *run* is the set of rows one search wrote, identified by their timestamp
  to the second -- the same approximation Trends uses.
* Absence is reported as absence ("not observed in the latest run"), never as
  "out of stock" or "discontinued".
"""
from datetime import datetime, timezone
from statistics import median
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models.merchant import Merchant
from app.models.product_observation import ProductObservation
from app.schemas.price_change import (
    PriceAlert, PriceAlertResponse, PriceAlertThresholds,
)
from app.services.product_identity import canonicalise
from app.services.trends_service import _aware


def _run_key(row) -> datetime:
    return _aware(row.observed_at).replace(microsecond=0)


def _pct(old: float, new: float) -> Optional[float]:
    return round((new - old) / abs(old) * 100.0, 2) if old else None


class PriceChangeService:
    def __init__(self, db: Session):
        self.db = db
        self._names: Dict[int, str] = {}

    def detect(self, product_query: Optional[str] = None, market: Optional[str] = None,
               location: Optional[str] = None,
               min_change_percent: Optional[float] = None,
               outlier_mad_k: Optional[float] = None,
               dispersion_min_percent: Optional[float] = None) -> PriceAlertResponse:
        thresholds = PriceAlertThresholds(
            min_change_percent=settings.PRICE_CHANGE_MIN_PERCENT
            if min_change_percent is None else min_change_percent,
            outlier_mad_k=settings.PRICE_OUTLIER_MAD_K
            if outlier_mad_k is None else outlier_mad_k,
            dispersion_min_percent=settings.PRICE_DISPERSION_MIN_PERCENT
            if dispersion_min_percent is None else dispersion_min_percent,
            min_merchants_for_outliers=settings.PRICE_OUTLIER_MIN_MERCHANTS)

        query = self.db.query(ProductObservation).filter(
            ProductObservation.price_status == "verified",
            ProductObservation.price.isnot(None),
            ProductObservation.currency.isnot(None))
        if product_query:
            query = query.filter(
                ProductObservation.normalized_query == canonicalise(product_query))
        if market:
            query = query.filter(ProductObservation.market == market)
        if location:
            query = query.filter(ProductObservation.location_resolved == location)
        rows = [r for r in query.all() if r.observed_at is not None]

        contexts: Dict[Tuple, List] = {}
        for row in rows:
            contexts.setdefault(
                (row.normalized_query, row.market, row.location_resolved), []).append(row)

        alerts: List[PriceAlert] = []
        for ctx_rows in contexts.values():
            alerts.extend(self._context_alerts(ctx_rows, thresholds))

        order = {"warning": 0, "info": 1}
        alerts.sort(key=lambda a: (order.get(a.severity, 9),
                                   -(abs(a.change_percent or 0)),
                                   a.product.lower(), (a.merchant or "").lower()))

        response = PriceAlertResponse(
            generated_at=datetime.now(timezone.utc), thresholds=thresholds,
            contexts_examined=len(contexts), verified_observations=len(rows),
            total=len(alerts), alerts=alerts)
        if not rows:
            response.detail = ("No verified price observations match this selection. "
                               "Run a Products or Price Intelligence search first.")
        elif not alerts:
            response.detail = ("No change met the thresholds. A change needs two distinct "
                               "verified readings at one merchant, in one market and "
                               "location; a repeated cached reading is not a second one.")
        return response

    # ------------------------------------------------------------------
    def _context_alerts(self, rows: List, t: PriceAlertThresholds) -> List[PriceAlert]:
        out: List[PriceAlert] = []
        sample = rows[0]
        product = sample.product_query or sample.normalized_query or "product"
        runs = sorted({_run_key(r) for r in rows})
        latest_run = runs[-1]

        series: Dict[Tuple, List] = {}
        for row in rows:
            series.setdefault((row.merchant_id, row.currency), []).append(row)

        base = dict(product=product, market=sample.market,
                    location=sample.location_resolved)

        for (merchant_id, currency), group in series.items():
            group.sort(key=lambda r: _aware(r.observed_at))
            merchant = self._merchant(merchant_id)

            # Same run, different verified prices: the evidence disagrees.
            by_run: Dict[datetime, List] = {}
            for row in group:
                by_run.setdefault(_run_key(row), []).append(row)
            for run, run_rows in by_run.items():
                prices = sorted({r.price for r in run_rows})
                if len(prices) > 1:
                    out.append(PriceAlert(
                        type="conflicting_prices", severity="warning", confidence="medium",
                        merchant=merchant, merchant_id=merchant_id, currency=currency,
                        previous_price=prices[0], current_price=prices[-1],
                        observed_at=run,
                        explanation=(merchant or "This merchant") + " was observed at "
                        + str(len(prices)) + " different verified prices in one run. "
                        "Check the sources before relying on either.",
                        record_ids=[r.id for r in run_rows],
                        source_urls=_urls(run_rows), **base))

            # Collapse consecutive identical readings into measurements.
            points: List[List] = []
            for row in group:
                if points and points[-1][0].price == row.price:
                    points[-1].append(row)
                else:
                    points.append([row])

            if len(points) >= 2:
                prev, cur = points[-2][-1], points[-1][-1]
                pct = _pct(prev.price, cur.price)
                if pct is not None and abs(pct) >= t.min_change_percent:
                    up = cur.price > prev.price
                    out.append(PriceAlert(
                        type="price_increase" if up else "price_decrease",
                        severity="warning" if abs(pct) >= 2 * t.min_change_percent else "info",
                        confidence="high" if prev.source_type == cur.source_type else "medium",
                        merchant=merchant, merchant_id=merchant_id, currency=currency,
                        previous_price=prev.price, current_price=cur.price,
                        change_absolute=round(cur.price - prev.price, 2),
                        change_percent=pct,
                        previous_observed_at=_aware(prev.observed_at),
                        observed_at=_aware(cur.observed_at),
                        explanation="Verified price moved from " + _fmt(prev.price, currency)
                        + " to " + _fmt(cur.price, currency) + " (" + ("+" if up else "")
                        + str(pct) + "%) between two distinct readings."
                        + ("" if prev.source_type == cur.source_type else
                           " The readings came from different source types."),
                        record_ids=[prev.id, cur.id], source_urls=_urls([prev, cur]),
                        **base))

            if len(runs) >= 2:
                seen_runs = {_run_key(r) for r in group}
                first, last = group[0], group[-1]
                if min(seen_runs) == latest_run:
                    out.append(PriceAlert(
                        type="new_offer", severity="info", confidence="medium",
                        merchant=merchant, merchant_id=merchant_id, currency=currency,
                        current_price=first.price, observed_at=_aware(first.observed_at),
                        explanation=(merchant or "A merchant") + " was priced for the first "
                        "time in the latest run of this market and location.",
                        record_ids=[first.id], source_urls=_urls([first]), **base))
                elif latest_run not in seen_runs:
                    out.append(PriceAlert(
                        type="not_observed_in_latest", severity="info", confidence="low",
                        merchant=merchant, merchant_id=merchant_id, currency=currency,
                        previous_price=last.price,
                        previous_observed_at=_aware(last.observed_at),
                        explanation="No verified price from " + (merchant or "this merchant")
                        + " in the latest run. Absence from one search is not proof the "
                        "offer ended or the product is out of stock.",
                        record_ids=[last.id], source_urls=_urls([last]), **base))

        out.extend(self._latest_run_alerts(rows, latest_run, t, base))
        return out

    def _latest_run_alerts(self, rows, latest_run, t, base) -> List[PriceAlert]:
        """Cross-merchant tests on the latest run, per currency."""
        out: List[PriceAlert] = []
        latest = [r for r in rows if _run_key(r) == latest_run]
        by_currency: Dict[str, Dict[int, object]] = {}
        for row in latest:
            # One price per merchant: the lowest verified one in this run.
            current = by_currency.setdefault(row.currency, {}).get(row.merchant_id)
            if current is None or row.price < current.price:
                by_currency[row.currency][row.merchant_id] = row

        for currency, per_merchant in by_currency.items():
            offers = list(per_merchant.values())
            prices = [o.price for o in offers]
            if len(offers) >= 2 and min(prices) > 0:
                spread = round((max(prices) / min(prices) - 1) * 100.0, 2)
                if spread >= t.dispersion_min_percent:
                    low = min(offers, key=lambda o: o.price)
                    high = max(offers, key=lambda o: o.price)
                    out.append(PriceAlert(
                        type="price_dispersion", severity="info", confidence="medium",
                        currency=currency, previous_price=low.price, current_price=high.price,
                        change_percent=spread, observed_at=latest_run,
                        explanation="Latest verified prices range from "
                        + _fmt(low.price, currency) + " (" + (self._merchant(low.merchant_id) or "?")
                        + ") to " + _fmt(high.price, currency) + " ("
                        + (self._merchant(high.merchant_id) or "?") + "), a "
                        + str(spread) + "% spread. Sizes or variants may differ; "
                        "compare the sources.",
                        record_ids=[o.id for o in offers], source_urls=_urls(offers), **base))

            if len(offers) >= t.min_merchants_for_outliers:
                mid = median(prices)
                mad = median(abs(p - mid) for p in prices)
                if mad > 0:
                    for offer in offers:
                        score = 0.6745 * (offer.price - mid) / mad
                        if abs(score) >= t.outlier_mad_k:
                            name = self._merchant(offer.merchant_id)
                            out.append(PriceAlert(
                                type="outlier", severity="warning", confidence="medium",
                                merchant=name, merchant_id=offer.merchant_id,
                                currency=currency, current_price=offer.price,
                                change_percent=_pct(mid, offer.price),
                                observed_at=_aware(offer.observed_at),
                                explanation=(name or "A merchant") + "'s price "
                                + _fmt(offer.price, currency) + " is far from the median "
                                + _fmt(mid, currency) + " of " + str(len(offers))
                                + " merchants (robust z = " + str(round(score, 1))
                                + "). It may be a different size, a bundle or an error.",
                                record_ids=[offer.id], source_urls=_urls([offer]), **base))
        return out

    def _merchant(self, merchant_id: Optional[int]) -> Optional[str]:
        if not merchant_id:
            return None
        if merchant_id not in self._names:
            m = self.db.query(Merchant).filter(Merchant.id == merchant_id).first()
            self._names[merchant_id] = m.name if m else None
        return self._names[merchant_id]


def _fmt(value: float, currency: Optional[str]) -> str:
    return ("%.2f" % value) + (" " + currency if currency else "")


def _urls(rows) -> List[str]:
    out: List[str] = []
    for r in rows:
        if r.source_url and r.source_url not in out:
            out.append(r.source_url)
    return out
