"""Competitor discovery.

Built on the services the earlier modules already use, not beside them:

* location resolution -- ``location_service.default_resolver`` (the audited
  resolver; a second one must never exist)
* search, caching, credit accounting, provider-error semantics --
  ``SerpApiOrganicService`` over ``ApiBudgetManager``
* business identity -- ``merchant_identity.match_merchant`` and its
  normalisers (the only merchant matcher)
* business records -- the shared ``merchants`` table

One ``google`` search returns both ``local_results`` and ``organic_results``, so
a single credit covers both sources. Local results come first and are
authoritative: each is a structured business, and the domains they establish
then corroborate organic results, which are otherwise only classified
heuristically.

Nothing here names an industry, a market, a location or a company. The market
and query are inputs; the only judgements made are about the shape of a web
result and the strength of an identity match.
"""
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.competitor import CompetitorObservation
from app.models.merchant import Merchant
from app.schemas.competitor import (
    Competitor, CompetitorEvidence, CompetitorSearchResponse, RejectedResult,
    StageStatus,
)
from app.services.merchant_identity import (
    match_merchant, normalize_domain, normalize_name,
)
from app.services.result_classifier import (
    BUSINESS, classify_local_result, classify_organic_result,
    is_platform_domain, registrable_domain,
)
from app.services.serpapi_organic_service import (
    SerpApiOrganicService, SerpApiProviderError,
)

# Status values, kept explicit so an uncertain business is never quietly
# promoted to a verified competitor.
VERIFIED = "verified"
DISCOVERED = "discovered"
UNCERTAIN = "uncertain"
REJECTED = "rejected"

LOCAL = "local"
ORGANIC = "organic"

# Shortest input that can meaningfully describe a market. Purely structural --
# there is no list of acceptable industries anywhere, and there must not be.
MIN_QUERY_LENGTH = 2

_HAS_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


def validate_discovery_request(market: str, query: str,
                               location: Optional[str]) -> Tuple[str, str, str]:
    """Reject a request that cannot produce meaningful competitor evidence.

    Discovery persists what it finds, so an unusable request does not merely
    return nothing -- it writes meaningless businesses into the shared
    ``merchants`` table, where every later module inherits them.

    Observed: ``?market=x`` with no location ran an unscoped global search for
    "x" and persisted a government space-weather page as a competitor.

    Two gates, both structural and industry-agnostic:

    * the query must be long enough to describe something and contain a
      letter, which rejects "x", "1" and punctuation;
    * a location is required, because a market without a place is not a market
      this module can describe. It is also the stronger gate: the location is
      then resolved against the provider's catalogue before any search runs, so
      an unresolvable place fails before anything is persisted.
    """
    market = (market or "").strip()
    query = (query or "").strip()
    location = (location or "").strip()

    effective_query = query or market
    if not effective_query:
        raise ValueError("Provide a market/industry or a search query.")
    if len(effective_query) < MIN_QUERY_LENGTH or not _HAS_LETTER.search(effective_query):
        raise ValueError(
            "'" + effective_query + "' is too short to describe a market. "
            "Give a market or industry such as the kind of business you are "
            "looking for.")
    if not location:
        raise ValueError(
            "A location is required. Competitor discovery finds businesses "
            "competing in a market *and* a place; without one the search is "
            "not geographically scoped and returns unrelated results.")

    return market, query, location


