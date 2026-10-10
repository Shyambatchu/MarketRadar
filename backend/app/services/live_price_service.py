import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.merchant import Merchant
from app.models.product_observation import ProductObservation
from app.providers.merchant_website_provider import MerchantWebsitePriceProvider
from app.schemas.local_price import (
    ApiUsageReport, LocalPriceObservation, LocalPriceSearchResponse,
    NearbyMerchantStatus, StageStatus,
)
from app.services.api_budget import ApiBudgetManager
from app.services.location_service import (
    LocationResolutionError, default_resolver,
)
from app.services.money import parse_price
from app.services.merchant_identity import (
    match_merchant, normalize_domain, normalize_name,
)
from app.services.product_identity import canonicalise, match_product
from app.services.serpapi_organic_service import SerpApiProviderError

CACHE_VERSION = "v2"

# LocationResolutionError is re-exported: the search centre is never guessed,
# because a wrong centre silently corrupts merchant discovery, distance, radius
# filtering and cache identity. Callers import it from here.
__all__ = ["LivePriceService", "LocationResolutionError", "SerpApiProviderError",
           "haversine_distance"]


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return 3958.8 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class LivePriceService:
    def __init__(self, api_key: str, resolver=None):
        self.api_key = api_key
        self.website_provider = MerchantWebsitePriceProvider()
        self.resolver = resolver or default_resolver

    # ------------------------------------------------------------------
    # Stage 0 -- search centre
    # ------------------------------------------------------------------
    def resolve_search_center(self, area: str, budget: ApiBudgetManager) -> Tuple[float, float, str, str]:
        """(lat, lon, resolved_name, method). Never falls back to a fixed point."""
        data = budget.execute_search(
            CACHE_VERSION + "|geocode|" + area,
            {"engine": "google_maps", "q": area, "type": "search"},
            "google_maps",
        )
        if data is None:
            # The provider failed (or no key is configured). That says nothing
            # about the location, so it must not be reported as a bad place.
            raise SerpApiProviderError(
                "The location provider did not respond"
                + (" (" + budget.last_error.rstrip(". ") + ")" if budget.last_error else "")
                + ". Try again in a moment.")

        place = data.get("place_results") or {}
        gps = place.get("gps_coordinates") or {}
        if "latitude" in gps and "longitude" in gps:
            return (gps["latitude"], gps["longitude"],
                    place.get("title") or area, "place_results")

        # Broad areas ("New Jersey", "Hyderabad") return local_results instead
        # of a single place; the map URL carries the centre Google resolved.
        maps_url = (data.get("search_metadata") or {}).get("google_maps_url", "")
        m = re.search(r"/@(-?\d+\.\d+),(-?\d+\.\d+),", maps_url)
        if m:
            return float(m.group(1)), float(m.group(2)), area, "maps_viewport_center"

        raise LocationResolutionError(
            "Could not resolve '" + area + "' to coordinates. Try a more specific location.")

    # ------------------------------------------------------------------
    # Stage 0b -- canonical location for location-sensitive providers
    # ------------------------------------------------------------------
    def resolve_provider_location(self, area: str, resolved_name: str):
        """Canonical provider location name + country code.

        Google Shopping rejects a raw street address; it needs a canonical
        catalogue location. Delegated to the shared resolver so Market Research
        and Price Intelligence agree on what a location means, and so a postal
        code resolves rather than being discarded -- the catalogue indexes
        postal codes, and stripping them used to leave "08807" unresolvable.

        Localisation is an enhancement here, not the point of the request: the
        search centre already came from geocoding, so an unresolvable provider
        location degrades the shopping stage instead of failing the search.
        """
        for raw in (area, resolved_name):
            if not raw:
                continue
            resolution = self.resolver.resolve_or_none(raw)
            if resolution:
                return resolution.canonical_name, resolution.country_code
        return None, None

    # ------------------------------------------------------------------
    def fetch_real_data(self, product: str, area: str, radius: int, db: Session,
                        reference_merchant_name: Optional[str] = None,
                        hl: str = "en", gl: Optional[str] = None,
                        persist: bool = True) -> LocalPriceSearchResponse:
        budget = ApiBudgetManager(db, self.api_key)
        stages: List[StageStatus] = []

        lat, lon, center_name, center_method = self.resolve_search_center(area, budget)
        search_center_dict = {"name": center_name, "latitude": lat,
                              "longitude": lon, "resolution_method": center_method}
        stages.append(StageStatus(stage="search_center", status="ok", detail=center_method))

        provider_location, country_code = self.resolve_provider_location(area, center_name)
        effective_gl = gl or country_code or "us"

        # ---------------- Stage 1: merchant discovery ----------------
        maps_query = product + " stores"
        maps_data = budget.execute_search(
            CACHE_VERSION + "|maps|" + maps_query + "|" + str(lat) + "," + str(lon) +
            "|" + str(radius) + "mi|" + hl,
            {"engine": "google_maps", "q": maps_query,
             "ll": "@" + str(lat) + "," + str(lon) + ",11z", "hl": hl, "type": "search"},
            "google_maps",
        )
        if maps_data is None:
            stages.append(StageStatus(stage="merchant_discovery", status="error",
                                      detail="provider_request_failed"))
            maps_data = {}

        merchant_identities: List[Dict] = []
        nearby: List[NearbyMerchantStatus] = []

        for res in maps_data.get("local_results", []) or []:
            title = res.get("title")
            gps = res.get("gps_coordinates") or {}
            if not title or "latitude" not in gps or "longitude" not in gps:
                continue
            dist = round(haversine_distance(lat, lon, gps["latitude"], gps["longitude"]), 1)
            if dist > radius:
                continue
            website = res.get("website", "") or ""
            merchant_identities.append({
                "name": title, "normalized_name": normalize_name(title),
                "domain": normalize_domain(website), "website": website,
                "address": res.get("address", "") or "",
                "place_id": res.get("place_id", "") or "",
                "lat": gps["latitude"], "lon": gps["longitude"], "dist": dist,
            })
            nearby.append(NearbyMerchantStatus(
                merchant=title, address=res.get("address", ""), distance=dist,
                website=website, place_id=res.get("place_id", ""),
                product_status="unknown", price_status="unknown",
                verification_reason="insufficient_evidence",
            ))

        if maps_data:
            stages.append(StageStatus(stage="merchant_discovery", status="ok",
                                      results_count=len(merchant_identities)))

        counters = {k: 0 for k in (
            "website_candidates", "website_exact", "website_merchant_matches",
            "shopping_candidates", "shopping_exact", "shopping_merchant_matches",
            "uncertain")}
        verified_obs: List[LocalPriceObservation] = []

        # ---------------- shared verification ----------------
        def apply_candidate(merchant, title, snippet, url, price, page_type,
                            is_range, ambiguous, source_type, source_domain,
                            evidence_scope, match_method, match_confidence,
                            merchant_match_status, currency=None):
            nms = next((n for n in nearby if n.merchant == merchant["name"]), None)
            if nms is None or nms.price_status == "verified":
                return

            verdict = match_product(product, title, snippet, url)

            if not verdict["matched"]:
                # Absence of a match is weak evidence: only a specific
                # contradiction may set not_found (spec 13 / 52).
                if nms.product_status == "unknown" and verdict["reason"] in (
                        "different_variant", "different_model", "different_size"):
                    nms.product_status = "not_found"
                    nms.price_status = "unknown"
                    nms.verification_reason = verdict["reason"]
                    nms.source_domain = source_domain
                    nms.source_url = url
                return

            nms.product_status = "found"
            nms.product_name = title
            nms.product_size = verdict["observed_size"]
            nms.source_domain = source_domain
            nms.source_url = url
            nms.evidence_scope = evidence_scope
            nms.inventory_confirmed = False
            nms.merchant_match_status = merchant_match_status

            def unavailable(reason):
                nms.price_status = "unavailable"
                nms.verification_reason = reason

            if merchant_match_status != "matched":
                return unavailable("merchant_identity_uncertain")
            if page_type == "listing":
                return unavailable("price_not_product_specific")
            if is_range:
                return unavailable("price_range")
            if ambiguous:
                return unavailable("ambiguous_price")
            if not verdict["size_confirmed"]:
                return unavailable("size_unverified")
            if price is None:
                return unavailable("price_unavailable")
            if not currency:
                return unavailable("currency_unknown")

            nms.price_status = "verified"
            nms.verification_reason = None
            nms.price = price
            nms.currency = currency
            nms.price_source = source_type

            is_ref = bool(reference_merchant_name) and \
                merchant["name"].lower() == reference_merchant_name.lower()
            if is_ref or any(o.merchant == merchant["name"] for o in verified_obs):
                return

            verified_obs.append(LocalPriceObservation(
                merchant=merchant["name"], merchant_name=merchant["name"],
                merchant_domain=merchant["domain"], product_name=title,
                normalized_product_name=normalize_name(title),
                size=verdict["observed_size"], price=price, currency=currency,
                source_type=source_type, source_domain=source_domain,
                source_url=url, discovery_method="indexed_search",
                observed_at=datetime.now(timezone.utc), snippet_text=snippet,
                verification_status="verified", evidence_scope=evidence_scope,
                inventory_confirmed=False, page_type=page_type,
                distance=merchant["dist"], is_reference_store=False,
                match_type="exact", match_method=match_method,
                match_confidence=match_confidence,
                merchant_match_status=merchant_match_status, source=source_type,
            ))

        # ---------------- Stage 2: merchant website evidence ----------------
        website_rows = 0
        off_domain = 0
        listing_pages = 0
        website_errors = 0
        for m in merchant_identities:
            if not m["domain"]:
                continue
            out = self.website_provider.discover_prices(
                m, product, budget, CACHE_VERSION, hl=hl, gl=effective_gl)
            if out["status"] == "error":
                website_errors += 1
                continue
            off_domain += out["off_domain_rejected"]
            for obs in out["observations"]:
                website_rows += 1
                counters["website_candidates"] += 1
                if obs["page_type"] == "listing":
                    listing_pages += 1
                # The row is served by this merchant's own domain, so merchant
                # identity is exact by construction -- but a catalogue is not a
                # store shelf (spec 38).
                counters["website_merchant_matches"] += 1
                if match_product(product, obs["title"], obs["raw_snippet"], obs["url"])["matched"]:
                    counters["website_exact"] += 1
                apply_candidate(
                    merchant=m, title=obs["title"], snippet=obs["raw_snippet"],
                    url=obs["url"], price=obs["price"], page_type=obs["page_type"],
                    is_range=obs["is_range"], ambiguous=obs["ambiguous_price"],
                    currency=obs.get("currency"),
                    source_type="merchant_website_indexed",
                    source_domain=obs["source_domain"], evidence_scope="catalog",
                    match_method="exact_domain", match_confidence="high",
                    merchant_match_status="matched",
                )

        stages.append(StageStatus(
            stage="merchant_website_evidence",
            status="degraded" if website_errors else "ok",
            detail=(str(website_errors) + " merchant lookups failed") if website_errors else None,
            results_count=website_rows))

        # ---------------- Stage 3: shopping evidence ----------------
        shopping_params = {"engine": "google_shopping", "q": product,
                           "hl": hl, "gl": effective_gl}
        if provider_location:
            shopping_params["location"] = provider_location
        # Cache identity mirrors request identity exactly: every parameter the
        # provider is given is in the key, and nothing it is not. Radius is
        # absent because the shopping request is not radius-scoped -- it is the
        # canonical location, language and country that change these results.
        shopping_key = (CACHE_VERSION + "|shopping|" + product + "|" +
                        (provider_location or "nolocation") + "|" + hl + "|" + effective_gl)

        shopping_data = budget.execute_search(shopping_key, shopping_params, "google_shopping")

        if shopping_data is None:
            stages.append(StageStatus(stage="shopping_evidence", status="error",
                                      detail="provider_request_failed", results_count=None))
            shopping_results = []
        else:
            shopping_results = shopping_data.get("shopping_results", []) or []
            stages.append(StageStatus(
                stage="shopping_evidence",
                status="ok" if provider_location else "degraded",
                detail=None if provider_location else "location_not_resolved_results_not_localised",
                results_count=len(shopping_results)))

        for item in shopping_results:
            counters["shopping_candidates"] += 1
            title = item.get("title", "")
            source_name = item.get("source", "") or ""
            link = item.get("link") or item.get("product_link") or ""
            # The provider's own parse of the amount, with the currency read
            # from the displayed price -- never assumed from the symbol alone.
            parsed = parse_price(str(item.get("price") or ""), effective_gl)
            price = item.get("extracted_price")
            if not isinstance(price, (int, float)):
                price = parsed.amount if parsed else None
            currency = item.get("currency") if isinstance(item.get("currency"), str)                 and len(item.get("currency")) == 3 else (parsed.currency if parsed else None)

            shop_domain = normalize_domain(link)
            if not shop_domain and "." in source_name:
                shop_domain = normalize_domain("http://" + source_name)

            if match_product(product, title, "", link)["matched"]:
                counters["shopping_exact"] += 1

            resolved = match_merchant(shop_domain, source_name, merchant_identities)
            if resolved["status"] == "uncertain":
                counters["uncertain"] += 1
            if not resolved["merchant"]:
                continue
            counters["shopping_merchant_matches"] += 1

            apply_candidate(
                merchant=resolved["merchant"], title=title, snippet="", url=link,
                price=price, page_type="product", is_range=False, ambiguous=False,
                currency=currency,
                source_type="google_shopping", source_domain=shop_domain,
                evidence_scope="marketplace_listing",
                match_method=resolved["method"], match_confidence=resolved["confidence"],
                merchant_match_status=resolved["status"],
            )

        # ---------------- assembly ----------------
        nearby.sort(key=lambda x: x.distance)
        verified_obs.sort(key=lambda x: x.price if x.price is not None else float("inf"))

        currencies = sorted({o.currency for o in verified_obs if o.price is not None})
        # Figures in different currencies are never averaged together.
        prices = [o.price for o in verified_obs if o.price is not None]             if len(currencies) <= 1 else []
        sizes = sorted({o.size for o in verified_obs if o.size})

        reference_store = None
        found = 0
        not_found = 0
        unknown = 0
        price_unavailable = 0
        for nms in nearby:
            if reference_merchant_name and nms.merchant.lower() == reference_merchant_name.lower():
                reference_store = nms
            if nms.product_status == "found":
                found += 1
                if nms.price_status == "unavailable":
                    price_unavailable += 1
            elif nms.product_status == "not_found":
                not_found += 1
            else:
                unknown += 1

        persisted = 0
        # No session means nothing to write to (unit tests drive the funnel
        # with a stubbed budget); that is "skipped", not a failure.
        persist = persist and db is not None
        if persist:
            persisted = self._persist(db, product, nearby, merchant_identities,
                                      provider_location)
        stages.append(StageStatus(stage="persistence",
                                  status="ok" if persist else "skipped",
                                  results_count=persisted if persist else None))

        return LocalPriceSearchResponse(
            persisted_observations=persisted,
            searched_product=product, searched_area=area, searched_radius=radius,
            search_center=search_center_dict, product_name=product, area=area,
            radius=radius,
            lowest_price=min(prices) if prices else None,
            average_price=round(sum(prices) / len(prices), 2) if prices else None,
            highest_price=max(prices) if prices else None,
            verified_sizes=sizes, mixed_size_statistics=len(sizes) > 1,
            currency=currencies[0] if len(currencies) == 1 else None,
            mixed_currency_statistics=len(currencies) > 1,
            nearby_merchants_discovered=len(merchant_identities),
            product_evidence_found=found, product_evidence_not_found=not_found,
            product_evidence_unknown=unknown, price_unavailable_count=price_unavailable,
            website_results_found=website_rows,
            website_off_domain_rejected=off_domain,
            website_listing_pages=listing_pages,
            shopping_results_found=len(shopping_results),
            candidate_product_matches=counters["website_candidates"] + counters["shopping_candidates"],
            exact_product_matches=counters["website_exact"] + counters["shopping_exact"],
            merchant_matches=counters["website_merchant_matches"] + counters["shopping_merchant_matches"],
            website_candidates=counters["website_candidates"],
            website_exact_matches=counters["website_exact"],
            website_merchant_matches=counters["website_merchant_matches"],
            shopping_candidates=counters["shopping_candidates"],
            shopping_exact_matches=counters["shopping_exact"],
            shopping_merchant_matches=counters["shopping_merchant_matches"],
            merchant_uncertain_count=counters["uncertain"],
            verified_local_prices=sum(1 for o in verified_obs if o.price is not None),
            stages=stages,
            reference_price=reference_store.price if reference_store else None,
            reference_store=reference_store, nearby_merchants=nearby,
            verified_price_observations=verified_obs,
            api_usage=ApiUsageReport(**budget.get_usage_report()),
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    @staticmethod
    def _persist(db: Session, product: str, nearby: List[NearbyMerchantStatus],
                 identities: List[Dict], location_resolved: Optional[str]) -> int:
        """Append what this run established, so it feeds Trends and Pulse.

        Only merchants with evidence either way (found or specifically
        contradicted) are recorded. A merchant that was never looked at, or
        whose lookup produced nothing, is not a reading of that merchant, and
        storing it as "unknown" would turn a gap in coverage into history.

        Rows go into the same append-only ``product_observations`` table that
        Products writes, filed under the product as the market -- the same
        convention Products uses for a blank market -- and the provider's
        canonical location, so both modules' readings land in one context.
        ``discovery_method`` records that they came from Price Intelligence.
        """
        by_name = {m["name"]: m for m in identities}
        written = 0
        for status in nearby:
            if status.product_status not in ("found", "not_found"):
                continue
            identity = by_name.get(status.merchant) or {}
            merchant = _upsert_merchant(db, status.merchant, identity)
            verified = status.price_status == "verified"
            db.add(ProductObservation(
                merchant_id=merchant.id,
                product_query=product, normalized_query=canonicalise(product),
                market=product, location_requested=None,
                location_resolved=location_resolved,
                product_name=status.product_name,
                normalized_product_name=normalize_name(status.product_name or ""),
                observed_size=status.product_size,
                size_confirmed=bool(verified),
                product_status=status.product_status,
                price_status=status.price_status,
                verification_reason=status.verification_reason,
                price=status.price if verified else None,
                currency=status.currency if verified else None,
                source_type=status.price_source or (
                    "google_shopping" if status.evidence_scope == "marketplace_listing"
                    else "merchant_website_indexed"),
                source_url=status.source_url, source_domain=status.source_domain,
                discovery_method="price_intelligence",
                page_type=None,
                evidence_scope=status.evidence_scope or "catalog",
                inventory_confirmed=False,
                match_method="product_identity",
                merchant_match_status=status.merchant_match_status))
            written += 1
        db.commit()
        return written


def _upsert_merchant(db: Session, name: str, identity: Dict) -> Merchant:
    """The shared business identity, found by domain then place id.

    Gaps are filled, never overwritten -- the same rule Competitors applies --
    and a name alone never matches an existing merchant, because a name does
    not identify a business across places.
    """
    domain = identity.get("domain") or None
    place_id = identity.get("place_id") or None
    merchant = None
    if domain:
        merchant = db.query(Merchant).filter(Merchant.normalized_domain == domain).first()
    if merchant is None and place_id:
        merchant = db.query(Merchant).filter(Merchant.place_id == place_id).first()
    now = datetime.now(timezone.utc)
    if merchant is None:
        merchant = Merchant(
            name=name, normalized_name=normalize_name(name),
            website=identity.get("website") or None, normalized_domain=domain,
            place_id=place_id, address=identity.get("address") or None,
            latitude=identity.get("lat"), longitude=identity.get("lon"),
            source="google_maps", entity_type="business",
            # A structured map result with a place id or its own domain is the
            # same evidence Competitors treats as verified.
            status="verified" if (place_id or domain) else "discovered",
            last_seen_at=now)
        db.add(merchant)
        db.flush()
    else:
        for field, value in (("website", identity.get("website")),
                             ("normalized_domain", domain), ("place_id", place_id),
                             ("address", identity.get("address")),
                             ("latitude", identity.get("lat")),
                             ("longitude", identity.get("lon"))):
            if value and not getattr(merchant, field):
                setattr(merchant, field, value)
        merchant.last_seen_at = now
    return merchant
