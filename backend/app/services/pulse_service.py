"""Market Pulse: a factual snapshot of one market and location.

Strictly a read-only analytical layer over data the other modules produced:

    Competitor discovery -> Product discovery -> observations -> Trends -> Pulse

It performs no discovery of its own. It resolves no locations, identifies no
merchants, matches no products and makes no provider request, so it can never
spend a SerpApi credit. It writes nothing.

What it does is assemble, for one market and place, what was observed and how
strongly it is evidenced. It states no conclusions. There is deliberately no
notion here of a market "growing", a competitor "winning", demand being "high",
or a business having "disappeared" -- each of those is an inference the
evidence does not support, and the counters and statuses are reported instead.

Two rules carried over verbatim from the layers beneath:

* A single measurement read repeatedly is not a trend, and not a sample. Trend
  direction comes from ``TrendsService``, which already collapses identical
  consecutive readings; price statistics apply the same test before averaging
  anything.
* Absence is not proof of absence. A merchant missing from the latest search is
  flagged as such, with the reason stated in full, never as a closure.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.competitor import CompetitorObservation
from app.models.merchant import Merchant
from app.models.product_observation import ProductObservation
from app.schemas.pulse import (
    CompetitorEntry, DataQuality, MarketContext, MarketOption,
    MarketPulseOptionsResponse, MarketPulseResponse, PriceEntry,
    PriceStatistics, ProductEntry, VisibilityEntry,
)
from app.services.trends_service import TrendsService, _aware, collapse

# Fewest distinct price measurements before an average describes anything.
# Below this, the figures are listed individually instead.
MIN_PRICES_FOR_STATISTICS = 2

PRESENT_NOTE = "Present in the latest observation of this market and location."
ABSENT_NOTE = (
    "Not present in the latest observation of this market and location. "
    "Absence from one search is not proof the business has closed or left the "
    "market -- a later search may simply have returned a different slice of "
    "results.")


class MarketPulseService:
    """Read-only. Every method derives; none of them writes."""

    def __init__(self, db: Session, trends: Optional[TrendsService] = None):
        self.db = db
        self.trends = trends or TrendsService(db=db)

    # ------------------------------------------------------------------
    def options(self) -> MarketPulseOptionsResponse:
        """Markets and locations actually present in the history.

        Offered so a selection always refers to something observed; no market
        category is invented.
        """
        buckets: Dict[Tuple[Optional[str], Optional[str]], Dict] = {}

        def bucket(market, location):
            return buckets.setdefault((market, location), {
                "competitor": 0, "product": 0, "merchants": set(), "times": []})

        for row in self.db.query(CompetitorObservation).all():
            entry = bucket(row.market, row.location_resolved)
            entry["competitor"] += 1
            if row.merchant_id:
                entry["merchants"].add(row.merchant_id)
            if row.observed_at:
                entry["times"].append(_aware(row.observed_at))
        for row in self.db.query(ProductObservation).all():
            entry = bucket(row.market, row.location_resolved)
            entry["product"] += 1
            if row.merchant_id:
                entry["merchants"].add(row.merchant_id)
            if row.observed_at:
                entry["times"].append(_aware(row.observed_at))

        options = []
        for (market, location), entry in buckets.items():
            times = sorted(entry["times"])
            options.append(MarketOption(
                market=market, location=location,
                competitor_observations=entry["competitor"],
                product_observations=entry["product"],
                merchants=len(entry["merchants"]),
                first_observed_at=times[0] if times else None,
                last_observed_at=times[-1] if times else None))

        options.sort(key=lambda o: (o.market or "", o.location or ""))
        response = MarketPulseOptionsResponse(
            generated_at=datetime.now(timezone.utc),
            total=len(options), options=options)
        if not options:
            response.detail = (
                "No observations have been recorded yet. Run a Competitors or "
                "Products search to build the history Market Pulse reads.")
        return response

    # ------------------------------------------------------------------
    def snapshot(self, market: Optional[str] = None,
                 location: Optional[str] = None) -> MarketPulseResponse:
        """Everything observed for one market and location.

        Both filters are applied to every section, so a snapshot can never mix
        one market's competitors with another's products.
        """
        market = (market or "").strip() or None
        location = (location or "").strip() or None

        competitor_rows = self._competitor_rows(market, location)
        product_rows = self._product_rows(market, location)

        context = self._context(market, location, competitor_rows, product_rows)
        competitors = self._competitors(competitor_rows)
        products = self._products(product_rows)
        prices = self._prices(product_rows)
        statistics = self._price_statistics(product_rows)
        visibility = self._visibility(competitor_rows)
        trends = self._trends(market, location)

        response = MarketPulseResponse(
            generated_at=datetime.now(timezone.utc),
            context=context, competitors=competitors, products=products,
            prices=prices, price_statistics=statistics, visibility=visibility,
            trends=trends,
            data_quality=self._data_quality(competitors, products, trends),
            has_data=bool(competitor_rows or product_rows))

        if not response.has_data:
            response.detail = (
                "No observations match this market and location. Run a "
                "Competitors or Products search for it to build history."
                if (market or location) else
                "No observations have been recorded yet.")
        return response

    # ------------------------------------------------------------------
    def _competitor_rows(self, market, location) -> List[CompetitorObservation]:
        query = self.db.query(CompetitorObservation)
        if market:
            query = query.filter(CompetitorObservation.market == market)
        if location:
            query = query.filter(CompetitorObservation.location_resolved == location)
        return query.all()

    def _product_rows(self, market, location) -> List[ProductObservation]:
        query = self.db.query(ProductObservation)
        if market:
            query = query.filter(ProductObservation.market == market)
        if location:
            query = query.filter(ProductObservation.location_resolved == location)
        return query.all()

    # ------------------------------------------------------------------
    def _context(self, market, location, competitor_rows, product_rows) -> MarketContext:
        times = sorted(_aware(r.observed_at)
                       for r in list(competitor_rows) + list(product_rows)
                       if r.observed_at)
        merchants = {r.merchant_id for r in list(competitor_rows) + list(product_rows)
                     if r.merchant_id}
        context = MarketContext(
            market=market, location=location,
            merchants=len(merchants),
            competitor_observations=len(competitor_rows),
            product_observations=len(product_rows),
            first_observed_at=times[0] if times else None,
            last_observed_at=times[-1] if times else None,
            distinct_searches=len({t.replace(microsecond=0) for t in times}))
        if times:
            context.observation_span_hours = round(
                (times[-1] - times[0]).total_seconds() / 3600.0, 2)
        return context

    # ------------------------------------------------------------------
    def _competitors(self, rows: List[CompetitorObservation]) -> List[CompetitorEntry]:
        grouped: Dict[int, List[CompetitorObservation]] = {}
        for row in rows:
            if row.merchant_id:
                grouped.setdefault(row.merchant_id, []).append(row)

        # The newest observation across this context, so "present in latest"
        # compares like with like.
        all_times = [_aware(r.observed_at) for r in rows if r.observed_at]
        latest = max(all_times) if all_times else None

        entries: List[CompetitorEntry] = []
        for merchant_id, group in grouped.items():
            merchant = self.db.query(Merchant).filter(
                Merchant.id == merchant_id).first()
            if merchant is None:
                continue
            times = sorted(_aware(r.observed_at) for r in group if r.observed_at)
            present = bool(latest and times and times[-1] >= latest)
            entries.append(CompetitorEntry(
                merchant_id=merchant_id, name=merchant.name,
                domain=merchant.normalized_domain, website=merchant.website,
                address=merchant.address,
                status=merchant.status or "discovered",
                entity_type=merchant.entity_type or "unknown",
                discovery_sources=_ordered_unique(r.source_type for r in group),
                discovery_methods=_ordered_unique(r.discovery_method for r in group),
                first_seen_at=times[0] if times else None,
                last_seen_at=times[-1] if times else None,
                observation_count=len(group),
                distinct_searches=len({t.replace(microsecond=0) for t in times}),
                present_in_latest=present,
                presence_note=PRESENT_NOTE if present else ABSENT_NOTE,
                has_location_evidence=bool(
                    merchant.address or merchant.latitude is not None)))

        rank = {"verified": 0, "discovered": 1, "uncertain": 2, "rejected": 3}
        entries.sort(key=lambda e: (rank.get(e.status, 9), e.name.lower()))
        return entries

    # ------------------------------------------------------------------
    def _products(self, rows: List[ProductObservation]) -> List[ProductEntry]:
        entries = []
        for row in sorted(rows, key=lambda r: _aware(r.observed_at) or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
            merchant = self.db.query(Merchant).filter(
                Merchant.id == row.merchant_id).first() if row.merchant_id else None
            entries.append(ProductEntry(
                observation_id=row.id, merchant_id=row.merchant_id,
                merchant=merchant.name if merchant else None,
                merchant_domain=merchant.normalized_domain if merchant else None,
                product_query=row.product_query, product_name=row.product_name,
                observed_size=row.observed_size,
                size_confirmed=bool(row.size_confirmed),
                product_status=row.product_status or "unknown",
                price_status=row.price_status or "unknown",
                verification_reason=row.verification_reason,
                evidence_scope=row.evidence_scope or "catalog",
                inventory_confirmed=bool(row.inventory_confirmed),
                source_url=row.source_url, source_domain=row.source_domain,
                page_type=row.page_type, observed_at=row.observed_at))
        return entries

    # ------------------------------------------------------------------
    @staticmethod
    def _verified_price_rows(rows: List[ProductObservation]) -> List[ProductObservation]:
        """Verified prices only.

        An unverified price was never established as this product's price, so
        admitting it would turn an uncertainty into a market figure.
        """
        return [r for r in rows
                if r.price_status == "verified" and r.price is not None]

    def _prices(self, rows: List[ProductObservation]) -> List[PriceEntry]:
        entries = []
        for row in sorted(self._verified_price_rows(rows),
                          key=lambda r: (r.price, _aware(r.observed_at) or datetime.min.replace(tzinfo=timezone.utc))):
            merchant = self.db.query(Merchant).filter(
                Merchant.id == row.merchant_id).first() if row.merchant_id else None
            entries.append(PriceEntry(
                observation_id=row.id, merchant_id=row.merchant_id,
                merchant=merchant.name if merchant else None,
                product_name=row.product_name, product_query=row.product_query,
                observed_size=row.observed_size, price=row.price,
                currency=row.currency, source_url=row.source_url,
                source_domain=row.source_domain,
                evidence_scope=row.evidence_scope or "catalog",
                inventory_confirmed=bool(row.inventory_confirmed),
                observed_at=row.observed_at))
        return entries

    def _price_statistics(self, rows: List[ProductObservation]) -> PriceStatistics:
        """Aggregates only when enough distinct measurements exist.

        Distinct is the operative word. Re-running a search inside the response
        cache stores the same price again; averaging those repeats would report
        a sample of one as though it were a market rate.
        """
        verified = self._verified_price_rows(rows)
        stats = PriceStatistics()
        if not verified:
            stats.detail = "No verified price observations in this context."
            return stats

        # Distinct (merchant, product, price) readings, not raw rows.
        distinct = {(r.merchant_id, r.normalized_query, r.price) for r in verified}
        stats.distinct_measurements = len(distinct)
        stats.currency = next((r.currency for r in verified if r.currency), None)

        if len(distinct) < MIN_PRICES_FOR_STATISTICS:
            stats.detail = (
                str(len(distinct)) + " distinct verified price measurement from "
                + str(len(verified)) + " observation"
                + ("s" if len(verified) != 1 else "")
                + ". Too few to summarise; the individual prices are listed instead.")
            return stats

        values = sorted(price for _, _, price in distinct)
        stats.sufficient = True
        stats.lowest = values[0]
        stats.highest = values[-1]
        stats.average = round(sum(values) / len(values), 2)
        stats.detail = (
            "Across " + str(len(distinct)) + " distinct verified price "
            "measurements. These describe what was observed, not a market rate.")
        return stats

    # ------------------------------------------------------------------
    def _visibility(self, rows: List[CompetitorObservation]) -> List[VisibilityEntry]:
        grouped: Dict[int, List[CompetitorObservation]] = {}
        for row in rows:
            if row.merchant_id:
                grouped.setdefault(row.merchant_id, []).append(row)

        entries = []
        for merchant_id, group in grouped.items():
            merchant = self.db.query(Merchant).filter(
                Merchant.id == merchant_id).first()
            if merchant is None:
                continue
            group.sort(key=lambda r: _aware(r.observed_at) or datetime.min.replace(tzinfo=timezone.utc))
            newest = group[-1]
            positions = [r.position for r in group if r.position is not None]
            ratings = [r.rating for r in group if r.rating is not None]
            reviews = [r.reviews for r in group if r.reviews is not None]
            entries.append(VisibilityEntry(
                merchant_id=merchant_id, merchant=merchant.name,
                domain=merchant.normalized_domain,
                best_position=min(positions) if positions else None,
                latest_position=newest.position,
                rating=ratings[-1] if ratings else None,
                reviews=reviews[-1] if reviews else None,
                observed_at=newest.observed_at, observation_count=len(group)))

        entries.sort(key=lambda e: (
            e.best_position if e.best_position is not None else 9999,
            e.merchant.lower()))
        return entries

    # ------------------------------------------------------------------
    def _trends(self, market, location) -> List:
        """Trend semantics come from TrendsService unchanged.

        In particular it already collapses identical consecutive readings, so a
        repeatedly-read cached value arrives here as insufficient_history
        rather than as a direction.
        """
        # Every series is built from rows filtered by the same market *and*
        # location as the rest of the snapshot, compared exactly. Filtering
        # price series by market alone (and visibility by a substring of the
        # context text) once let another city's prices into this snapshot.
        series = []
        series.extend(self.trends.price_trends(
            market=market, location=location).series)
        series.extend(self.trends.visibility_trends(
            market=market, location=location, metric="position").series)
        series.extend(self.trends.visibility_trends(
            market=market, location=location, metric="rating").series)

        order = {"trend": 0, "insufficient_history": 1, "no_data": 2}
        series.sort(key=lambda s: (order.get(s.status, 9), s.metric, s.subject.lower()))
        return series

    # ------------------------------------------------------------------
    @staticmethod
    def _data_quality(competitors, products, trends) -> DataQuality:
        quality = DataQuality(
            competitors_verified=sum(1 for c in competitors if c.status == "verified"),
            competitors_discovered=sum(1 for c in competitors if c.status == "discovered"),
            competitors_uncertain=sum(1 for c in competitors if c.status == "uncertain"),
            products_found=sum(1 for p in products if p.product_status == "found"),
            products_not_found=sum(1 for p in products if p.product_status == "not_found"),
            products_unknown=sum(1 for p in products if p.product_status == "unknown"),
            prices_verified=sum(1 for p in products if p.price_status == "verified"),
            prices_unavailable=sum(1 for p in products if p.price_status == "unavailable"),
            prices_unknown=sum(1 for p in products if p.price_status == "unknown"),
            trend_series=len(trends),
            trend_series_with_direction=sum(1 for t in trends if t.status == "trend"),
            trend_series_insufficient_history=sum(
                1 for t in trends if t.status == "insufficient_history"))

        notes = []
        if quality.products_unknown:
            notes.append(
                str(quality.products_unknown) + " product observation(s) are "
                "'unknown': the evidence was insufficient either way. That is "
                "not a finding that the merchant does not stock the product.")
        if quality.competitors_uncertain:
            notes.append(
                str(quality.competitors_uncertain) + " business(es) could not be "
                "identified reliably enough to attribute evidence to them.")
        if quality.trend_series and not quality.trend_series_with_direction:
            notes.append(
                "No trend direction can be stated yet: every series holds a "
                "single distinct measurement. Repeating a search inside the "
                "response cache returns identical readings.")
        quality.notes = notes
        return quality


def _ordered_unique(values) -> List[str]:
    out: List[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out
