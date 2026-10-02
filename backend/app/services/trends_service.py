"""Trends: what the observation history already shows.

Derived, never authoritative. Every figure here is computed on read from
observations that Competitors and Products already stored; this module writes
nothing, normalises nothing and deletes nothing. The observation tables remain
the source of truth, and a trend is only ever a reading of them.

It also makes no provider request, so it costs no SerpApi credit.

The one thing that makes this honest
------------------------------------
Re-running a search inside the response cache window (7 days) returns
byte-identical data, and each run stores its own observation row. Three rows
can therefore describe **one** measurement. Counting them as three samples
would manufacture a history that was never observed -- and, worse, report a
value as "stable" when all we did was read the same cached response again.

So consecutive observations carrying an identical value collapse into a single
point, and a direction is claimed only when two or more *distinct* points
exist. One measurement seen repeatedly is ``insufficient_history``, never
``flat``.

Comparability
-------------
Series are never merged across contexts. A merchant's position in one market
and location is not comparable with another's, and a product's price at one
merchant is not comparable with another merchant's. A "change" computed across
two different requests is an artefact of the request, not a market movement.
"""
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.competitor import CompetitorObservation
from app.models.merchant import Merchant
from app.models.product_observation import ProductObservation
from app.services.product_identity import canonicalise
from app.schemas.trend import (
    ContextSummary, MerchantPresence, MerchantPresenceResponse,
    TrendListResponse, TrendPoint, TrendSeriesModel, TrendSummaryResponse,
)

# Recorded by Products when the merchant lookup itself failed.
PROVIDER_FAILED = "provider_request_failed"

TREND = "trend"
INSUFFICIENT = "insufficient_history"
NO_DATA = "no_data"

UP = "up"
DOWN = "down"
FLAT = "flat"

# Metrics where a smaller number is an improvement, so "down" is not a decline.
LOWER_IS_BETTER = {"position"}


def _aware(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; comparisons need one convention."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def collapse(observations: List[Tuple[datetime, Optional[float], Optional[str]]]
             ) -> List[TrendPoint]:
    """Consecutive identical readings become one point.

    This is the whole defence against reading a cached response twice and
    calling it a trend. Order is oldest first.
    """
    points: List[TrendPoint] = []
    for observed_at, value, label in sorted(observations, key=lambda o: o[0]):
        if points and points[-1].value == value and points[-1].label == label:
            # Same reading as the point before it: the same measurement seen
            # again, not a new one.
            points[-1].observation_count += 1
            points[-1].observed_at = observed_at
            continue
        points.append(TrendPoint(value=value, label=label,
                                 observed_at=observed_at, observation_count=1))
    return points


def build_series(subject: str, metric: str, context: Optional[str],
                 observations: List[Tuple[datetime, Optional[float], Optional[str]]],
                 subject_id: Optional[int] = None) -> TrendSeriesModel:
    """A series, with a direction only when the evidence supports one."""
    raw = len(observations)
    if raw == 0:
        return TrendSeriesModel(
            subject=subject, subject_id=subject_id, metric=metric,
            context=context, status=NO_DATA,
            detail="no observations recorded for this metric")

    points = collapse(observations)
    series = TrendSeriesModel(
        subject=subject, subject_id=subject_id, metric=metric, context=context,
        raw_observations=raw, distinct_points=len(points), points=points,
        first_observed_at=points[0].observed_at,
        last_observed_at=points[-1].observed_at)

    span = (_aware(points[-1].observed_at) - _aware(points[0].observed_at))
    series.observation_span_hours = round(span.total_seconds() / 3600.0, 2)

    if len(points) < 2:
        series.status = INSUFFICIENT
        series.detail = (
            "one distinct measurement across " + str(raw) + " observation"
            + ("s" if raw != 1 else "")
            + "; a repeated reading is not a trend")
        series.first_value = points[0].value
        series.last_value = points[0].value
        return series

    first, last = points[0].value, points[-1].value
    series.status = TREND
    series.first_value = first
    series.last_value = last

    if first is None or last is None:
        series.direction = "unknown"
        series.detail = "a measurement had no comparable value"
        return series

    series.change_absolute = round(last - first, 4)
    if first:
        series.change_percent = round((last - first) / abs(first) * 100.0, 2)

    if last > first:
        series.direction = UP
    elif last < first:
        series.direction = DOWN
    else:
        # Genuinely flat: two or more distinct measurements that agreed.
        series.direction = FLAT
    return series


