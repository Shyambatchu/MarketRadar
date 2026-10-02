"""Product discovery: what do the merchants in a market actually offer?

Built entirely on services that already exist, because every one of them is a
place where a second implementation would eventually disagree with the first:

* location          -- ``location_service.default_resolver``, via Competitors
* merchant identity -- ``CompetitorService`` over ``merchant_identity``
* product identity  -- ``product_identity.match_product``, unchanged
* product evidence  -- ``MerchantWebsitePriceProvider``
* search, cache, credits, provider errors -- ``ApiBudgetManager``

This module therefore resolves no locations, matches no merchants and
implements no product matching of its own. What it adds is the join: for each
merchant a market contains, ask the merchant's own site what it offers, and
record the answer as evidence.

It is also deliberately not a second Price Intelligence. Price evidence is
retained when the existing rules allow it, under the same semantics, but
nothing here re-derives prices or relaxes a rule to make one appear.

Nothing in this module names an industry, product, brand, merchant or place.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.merchant import Merchant
from app.models.product_observation import ProductObservation
from app.providers.merchant_website_provider import MerchantWebsitePriceProvider
from app.schemas.product import (
    ProductEvidence, ProductObservationRecord, ProductSearchResponse,
    RejectedProductResult, StageStatus,
)
from app.services.api_budget import ApiBudgetManager
from app.services.competitor_service import (
    _HAS_LETTER, MIN_QUERY_LENGTH, CompetitorService,
)
from app.services.merchant_identity import normalize_name
from app.services.product_identity import canonicalise, match_product

CACHE_VERSION = "v2"

# Reasons that are a specific contradiction rather than an absence of evidence.
# Only these may set product_status = not_found (spec: missing evidence is not
# proof of absence).
CONTRADICTION_REASONS = {"different_variant", "different_model", "different_size"}

FOUND = "found"
NOT_FOUND = "not_found"
UNKNOWN = "unknown"

VERIFIED = "verified"
UNAVAILABLE = "unavailable"

# Bounds credit spend: each merchant costs one indexed search. Callers may
# raise it; it exists so a broad market cannot quietly spend twenty credits.
DEFAULT_MAX_MERCHANTS = 5


class ProductService:
    def __init__(self, db: Session, competitor_service: CompetitorService,
                 website_provider: Optional[MerchantWebsitePriceProvider] = None):
        self.db = db
        self.competitors = competitor_service
        self.website_provider = website_provider or MerchantWebsitePriceProvider()

    # ------------------------------------------------------------------
    def discover(self, product: str, market: str = "", location: Optional[str] = None,
                 hl: str = "en", gl: str = "us",
                 max_merchants: int = DEFAULT_MAX_MERCHANTS,
                 persist: bool = True) -> ProductSearchResponse:
        """Find product evidence across the merchants in a market.

        Raises ``LocationResolutionError`` or ``SerpApiProviderError`` from the
        underlying services. Neither is converted into an empty result.
        """
        # Validated before anything is searched or written. Products persists
        # observations against the shared merchants table, so an unusable
        # request would pollute it for every later module.
        product = (product or "").strip()
        if not product:
            raise ValueError("A product query is required.")
        if len(product) < MIN_QUERY_LENGTH or not _HAS_LETTER.search(product):
            raise ValueError(
                "'" + product + "' is too short to describe a product.")
        # A blank market is filed under the product searched -- the same label
        # Competitors files its observations under -- so one search lands in
        # one Market Pulse context instead of two (one of them NULL).
        market = (market or "").strip() or product
        # Merchant discovery is geographic, so the same location requirement
        # applies here. Delegated validation would raise anyway; doing it here
        # names the product flow in the message.
        if not (location or "").strip():
            raise ValueError(
                "A location is required. Product evidence is gathered from the "
                "merchants in a place, so without one there are no catalogues "
                "to search.")

        stages: List[StageStatus] = []

        # ---------------- Stage 1: merchants -----------------------------
        # Delegated in full: this module must not identify businesses itself.
        merchant_search = self.competitors.discover(
            market=market, query=market,
            location=location, hl=hl, gl=gl, persist=persist)

        stages.append(StageStatus(
            stage="location_resolution",
            status="ok" if merchant_search.location_resolved else "skipped",
            detail=merchant_search.location_resolved or "no_location_supplied"))
        stages.append(StageStatus(
            stage="merchant_discovery", status="ok",
            results_count=len(merchant_search.competitors)))

        # A product may only be attributed to a merchant we actually
        # identified. An uncertain identity -- a chain we cannot pin to one
        # store, or a fuzzy name match -- may not carry product evidence.
        candidates = [c for c in merchant_search.competitors
                      if c.status != "uncertain"
                      and c.match_confidence != "low"]
        without_domain = [c for c in candidates if not c.domain]
        searchable = [c for c in candidates if c.domain][:max_merchants]

        if len(candidates) - len(without_domain) > max_merchants:
            stages.append(StageStatus(
                stage="merchant_selection", status="degraded",
                detail="limited to " + str(max_merchants) + " merchants to bound credit spend",
                results_count=len(searchable)))

        budget = ApiBudgetManager(self.db, self.competitors.organic.api_key)

        # ---------------- Stage 2: product evidence ----------------------
        evidence: List[ProductEvidence] = []
        rejected: List[RejectedProductResult] = []
        rows_examined = 0
        off_domain = 0
        listing_rejected = 0
        candidate_matches = 0
        provider_errors = 0

        for merchant in searchable:
            out = self.website_provider.discover_prices(
                {"domain": merchant.domain, "name": merchant.name},
                product, budget, CACHE_VERSION, hl=hl, gl=gl)

            if out["status"] == "error":
                # A provider failure is never "this merchant does not stock it".
                provider_errors += 1
                evidence.append(self._unknown_evidence(
                    merchant, reason="provider_request_failed"))
                continue
            if out["status"] == "skipped":
                continue

            off_domain += out["off_domain_rejected"]
            best = None

            for row in out["observations"]:
                rows_examined += 1
                verdict = match_product(product, row["title"], row["raw_snippet"],
                                        row["url"])

                if not verdict["matched"]:
                    rejected.append(RejectedProductResult(
                        merchant=merchant.name, title=row["title"], url=row["url"],
                        page_type=row["page_type"], reason=verdict["reason"],
                        detail=verdict["detail"]))
                    continue

                candidate_matches += 1
                if row["page_type"] == "listing":
                    listing_rejected += 1

                scored = self._score(merchant, product, row, verdict)
                # Prefer the strongest evidence this merchant offers: a
                # verified price beats an unverified one, a product page beats
                # a listing.
                if best is None or _rank(scored) < _rank(best):
                    best = scored

            if best is not None:
                evidence.append(best)
            else:
                # Rows were examined but none established identity. Absence of
                # a match is weak evidence, so the outcome is unknown unless a
                # row specifically contradicted the request.
                contradicted = next(
                    (r for r in rejected
                     if r.merchant == merchant.name
                     and r.reason in CONTRADICTION_REASONS), None)
                evidence.append(self._unknown_evidence(
                    merchant,
                    product_status=NOT_FOUND if contradicted else UNKNOWN,
                    reason=contradicted.reason if contradicted
                    else "insufficient_evidence"))

        stages.append(StageStatus(
            stage="product_evidence",
            status="degraded" if provider_errors else "ok",
            detail=(str(provider_errors) + " merchant lookups failed")
            if provider_errors else None,
            results_count=rows_examined))

        # ---------------- persistence ------------------------------------
        if persist:
            self._persist(evidence, product, market, location,
                          merchant_search.location_resolved)
            self.db.commit()
        stages.append(StageStatus(stage="persistence",
                                  status="ok" if persist else "skipped",
                                  results_count=len(evidence) if persist else None))

        evidence.sort(key=_rank)

        found = sum(1 for e in evidence if e.product_status == FOUND)
        not_found = sum(1 for e in evidence if e.product_status == NOT_FOUND)
        unknown = sum(1 for e in evidence if e.product_status == UNKNOWN)
        verified = sum(1 for e in evidence if e.price_status == VERIFIED)
        unavailable = sum(1 for e in evidence if e.price_status == UNAVAILABLE)

        return ProductSearchResponse(
            product_query=product, market=market or None,
            location_requested=location,
            location_resolved=merchant_search.location_resolved,
            location_resolution=merchant_search.location_resolution,
            provider_status="success" if evidence else "no_results",
            cache_hit=merchant_search.cache_hit,
            stages=stages,
            merchants_considered=len(candidates),
            merchants_searched=len(searchable),
            merchants_without_domain=len(without_domain),
            merchant_provider_errors=provider_errors,
            website_rows_examined=rows_examined,
            off_domain_rejected=off_domain,
            listing_pages_rejected=listing_rejected,
            candidate_matches=candidate_matches,
            products_found=found, products_not_found=not_found,
            products_unknown=unknown,
            prices_verified=verified, prices_unavailable=unavailable,
            evidence=evidence, rejected_results=rejected)

    # ------------------------------------------------------------------
    @staticmethod
    def _unknown_evidence(merchant, product_status: str = UNKNOWN,
                          reason: str = "insufficient_evidence") -> ProductEvidence:
        """A merchant we looked at but could not establish a product for."""
        return ProductEvidence(
            merchant=merchant.name, merchant_id=merchant.id,
            merchant_domain=merchant.domain,
            merchant_match_status=merchant.match_confidence
            if merchant.match_confidence != "unmatched" else "matched",
            product_status=product_status, price_status=UNKNOWN,
            verification_reason=reason,
            source_domain=merchant.domain,
            discovery_method="indexed_search",
            evidence_scope="catalog", inventory_confirmed=False,
            observed_at=datetime.now(timezone.utc))

    def _score(self, merchant, product: str, row: Dict, verdict: Dict) -> ProductEvidence:
        """Apply the established evidence rules to one matched row.

        These are Price Intelligence's rules, unchanged. Identity is settled by
        this point; everything below decides only whether the *price* may be
        treated as this product's price.
        """
        price_status = VERIFIED
        reason: Optional[str] = None

        def unavailable(why: str):
            nonlocal price_status, reason
            price_status, reason = UNAVAILABLE, why

        if merchant.status == "uncertain":
            unavailable("merchant_identity_uncertain")
        elif row["page_type"] == "listing":
            # A price on a filtered listing belongs to "some product in this
            # list", not to the requested one.
            unavailable("price_not_product_specific")
        elif row["is_range"]:
            unavailable("price_range")
        elif row["ambiguous_price"]:
            unavailable("ambiguous_price")
        elif not verdict["size_confirmed"]:
            # Identity holds, but the requested size was never observed.
            unavailable("size_unverified")
        elif row["price"] is None:
            unavailable("price_unavailable")

        return ProductEvidence(
            merchant=merchant.name, merchant_id=merchant.id,
            merchant_domain=merchant.domain,
            merchant_match_status="uncertain" if merchant.status == "uncertain"
            else "matched",
            product_name=row["title"],
            normalized_product_name=normalize_name(row["title"]),
            observed_size=verdict["observed_size"],
            size_confirmed=verdict["size_confirmed"],
            product_status=FOUND,
            price_status=price_status,
            verification_reason=reason,
            price=row["price"] if price_status == VERIFIED else None,
            currency="USD" if price_status == VERIFIED else None,
            source_type=row["source_type"], source_url=row["url"],
            source_domain=row["source_domain"],
            discovery_method="indexed_search", page_type=row["page_type"],
            # The merchant's own site proves it offers the product. It does not
            # prove any physical store currently holds it.
            evidence_scope="catalog", inventory_confirmed=False,
            match_method="product_identity", match_reason=verdict["reason"],
            snippet=row["raw_snippet"],
            observed_at=datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    def _persist(self, evidence: List[ProductEvidence], product: str,
                 market: str, location_requested: Optional[str],
                 location_resolved: Optional[str]) -> None:
        """Append observations. Nothing is updated or overwritten."""
        for e in evidence:
            self.db.add(ProductObservation(
                merchant_id=e.merchant_id,
                product_query=product, normalized_query=canonicalise(product),
                market=market or None,
                location_requested=location_requested,
                location_resolved=location_resolved,
                product_name=e.product_name,
                normalized_product_name=e.normalized_product_name,
                observed_size=e.observed_size,
                size_confirmed=e.size_confirmed,
                product_status=e.product_status, price_status=e.price_status,
                verification_reason=e.verification_reason,
                price=e.price, currency=e.currency,
                source_type=e.source_type, source_url=e.source_url,
                source_domain=e.source_domain,
                discovery_method=e.discovery_method, page_type=e.page_type,
                evidence_scope=e.evidence_scope,
                inventory_confirmed=e.inventory_confirmed,
                match_method=e.match_method, match_reason=e.match_reason,
                merchant_match_status=e.merchant_match_status,
                snippet=e.snippet))

    # ------------------------------------------------------------------
    def list_saved(self, product_query: Optional[str] = None,
                   market: Optional[str] = None,
                   merchant_id: Optional[int] = None,
                   product_status: Optional[str] = None,
                   limit: int = 100) -> Tuple[int, List[ProductObservationRecord]]:
        query = self.db.query(ProductObservation)
        if product_query:
            query = query.filter(
                ProductObservation.normalized_query == canonicalise(product_query))
        if market:
            query = query.filter(ProductObservation.market == market)
        if merchant_id is not None:
            query = query.filter(ProductObservation.merchant_id == merchant_id)
        if product_status:
            query = query.filter(ProductObservation.product_status == product_status)

        total = query.count()
        rows = query.order_by(ProductObservation.observed_at.desc(),
                              ProductObservation.id.desc()).limit(limit).all()
        return total, [self._to_record(r) for r in rows]

    def get_saved(self, observation_id: int) -> Optional[ProductObservationRecord]:
        row = self.db.query(ProductObservation).filter(
            ProductObservation.id == observation_id).first()
        return self._to_record(row) if row else None

    def _to_record(self, row: ProductObservation) -> ProductObservationRecord:
        merchant = self.db.query(Merchant).filter(
            Merchant.id == row.merchant_id).first() if row.merchant_id else None
        return ProductObservationRecord(
            id=row.id, merchant_id=row.merchant_id,
            merchant_name=merchant.name if merchant else None,
            merchant_domain=merchant.normalized_domain if merchant else None,
            product_query=row.product_query, market=row.market,
            location_resolved=row.location_resolved,
            product_name=row.product_name, observed_size=row.observed_size,
            size_confirmed=bool(row.size_confirmed),
            product_status=row.product_status, price_status=row.price_status,
            verification_reason=row.verification_reason,
            price=row.price, currency=row.currency,
            source_type=row.source_type, source_url=row.source_url,
            source_domain=row.source_domain,
            discovery_method=row.discovery_method, page_type=row.page_type,
            evidence_scope=row.evidence_scope or "catalog",
            inventory_confirmed=bool(row.inventory_confirmed),
            match_method=row.match_method or "product_identity",
            match_reason=row.match_reason,
            merchant_match_status=row.merchant_match_status or "matched",
            snippet=row.snippet, observed_at=row.observed_at)


def _rank(evidence: ProductEvidence) -> tuple:
    """Strongest evidence first: found before unknown, verified price before not."""
    product_rank = {FOUND: 0, UNKNOWN: 1, NOT_FOUND: 2}
    price_rank = {VERIFIED: 0, UNAVAILABLE: 1, UNKNOWN: 2}
    return (product_rank.get(evidence.product_status, 9),
            price_rank.get(evidence.price_status, 9),
            evidence.price if evidence.price is not None else float("inf"),
            (evidence.merchant or "").lower())