def _ordered_unique(values) -> List[str]:
    """De-duplicate while preserving order, dropping blanks."""
    out: List[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def _display_match_method(method: Optional[str]) -> str:
    """How identity was established, as something a reader can act on.

    ``match_merchant`` returns "unmatched" when nothing in the candidate set
    resembled the result -- correct, but on a first sighting that is not a
    failed match, it is simply the first time we have seen the business.
    """
    if not method or method == "unmatched":
        return "new"
    return method


class CompetitorService:
    def __init__(self, db: Session, organic_service: SerpApiOrganicService):
        self.db = db
        self.organic = organic_service

    # ------------------------------------------------------------------
    def discover(self, market: str, query: str, location: Optional[str] = None,
                 hl: str = "en", gl: str = "us",
                 num: int = 20, persist: bool = True) -> CompetitorSearchResponse:
        """Discover competitors for a market and place.

        Raises ``LocationResolutionError`` (unresolvable location) or
        ``SerpApiProviderError`` (the provider failed). Neither is converted
        into an empty competitor list.
        """
        # Validated before anything is searched or written: discovery
        # persists what it finds, so an unusable request would pollute the
        # shared merchants table rather than simply returning nothing.
        market, query, location = validate_discovery_request(market, query, location)
        # The explicit query wins when given, because it is the user's stated
        # intent; the market is what the results get filed under either way.
        effective_query = query or market

        stages: List[StageStatus] = []

        # One search, two sources. Location resolution and cache identity are
        # handled inside the organic service, so they cannot drift from what
        # Market Research does.
        search = self.organic.search_google(
            query=effective_query, location=location, num=num, hl=hl, gl=gl)

        resolution = search.get("location_resolution")
        stages.append(StageStatus(
            stage="location_resolution",
            status="ok" if resolution else "skipped",
            detail=(resolution or {}).get("canonical_name") if resolution
            else "no_location_supplied"))

        local_rows = search.get("local_results") or []
        organic_rows = search.get("results") or []
        stages.append(StageStatus(stage="local_discovery", status="ok",
                                  results_count=len(local_rows)))
        stages.append(StageStatus(stage="organic_discovery", status="ok",
                                  results_count=len(organic_rows)))

        candidates: List[Dict] = []
        rejected: List[RejectedResult] = []

        # ---------------- local results: authoritative -------------------
        for row in local_rows:
            classification = classify_local_result(row)
            website = row.get("website") or ""
            # A business listing a social or marketplace page as its website
            # does not own that domain. The URL stays as evidence, but it may
            # not become this business's identity -- otherwise every business
            # sharing the platform would collide on the exact-domain tier.
            domain = "" if is_platform_domain(website) else normalize_domain(website)
            if classification.entity_type != BUSINESS:
                rejected.append(RejectedResult(
                    title=row.get("title"), url=website or None, domain=domain or None,
                    entity_type=classification.entity_type,
                    reason=classification.reason, source_type=LOCAL))
                continue

            self._add_candidate(candidates, {
                "name": row.get("title") or "",
                "domain": domain,
                "website": website or None,
                "address": row.get("address") or None,
                "place_id": row.get("place_id") or None,
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "rating": row.get("rating"),
                "reviews": row.get("reviews"),
                "position": row.get("position"),
                "title": row.get("title"),
                "snippet": None,
                "source_type": LOCAL,
                "discovery_method": "google_maps_local",
                "entity_type": classification.entity_type,
                "classification_reason": classification.reason,
                "classification_confidence": classification.confidence,
            })

        # Domains a structured local result already vouched for.
        known_business_domains = {
            registrable_domain(c["domain"]) for c in candidates if c["domain"]}

        # ---------------- organic results: classified --------------------
        for row in organic_rows:
            url = row.get("link") or ""
            classification = classify_organic_result(
                row.get("title") or "", url, row.get("snippet") or "",
                known_business_domains=known_business_domains)
            domain = normalize_domain(url)

            if classification.entity_type != BUSINESS:
                # Retained, not discarded: the funnel reports what it rejected.
                rejected.append(RejectedResult(
                    title=row.get("title"), url=url or None, domain=domain or None,
                    entity_type=classification.entity_type,
                    reason=classification.reason, source_type=ORGANIC))
                continue

            self._add_candidate(candidates, {
                "name": self._business_name_from_organic(row, domain),
                "domain": domain,
                "website": url or None,
                "address": None,
                "place_id": None,
                # An organic result carries no coordinates; inventing them
                # would be worse than leaving them unknown.
                "latitude": None,
                "longitude": None,
                "rating": None,
                "reviews": None,
                "position": row.get("position"),
                "title": row.get("title"),
                "snippet": row.get("snippet"),
                "source_type": ORGANIC,
                "discovery_method": "google_organic",
                "entity_type": classification.entity_type,
                "classification_reason": classification.reason,
                "classification_confidence": classification.confidence,
            })

        duplicates_merged = sum(len(c["evidence"]) - 1 for c in candidates)
        stages.append(StageStatus(
            stage="identity_resolution", status="ok",
            results_count=len(candidates),
            detail=(str(duplicates_merged) + " duplicate results merged")
            if duplicates_merged else None))

        # ---------------- status, then persistence -----------------------
        competitors: List[Competitor] = []
        new_count = 0
        for candidate in candidates:
            status, reason = self._decide_status(candidate)
            competitor, is_new = self._persist(
                # A blank market is filed under the query actually searched,
                # so every observation of one search shares one context.
                candidate, status, reason, market or effective_query, query,
                effective_query,
                location, (resolution or {}).get("canonical_name"),
                persist=persist)
            new_count += 1 if is_new else 0
            competitors.append(competitor)

        if persist:
            self.db.commit()

        stages.append(StageStatus(
            stage="persistence",
            status="ok" if persist else "skipped",
            results_count=len(competitors) if persist else None))

        # Rank by evidence strength, then visibility, then name -- never by a
        # score we invented.
        rank = {VERIFIED: 0, DISCOVERED: 1, UNCERTAIN: 2, REJECTED: 3}
        competitors.sort(key=lambda c: (
            rank.get(c.status, 9),
            c.best_position if c.best_position is not None else 9999,
            c.name.lower()))

        return CompetitorSearchResponse(
            market=market, query=query, effective_query=effective_query,
            location_requested=location,
            location_resolved=(resolution or {}).get("canonical_name"),
            location_resolution=resolution,
            provider_status="success" if competitors else "no_results",
            cache_hit=bool(search.get("cache_hit")),
            stages=stages,
            local_results_found=len(local_rows),
            organic_results_found=len(organic_rows),
            business_candidates=len(candidates),
            rejected_non_business=len(rejected),
            competitors_discovered=sum(1 for c in competitors if c.status == DISCOVERED),
            competitors_verified=sum(1 for c in competitors if c.status == VERIFIED),
            competitors_uncertain=sum(1 for c in competitors if c.status == UNCERTAIN),
            duplicates_merged=duplicates_merged,
            new_competitors=new_count,
            competitors=competitors,
            rejected_results=rejected,
        )

    # ------------------------------------------------------------------
    # Identity: dedup within one search
    # ------------------------------------------------------------------
    def _add_candidate(self, candidates: List[Dict], row: Dict) -> None:
        """Merge ``row`` into an existing candidate, or start a new one.

        The same company routinely appears as a local result and again as one or
        more organic results. Matching is delegated to the shared tiered matcher
        so competitor identity cannot drift from merchant identity.
        """
        row["normalized_name"] = normalize_name(row["name"])
        if not row["name"]:
            return

        existing = match_merchant(
            row["domain"], row["name"],
            [{"name": c["name"], "normalized_name": c["normalized_name"],
              "domain": c["domain"], "address": c["address"] or "",
              "_ref": c} for c in candidates],
            source_address=row["address"] or "")

        evidence = {
            "source_type": row["source_type"],
            "source_url": row["website"],
            "source_domain": row["domain"] or None,
            "discovery_method": row["discovery_method"],
            "entity_type": row["entity_type"],
            "position": row["position"],
            "rating": row["rating"],
            "reviews": row["reviews"],
            "title": row["title"],
            "snippet": row["snippet"],
            "match_method": existing["method"],
            "match_confidence": existing["confidence"],
            "classification_reason": row["classification_reason"],
            "classification_confidence": row["classification_confidence"],
        }

        if existing["merchant"] is not None:
            target = existing["merchant"]["_ref"]
            target["evidence"].append(evidence)
            # A local result identifies a business better than an organic one,
            # so it upgrades the record it merged into.
            if row["source_type"] == LOCAL and target["source_type"] != LOCAL:
                for field in ("name", "address", "place_id", "latitude", "longitude",
                              "rating", "reviews", "source_type", "discovery_method",
                              "classification_reason", "classification_confidence"):
                    target[field] = row[field]
                target["normalized_name"] = row["normalized_name"]
            for field in ("domain", "website", "address", "place_id",
                          "latitude", "longitude", "rating", "reviews"):
                if not target.get(field) and row.get(field):
                    target[field] = row[field]
            target["match_method"] = existing["method"]
            target["match_confidence"] = existing["confidence"]
            target["ambiguous"] = target.get("ambiguous") or \
                existing["status"] == "uncertain"
            return

        row["evidence"] = [evidence]
        row["match_method"] = "new"
        row["match_confidence"] = "unmatched"
        # An ambiguous tier match means the evidence pointed at several
        # candidates at once; it may not become a verified identity.
        row["ambiguous"] = existing["status"] == "uncertain"
        candidates.append(row)

    @staticmethod
    def _business_name_from_organic(row: Dict, domain: str) -> str:
        """Best available name for an organic result.

        A page title is not a business name, so the leading segment before a
        separator is used and the domain is the fallback. Never invented: if
        nothing usable is present the domain stands in, which is at least true.
        """
        title = (row.get("title") or "").strip()
        for separator in ("|", " - ", " – ", " — ", ":"):
            if separator in title:
                head = title.split(separator)[0].strip()
                if len(head) >= 3:
                    return head
                break
        return title or domain or ""

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    @staticmethod
    def _decide_status(candidate: Dict) -> Tuple[str, Optional[str]]:
        """Strong evidence verifies; weak evidence stays weak.

        Verified needs identity that cannot reasonably be another business: a
        structured local result with a place id or its own domain, or an
        organic result a local result already vouched for. Everything resting
        on a fuzzy name, or on an ambiguous tier match, stays uncertain.
        """
        if candidate.get("ambiguous"):
            return UNCERTAIN, "ambiguous_identity_match"
        if candidate.get("match_confidence") == "low":
            return UNCERTAIN, "fuzzy_name_match_only"

        if candidate["source_type"] == LOCAL:
            if candidate.get("place_id") or candidate.get("domain"):
                return VERIFIED, None
            return DISCOVERED, "local_result_without_place_id_or_domain"

        if candidate.get("classification_confidence") == "high":
            # Corroborated by local discovery.
            return VERIFIED, None
        if candidate.get("domain"):
            return DISCOVERED, "organic_only_evidence"
        return UNCERTAIN, "no_domain_evidence"

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _find_existing(self, candidate: Dict,
                       location_resolved: Optional[str] = None) -> Optional[Merchant]:
        """Match against saved businesses in the tier order of the spec.

        Domain, then place id, then normalised name. No fuzzy matching against
        the whole table: at this scale it would eventually merge two unrelated
        businesses, and a wrong merge is unrecoverable.

        A name alone identifies nothing across places -- "Joe's Pizza" in two
        cities is two businesses -- so the name tier only matches a merchant
        already observed in the same resolved location.
        """
        if candidate.get("domain"):
            found = self.db.query(Merchant).filter(
                Merchant.normalized_domain == candidate["domain"]).first()
            if found:
                return found
        if candidate.get("place_id"):
            found = self.db.query(Merchant).filter(
                Merchant.place_id == candidate["place_id"]).first()
            if found:
                return found
        if candidate.get("normalized_name") and location_resolved:
            return self.db.query(Merchant).join(
                CompetitorObservation,
                CompetitorObservation.merchant_id == Merchant.id).filter(
                Merchant.normalized_name == candidate["normalized_name"],
                CompetitorObservation.location_resolved == location_resolved,
            ).first()
        return None

    def _persist(self, candidate: Dict, status: str, reason: Optional[str],
                 market: str, query: str, effective_query: str,
                 location_requested: Optional[str],
                 location_resolved: Optional[str],
                 persist: bool = True) -> Tuple[Competitor, bool]:
        now = datetime.now(timezone.utc)
        evidence_models = [
            CompetitorEvidence(
                source_type=e["source_type"], source_url=e["source_url"],
                source_domain=e["source_domain"],
                discovery_method=e["discovery_method"],
                entity_type=e["entity_type"], observed_at=now,
                match_method=e["match_method"],
                match_confidence=e["match_confidence"],
                status=status, reason=reason or e["classification_reason"],
                position=e["position"], rating=e["rating"], reviews=e["reviews"],
                title=e["title"], snippet=e["snippet"])
            for e in candidate["evidence"]]

        positions = [e["position"] for e in candidate["evidence"]
                     if e["position"] is not None]
        sources = _ordered_unique(e["source_type"] for e in candidate["evidence"])
        methods = _ordered_unique(e["discovery_method"] for e in candidate["evidence"])
        competitor = Competitor(
            name=candidate["name"], normalized_name=candidate["normalized_name"],
            domain=candidate["domain"] or None, website=candidate["website"],
            address=candidate["address"], place_id=candidate["place_id"],
            latitude=candidate.get("latitude"), longitude=candidate.get("longitude"),
            status=status, entity_type=candidate["entity_type"],
            match_method=_display_match_method(candidate["match_method"]),
            match_confidence=candidate["match_confidence"],
            status_reason=reason,
            rating=candidate["rating"], reviews=candidate["reviews"],
            best_position=min(positions) if positions else None,
            market=market or None,
            location_requested=location_requested,
            location_resolved=location_resolved,
            markets=[market] if market else [],
            locations=[location_resolved or location_requested]
            if (location_resolved or location_requested) else [],
            discovery_sources=sources, discovery_methods=methods,
            has_location_evidence=bool(
                candidate["address"] or candidate.get("latitude") is not None),
            last_seen_at=now, evidence_count=len(evidence_models),
            evidence=evidence_models)

        if not persist:
            return competitor, False

        merchant = self._find_existing(candidate, location_resolved)
        is_new = merchant is None
        if is_new:
            merchant = Merchant(
                name=candidate["name"],
                normalized_name=candidate["normalized_name"],
                website=candidate["website"],
                normalized_domain=candidate["domain"] or None,
                place_id=candidate["place_id"],
                address=candidate["address"],
                latitude=candidate.get("latitude"),
                longitude=candidate.get("longitude"),
                source=candidate["discovery_method"],
                entity_type=candidate["entity_type"],
                status=status, last_seen_at=now)
            self.db.add(merchant)
        else:
            # Only ever fill gaps: a saved value is evidence already recorded,
            # and a later thinner result must not erase it.
            for field, value in (("website", candidate["website"]),
                                 ("normalized_domain", candidate["domain"] or None),
                                 ("place_id", candidate["place_id"]),
                                 ("address", candidate["address"]),
                                 ("latitude", candidate.get("latitude")),
                                 ("longitude", candidate.get("longitude"))):
                if value and not getattr(merchant, field):
                    setattr(merchant, field, value)
            # Status may strengthen, never silently weaken.
            if status == VERIFIED:
                merchant.status = VERIFIED
            elif merchant.status not in (VERIFIED,):
                merchant.status = status
            merchant.entity_type = candidate["entity_type"]
            merchant.last_seen_at = now

        self.db.flush()

        for e in candidate["evidence"]:
            self.db.add(CompetitorObservation(
                merchant_id=merchant.id, market=market, query=effective_query,
                location_requested=location_requested,
                location_resolved=location_resolved,
                source_type=e["source_type"], source_url=e["source_url"],
                source_domain=e["source_domain"],
                discovery_method=e["discovery_method"],
                entity_type=e["entity_type"],
                match_method=e["match_method"],
                match_confidence=e["match_confidence"],
                status=status, reason=reason or e["classification_reason"],
                position=e["position"], rating=e["rating"], reviews=e["reviews"],
                title=e["title"], snippet=e["snippet"]))

        competitor.id = merchant.id
        competitor.city = merchant.city
        competitor.state = merchant.state
        competitor.country = merchant.country
        competitor.latitude = merchant.latitude
        competitor.longitude = merchant.longitude
        competitor.first_seen_at = merchant.created_at
        return competitor, is_new

    # ------------------------------------------------------------------
    # Saved competitors
    # ------------------------------------------------------------------
    def list_saved(self, market: Optional[str] = None,
                   location_resolved: Optional[str] = None,
                   status: Optional[str] = None,
                   limit: int = 100) -> Tuple[int, List[Competitor]]:
        query = self.db.query(Merchant)
        if status:
            query = query.filter(Merchant.status == status)
        if market or location_resolved:
            query = query.join(
                CompetitorObservation,
                CompetitorObservation.merchant_id == Merchant.id)
            if market:
                query = query.filter(CompetitorObservation.market == market)
            if location_resolved:
                query = query.filter(
                    CompetitorObservation.location_resolved == location_resolved)
            query = query.distinct()

        total = query.count()
        rows = query.order_by(Merchant.last_seen_at.desc().nullslast(),
                             Merchant.id.desc()).limit(limit).all()
        return total, [self._to_schema(m, with_evidence=False) for m in rows]

    def get_saved(self, merchant_id: int) -> Optional[Competitor]:
        merchant = self.db.query(Merchant).filter(Merchant.id == merchant_id).first()
        if merchant is None:
            return None
        return self._to_schema(merchant, with_evidence=True)

    def _to_schema(self, merchant: Merchant, with_evidence: bool) -> Competitor:
        observations = self.db.query(CompetitorObservation).filter(
            CompetitorObservation.merchant_id == merchant.id).order_by(
            CompetitorObservation.observed_at.desc()).all()

        ratings = [o.rating for o in observations if o.rating is not None]
        reviews = [o.reviews for o in observations if o.reviews is not None]
        positions = [o.position for o in observations if o.position is not None]
        latest = observations[0] if observations else None

        # Discovery context, drawn from the observations rather than stored
        # twice. Order is newest-first and de-duplicated, so a business found
        # in several markets shows all of them without repetition.
        markets = _ordered_unique(o.market for o in observations)
        locations = _ordered_unique(
            o.location_resolved or o.location_requested for o in observations)
        sources = _ordered_unique(o.source_type for o in observations)
        methods = _ordered_unique(o.discovery_method for o in observations)

        return Competitor(
            id=merchant.id, name=merchant.name,
            normalized_name=merchant.normalized_name,
            domain=merchant.normalized_domain, website=merchant.website,
            address=merchant.address, city=merchant.city, state=merchant.state,
            country=merchant.country, latitude=merchant.latitude,
            longitude=merchant.longitude, place_id=merchant.place_id,
            status=merchant.status or DISCOVERED,
            entity_type=merchant.entity_type or "unknown",
            # "unmatched" means nothing to match against on first sight, which
            # reads as a failure; a first occurrence is "new".
            match_method=_display_match_method(latest.match_method if latest else None),
            match_confidence=latest.match_confidence if latest else "unmatched",
            status_reason=latest.reason if latest else None,
            rating=ratings[0] if ratings else None,
            reviews=reviews[0] if reviews else None,
            best_position=min(positions) if positions else None,
            market=markets[0] if markets else None,
            location_requested=latest.location_requested if latest else None,
            location_resolved=locations[0] if locations else None,
            markets=markets, locations=locations,
            discovery_sources=sources, discovery_methods=methods,
            has_location_evidence=bool(
                merchant.address or merchant.latitude is not None),
            first_seen_at=merchant.created_at, last_seen_at=merchant.last_seen_at,
            evidence_count=len(observations),
            evidence=[
                CompetitorEvidence(
                    source_type=o.source_type, source_url=o.source_url,
                    source_domain=o.source_domain,
                    discovery_method=o.discovery_method,
                    entity_type=o.entity_type, observed_at=o.observed_at,
                    match_method=o.match_method,
                    match_confidence=o.match_confidence, status=o.status,
                    reason=o.reason, position=o.position, rating=o.rating,
                    reviews=o.reviews, title=o.title, snippet=o.snippet)
                for o in observations] if with_evidence else [])