class TrendsService:
    """Read-only derivation over the observation history."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    def summary(self) -> TrendSummaryResponse:
        """What history exists, and what can honestly be compared."""
        competitor_rows = self.db.query(CompetitorObservation).all()
        product_rows = self.db.query(ProductObservation).all()

        contexts = self._contexts(competitor_rows, product_rows)
        analyzable = [c for c in contexts if c.analyzable]

        # A context searched twice is a *precondition* for a trend, not a
        # trend. If both searches were served from cache the readings are
        # identical, so nothing was actually measured twice. Only a series
        # that reached "trend" proves something is comparable, so that is what
        # insufficient_history reports -- otherwise the summary would promise
        # movement the signal tabs cannot show.
        measurable = sum(
            result.analyzable for result in (
                self.price_trends(), self.availability_trends(),
                self.visibility_trends(metric="position"),
                self.visibility_trends(metric="rating")))

        response = TrendSummaryResponse(
            generated_at=datetime.now(timezone.utc),
            competitor_observations=len(competitor_rows),
            product_observations=len(product_rows),
            merchants_tracked=self.db.query(Merchant).count(),
            verified_price_observations=sum(
                1 for r in product_rows if r.price_status == "verified"),
            contexts=contexts,
            analyzable_contexts=len(analyzable),
            insufficient_history=measurable == 0)

        if not contexts:
            response.detail = (
                "No observations have been recorded yet. Run a Competitors or "
                "Products search to begin building history.")
        elif measurable == 0:
            response.detail = (
                "History exists, but nothing has been measured twice yet. "
                + (str(len(analyzable)) + " context(s) have been searched more "
                   "than once, but the repeat searches were served from the "
                   "7-day response cache and returned identical readings. "
                   if analyzable else "")
                + "A second measurement requires a later search once the cache "
                "expires, or a different market, location or product.")
        return response

    def _contexts(self, competitor_rows, product_rows) -> List[ContextSummary]:
        buckets: Dict[Tuple, List] = {}
        for row in competitor_rows:
            buckets.setdefault(
                ("competitors", row.market, row.location_resolved), []).append(row)
        for row in product_rows:
            buckets.setdefault(
                ("products", row.market, row.location_resolved), []).append(row)

        out: List[ContextSummary] = []
        for (source, market, location), rows in sorted(
                buckets.items(), key=lambda kv: (kv[0][0], kv[0][1] or "", kv[0][2] or "")):
            times = sorted(_aware(r.observed_at) for r in rows if r.observed_at)
            # Observations written by one search share a timestamp to the
            # second; distinct timestamps approximate distinct searches.
            distinct_searches = len({t.replace(microsecond=0) for t in times})
            summary = ContextSummary(
                market=market, location=location, source=source,
                merchants=len({r.merchant_id for r in rows if r.merchant_id}),
                observations=len(rows), distinct_searches=distinct_searches,
                first_observed_at=times[0] if times else None,
                last_observed_at=times[-1] if times else None)
            if times:
                summary.span_hours = round(
                    (times[-1] - times[0]).total_seconds() / 3600.0, 2)
            summary.analyzable = distinct_searches >= 2
            if not summary.analyzable:
                summary.detail = "only one search recorded for this context"
            out.append(summary)
        return out

    # ------------------------------------------------------------------
    def _product_query(self, product_query: Optional[str], market: Optional[str],
                       location: Optional[str]):
        query = self.db.query(ProductObservation)
        if product_query:
            query = query.filter(
                ProductObservation.normalized_query == canonicalise(product_query))
        if market:
            query = query.filter(ProductObservation.market == market)
        if location:
            query = query.filter(ProductObservation.location_resolved == location)
        return query

    def _product_context(self, row) -> Optional[str]:
        """Merchant plus the market and place the observation was made in."""
        return " / ".join(p for p in (self._merchant_name(row.merchant_id),
                                      row.market, row.location_resolved) if p) or None

    def price_trends(self, product_query: Optional[str] = None,
                     market: Optional[str] = None,
                     location: Optional[str] = None) -> TrendListResponse:
        """Verified prices only, per product, merchant, market and place.

        An unverified price was never established as this product's price, so
        including it would make a movement out of an uncertainty. A merchant
        identified by domain spans locations, so the place is part of the
        series key: one chain's prices in two cities are two series, not one.
        """
        query = self._product_query(product_query, market, location).filter(
            ProductObservation.price_status == "verified",
            ProductObservation.price.isnot(None))

        return self._series_from(
            rows=query.all(),
            key=lambda r: (r.normalized_query, r.merchant_id, r.market,
                           r.location_resolved),
            metric="price",
            value=lambda r: r.price,
            label=lambda r: r.observed_size,
            subject=lambda r: r.product_name or r.product_query,
            subject_id=lambda r: r.merchant_id,
            context=self._product_context,
            empty_detail="No verified price observations have been recorded yet.")

    def availability_trends(self, product_query: Optional[str] = None,
                            market: Optional[str] = None,
                            location: Optional[str] = None) -> TrendListResponse:
        """How a product's status at a merchant moved over time.

        A failed provider lookup is not a reading of the merchant at all, so
        it is excluded rather than shown as a move from "found" to "unknown".
        """
        query = self._product_query(product_query, market, location).filter(
            (ProductObservation.verification_reason.is_(None))
            | (ProductObservation.verification_reason != PROVIDER_FAILED))

        return self._series_from(
            rows=query.all(),
            key=lambda r: (r.normalized_query, r.merchant_id, r.market,
                           r.location_resolved),
            metric="availability",
            # Ordinal only so a change is detectable; it is not a score and is
            # never presented as one.
            value=lambda r: {"found": 1.0, "unknown": 0.0,
                             "not_found": -1.0}.get(r.product_status),
            label=lambda r: r.product_status,
            subject=lambda r: r.product_name or r.product_query,
            subject_id=lambda r: r.merchant_id,
            context=self._product_context,
            empty_detail="No product observations have been recorded yet.")

    def visibility_trends(self, market: Optional[str] = None,
                          metric: str = "position",
                          location: Optional[str] = None) -> TrendListResponse:
        """Merchant search position, rating or review count over time."""
        if metric not in ("position", "rating", "reviews"):
            raise ValueError("metric must be position, rating or reviews")

        query = self.db.query(CompetitorObservation)
        if market:
            query = query.filter(CompetitorObservation.market == market)
        if location:
            query = query.filter(CompetitorObservation.location_resolved == location)
        rows = [r for r in query.all() if getattr(r, metric) is not None]

        return self._series_from(
            rows=rows,
            key=lambda r: (r.merchant_id, r.market, r.location_resolved),
            metric=metric,
            value=lambda r: float(getattr(r, metric)),
            label=lambda r: None,
            subject=lambda r: self._merchant_name(r.merchant_id) or "Unknown merchant",
            subject_id=lambda r: r.merchant_id,
            context=lambda r: " / ".join(
                p for p in (r.market, r.location_resolved) if p) or None,
            empty_detail="No competitor observations carry this metric yet.")

    # ------------------------------------------------------------------
    def _series_from(self, rows: Iterable, key: Callable, metric: str,
                     value: Callable, label: Callable, subject: Callable,
                     subject_id: Callable, context: Callable,
                     empty_detail: str) -> TrendListResponse:
        grouped: Dict[Tuple, List] = {}
        for row in rows:
            grouped.setdefault(key(row), []).append(row)

        series: List[TrendSeriesModel] = []
        for group in grouped.values():
            group.sort(key=lambda r: _aware(r.observed_at))
            newest = group[-1]
            series.append(build_series(
                subject=subject(newest), metric=metric, context=context(newest),
                subject_id=subject_id(newest),
                observations=[(_aware(r.observed_at), value(r), label(r))
                              for r in group]))

        # Something that moved is more interesting than something that could
        # not be assessed, so assessable series come first.
        order = {TREND: 0, INSUFFICIENT: 1, NO_DATA: 2}
        series.sort(key=lambda s: (order.get(s.status, 9), s.subject.lower()))

        response = TrendListResponse(
            generated_at=datetime.now(timezone.utc),
            total=len(series),
            analyzable=sum(1 for s in series if s.status == TREND),
            insufficient_history=sum(1 for s in series if s.status == INSUFFICIENT),
            series=series)
        if not series:
            response.detail = empty_detail
        elif response.analyzable == 0:
            response.detail = (
                "Every series holds a single distinct measurement. Repeating a "
                "search inside the 7-day response cache returns identical data, "
                "so nothing has yet been measured twice.")
        return response

    # ------------------------------------------------------------------
    def merchant_presence(self, market: Optional[str] = None,
                          location: Optional[str] = None) -> MerchantPresenceResponse:
        """When each business was first and last seen in a context."""
        query = self.db.query(CompetitorObservation)
        if market:
            query = query.filter(CompetitorObservation.market == market)
        if location:
            query = query.filter(CompetitorObservation.location_resolved == location)
        rows = query.all()

        grouped: Dict[Tuple, List] = {}
        for row in rows:
            grouped.setdefault(
                (row.merchant_id, row.market, row.location_resolved), []).append(row)

        # The newest search per context, so "still present" means something.
        latest_per_context: Dict[Tuple, datetime] = {}
        for row in rows:
            ctx = (row.market, row.location_resolved)
            observed = _aware(row.observed_at)
            if observed and (ctx not in latest_per_context
                             or observed > latest_per_context[ctx]):
                latest_per_context[ctx] = observed

        merchants: List[MerchantPresence] = []
        for (merchant_id, market_name, location_name), group in grouped.items():
            times = sorted(_aware(r.observed_at) for r in group if r.observed_at)
            if not times:
                continue
            merchant = self.db.query(Merchant).filter(
                Merchant.id == merchant_id).first() if merchant_id else None
            latest = latest_per_context.get((market_name, location_name))
            merchants.append(MerchantPresence(
                merchant=merchant.name if merchant else "Unknown merchant",
                merchant_id=merchant_id,
                domain=merchant.normalized_domain if merchant else None,
                market=market_name, location=location_name,
                status=(merchant.status if merchant else "unknown") or "unknown",
                first_seen_at=times[0], last_seen_at=times[-1],
                observation_count=len(group),
                distinct_searches=len({t.replace(microsecond=0) for t in times}),
                present_in_latest=bool(latest and times[-1] >= latest)))

        merchants.sort(key=lambda m: (m.market or "", m.merchant.lower()))
        response = MerchantPresenceResponse(
            generated_at=datetime.now(timezone.utc),
            total=len(merchants),
            contexts=self._contexts(rows, []),
            merchants=merchants)
        if not merchants:
            response.detail = "No competitor observations have been recorded yet."
        return response

    # ------------------------------------------------------------------
    def _merchant_name(self, merchant_id: Optional[int]) -> Optional[str]:
        if not merchant_id:
            return None
        merchant = self.db.query(Merchant).filter(Merchant.id == merchant_id).first()
        return merchant.name if merchant else None
