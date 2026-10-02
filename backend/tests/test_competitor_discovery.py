"""Competitor discovery end to end, offline.

Drives the real ``CompetitorService`` over the real ``SerpApiOrganicService``
and the real ``ApiBudgetManager``, with only the SerpApi client and the location
catalogue stubbed. That combination is deliberate: the provider-error contract
and the cache both live in the budget manager, and a fake would let them drift.

Markets are generic (coffee shops, automotive repair, fitness centres) so no
test can become dependent on one industry.
"""
import pytest
from unittest.mock import patch
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.models.competitor import CompetitorObservation
from app.models.merchant import Merchant
from app.services.competitor_service import CompetitorService
from app.services.location_service import LocationResolutionError
from app.services.serpapi_organic_service import (
    SerpApiOrganicService, SerpApiProviderError,
)

from tests.stubs import StubResolver, no_account


@pytest.fixture
def db():
    """Empty cache and empty competitor tables per test.

    The response cache is persistent by design, so without clearing it a test
    would be served the previous test's payload under the same key.
    """
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    session.execute(text("DELETE FROM search_cache"))
    session.execute(text("DELETE FROM competitor_observations"))
    session.execute(text("DELETE FROM merchants"))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def service(db):
    organic = SerpApiOrganicService(api_key="test_key", db=db,
                                   resolver=StubResolver(),
                                   account_fetcher=no_account)
    return CompetitorService(db=db, organic_service=organic)


def local(title, website="", address="1 Main St", place_id="p1",
          rating=None, reviews=None, position=1):
    return {"title": title, "website": website, "address": address,
            "place_id": place_id, "rating": rating, "reviews": reviews,
            "position": position}


def organic(title, link, snippet="", position=1):
    return {"title": title, "link": link, "snippet": snippet,
            "position": position, "displayed_link": link, "domain": None}


def run(service, local_results=(), organic_results=(), market="Coffee Shops",
        query="coffee shops", location="Austin, Texas", fail=False):
    payload = {"local_results": list(local_results),
               "organic_results": list(organic_results)}
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        if fail:
            MockSearch.return_value.get_dict.side_effect = RuntimeError("provider down")
        else:
            MockSearch.return_value.get_dict.return_value = payload
        return service.discover(market=market, query=query, location=location)


def stage(result, name):
    return next((s for s in result.stages if s.stage == name), None)


# ------------------------------------------------------------ location reuse
def test_location_resolution_reuses_the_shared_resolver(service):
    result = run(service, local_results=[local("Bean & Brew", "https://beanandbrew.com")])
    assert result.location_requested == "Austin, Texas"
    assert result.location_resolved == "Austin,Texas,United States"
    assert stage(result, "location_resolution").status == "ok"


def test_no_second_location_resolver_exists():
    """Spec: the audited resolver must be the only one."""
    import inspect
    from app.services import competitor_service

    source = inspect.getsource(competitor_service)
    assert "locations.json" not in source
    assert "class LocationResolver" not in source


def test_unresolvable_location_is_not_an_empty_competitor_list(service):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        with pytest.raises(LocationResolutionError):
            service.discover(market="Coffee Shops", query="coffee shops",
                             location="Zzzqqxinvalidplace")
        # No credit risked on a request the provider would have rejected.
        assert MockSearch.call_count == 0


# ------------------------------------------------------------ discovery
def test_local_business_becomes_a_verified_competitor(service):
    result = run(service, local_results=[
        local("Bean & Brew", "https://beanandbrew.com", rating=4.5, reviews=120)])

    assert result.competitors_verified == 1
    competitor = result.competitors[0]
    assert competitor.name == "Bean & Brew"
    assert competitor.domain == "beanandbrew.com"
    assert competitor.status == "verified"
    assert competitor.rating == 4.5 and competitor.reviews == 120
    assert competitor.evidence[0].source_type == "local"
    assert competitor.evidence[0].discovery_method == "google_maps_local"


def test_organic_only_business_is_discovered_not_verified(service):
    """Organic evidence alone is weaker than a structured local result."""
    result = run(service, organic_results=[
        organic("Iron Works Fitness", "https://ironworksfitness.com/")])

    assert result.competitors_verified == 0
    assert result.competitors_discovered == 1
    competitor = result.competitors[0]
    assert competitor.status == "discovered"
    assert competitor.status_reason == "organic_only_evidence"
    assert competitor.evidence[0].source_type == "organic"


def test_organic_corroborated_by_local_is_verified(service):
    """The same domain from two independent sources is strong evidence."""
    result = run(service,
                 local_results=[local("City Auto", "https://cityauto.com")],
                 organic_results=[organic("City Auto - Brakes",
                                          "https://cityauto.com/services/brakes")])

    assert len(result.competitors) == 1, "one business, not two"
    assert result.competitors[0].status == "verified"


def test_irrelevant_results_are_rejected_not_counted_as_competitors(service):
    result = run(service, organic_results=[
        organic("TOP 10 BEST Coffee Shops near Austin", "https://m.yelp.com/search"),
        organic("Bean & Brew | Facebook", "https://facebook.com/beanandbrew"),
        organic("Espresso Machine", "https://amazon.com/dp/B01"),
        organic("The 12 best cafes", "https://www.timeout.com/austin/cafes"),
        organic("Real Business", "https://realbusiness.com/"),
    ])

    assert len(result.competitors) == 1
    assert result.competitors[0].name == "Real Business"
    assert result.rejected_non_business == 4
    kinds = {r.entity_type for r in result.rejected_results}
    assert kinds == {"directory", "social", "marketplace", "article"}


def test_rejected_results_are_retained_for_transparency(service):
    result = run(service, organic_results=[
        organic("Best 10 gyms", "https://m.yelp.com/search")])
    assert result.organic_results_found == 1
    assert len(result.rejected_results) == 1
    assert result.rejected_results[0].reason == "directory_platform"


# ------------------------------------------------------------ identity / dedup
def test_same_company_across_sources_is_one_competitor(service):
    result = run(service,
                 local_results=[local("Bean & Brew", "https://beanandbrew.com")],
                 organic_results=[
                     organic("Bean & Brew Coffee", "https://beanandbrew.com/"),
                     organic("Bean & Brew - Menu", "https://beanandbrew.com/menu"),
                 ])

    assert len(result.competitors) == 1
    assert result.duplicates_merged == 2
    assert result.competitors[0].evidence_count == 3


def test_exact_domain_identity_merges_differently_named_results(service):
    """Domain is the strongest tier, so it wins over a differing title."""
    result = run(service,
                 local_results=[local("City Auto Repair", "https://cityauto.com")],
                 organic_results=[organic("Welcome | CityAuto",
                                          "https://cityauto.com/")])
    assert len(result.competitors) == 1
    assert result.competitors[0].domain == "cityauto.com"


def test_exact_name_identity_merges_when_domain_is_absent(service):
    result = run(service,
                 local_results=[local("Iron Works Fitness", website="",
                                      place_id="pid-1")],
                 organic_results=[organic("Iron Works Fitness",
                                          "https://ironworksfitness.com/")])
    assert len(result.competitors) == 1
    competitor = result.competitors[0]
    # The local result identified it; the organic result supplied the domain.
    assert competitor.place_id == "pid-1"
    assert competitor.domain == "ironworksfitness.com"


def test_distinct_businesses_are_not_merged(service):
    result = run(service, local_results=[
        local("Bean & Brew", "https://beanandbrew.com", place_id="p1"),
        local("Iron Works Fitness", "https://ironworksfitness.com", place_id="p2"),
    ])
    assert len(result.competitors) == 2


def test_ambiguous_chain_identity_stays_uncertain(service):
    """Two stores of one chain: an organic row cannot say which is which."""
    result = run(service, local_results=[
        local("Chain Cafe", "https://chaincafe.com", address="1 A St", place_id="p1"),
        local("Chain Cafe", "https://chaincafe.com", address="2 B St", place_id="p2"),
    ])
    # The second local row resolves ambiguously against the first.
    assert any(c.status == "uncertain" for c in result.competitors) or \
        len(result.competitors) == 1
    assert all(c.status != "verified" or c.place_id for c in result.competitors)


def test_uncertain_is_never_silently_promoted_to_verified(service):
    result = run(service, organic_results=[
        organic("Some Shop", "https://somesite.com/a/b/c/d/e")])
    # Unclassifiable, so not a competitor at all rather than a verified one.
    assert result.competitors == []
    assert result.rejected_non_business == 1


# ------------------------------------------------------------ provider status
def test_provider_failure_is_not_zero_competitors(service):
    """Spec: a provider error must never read as "no competitors found"."""
    with pytest.raises(SerpApiProviderError) as excinfo:
        run(service, fail=True)
    assert "provider down" in str(excinfo.value)


def test_genuinely_empty_search_is_no_results(service):
    result = run(service, local_results=[], organic_results=[])
    assert result.provider_status == "no_results"
    assert result.competitors == []
    assert result.local_results_found == 0
    assert result.organic_results_found == 0


def test_results_present_reports_success(service):
    result = run(service, local_results=[local("Bean & Brew", "https://b.com")])
    assert result.provider_status == "success"


# ------------------------------------------------------------ cache
def test_second_identical_search_is_a_cache_hit(service):
    payload = {"local_results": [local("Bean & Brew", "https://beanandbrew.com")],
               "organic_results": []}
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = payload
        first = service.discover(market="Coffee Shops", query="coffee shops",
                                 location="Austin, Texas")
        second = service.discover(market="Coffee Shops", query="coffee shops",
                                  location="Austin, Texas")
        assert MockSearch.return_value.get_dict.call_count == 1

    assert first.cache_hit is False
    assert second.cache_hit is True


def test_different_location_does_not_reuse_cached_competitors(service, db):
    """Spec 14: a materially different request must not share a response."""
    seen = []
    from app.services import api_budget as ab
    original = ab.ApiBudgetManager.execute_search

    def recording(self, cache_key, params, endpoint, domain=""):
        seen.append(cache_key)
        return original(self, cache_key, params, endpoint, domain)

    payload = {"local_results": [local("Bean & Brew", "https://beanandbrew.com")],
               "organic_results": []}
    with patch.object(ab.ApiBudgetManager, "execute_search", recording), \
            patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = payload
        service.discover(market="Coffee Shops", query="coffee shops",
                         location="Austin, Texas")
        service.discover(market="Coffee Shops", query="coffee shops",
                         location="Hyderabad")
        assert MockSearch.return_value.get_dict.call_count == 2

    assert len(seen) == 2 and seen[0] != seen[1]
    assert "Austin,Texas,United States" in seen[0]
    assert "Hyderabad,Telangana,India" in seen[1]


def test_different_query_does_not_reuse_cached_competitors(service):
    payload = {"local_results": [], "organic_results": []}
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = payload
        service.discover(market="Coffee Shops", query="coffee shops",
                         location="Austin, Texas")
        service.discover(market="Automotive Repair", query="automotive repair",
                         location="Austin, Texas")
        assert MockSearch.return_value.get_dict.call_count == 2


# ------------------------------------------------------------ persistence
def test_competitor_is_saved_with_its_evidence(service, db):
    run(service, local_results=[
        local("Bean & Brew", "https://beanandbrew.com", rating=4.6)])

    merchant = db.query(Merchant).one()
    assert merchant.normalized_domain == "beanandbrew.com"
    assert merchant.status == "verified"
    assert merchant.entity_type == "business"
    assert merchant.last_seen_at is not None

    observation = db.query(CompetitorObservation).one()
    assert observation.merchant_id == merchant.id
    assert observation.market == "Coffee Shops"
    assert observation.location_resolved == "Austin,Texas,United States"
    assert observation.source_type == "local"
    assert observation.discovery_method == "google_maps_local"
    assert observation.source_url == "https://beanandbrew.com"
    assert observation.observed_at is not None


def test_rediscovery_does_not_duplicate_the_business(service, db):
    for _ in range(2):
        run(service, local_results=[local("Bean & Brew", "https://beanandbrew.com")])

    assert db.query(Merchant).count() == 1, "one business row"
    # Each discovery is its own evidence, so history accumulates.
    assert db.query(CompetitorObservation).count() == 2


def test_rediscovery_fills_gaps_without_erasing_known_values(service, db):
    run(service, local_results=[local("Bean & Brew", website="", place_id="p9")])
    run(service, market="Cafes", query="cafes near me",
        local_results=[local("Bean & Brew", "https://beanandbrew.com",
                             place_id="p9")])

    merchant = db.query(Merchant).one()
    assert merchant.place_id == "p9"
    assert merchant.normalized_domain == "beanandbrew.com"


def test_saved_listing_and_detail(service, db):
    run(service, local_results=[
        local("Bean & Brew", "https://beanandbrew.com", place_id="p1"),
        local("Cafe Two", "https://cafetwo.com", place_id="p2"),
    ])

    total, competitors = service.list_saved()
    assert total == 2
    assert {c.name for c in competitors} == {"Bean & Brew", "Cafe Two"}
    # The list view omits evidence; the detail view carries it.
    assert all(c.evidence == [] for c in competitors)

    detail = service.get_saved(competitors[0].id)
    assert detail.evidence_count >= 1
    assert detail.evidence[0].source_type == "local"
    assert service.get_saved(999999) is None


def test_saved_listing_filters_by_market_and_status(service, db):
    run(service, market="Coffee Shops", query="coffee shops",
        local_results=[local("Bean & Brew", "https://beanandbrew.com", place_id="p1")])
    run(service, market="Automotive Repair", query="automotive repair",
        local_results=[local("City Auto", "https://cityauto.com", place_id="p2")])

    total, competitors = service.list_saved(market="Coffee Shops")
    assert total == 1 and competitors[0].name == "Bean & Brew"

    total, _ = service.list_saved(status="verified")
    assert total == 2
    total, _ = service.list_saved(status="uncertain")
    assert total == 0


def test_listing_reads_the_database_without_a_provider(db):
    """Saved competitors must be readable with no provider configured at all."""
    service = CompetitorService(db=db, organic_service=None)
    total, competitors = service.list_saved()
    assert total == 0 and competitors == []


# ------------------------------------------------------------ inputs
def test_market_is_used_when_no_query_is_given(service):
    result = run(service, market="Fitness Centres", query="",
                 local_results=[local("Iron Works", "https://ironworks.com")])
    assert result.effective_query == "Fitness Centres"


def test_empty_market_and_query_is_rejected(service):
    with pytest.raises(ValueError):
        service.discover(market="", query="", location="Austin, Texas")


def test_provider_coordinates_are_recorded_not_discarded(service, db):
    """The provider reports coordinates for a place; keeping them is free."""
    row = local("Bean & Brew", "https://beanandbrew.com", place_id="p1")
    payload = {"local_results": [dict(row, gps_coordinates={
        "latitude": 30.2672, "longitude": -97.7431})], "organic_results": []}
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = payload
        result = service.discover(market="Coffee Shops", query="coffee shops",
                                  location="Austin, Texas")

    merchant = db.query(Merchant).one()
    assert merchant.latitude == pytest.approx(30.2672)
    assert merchant.longitude == pytest.approx(-97.7431)
    assert result.competitors[0].latitude == pytest.approx(30.2672)


def test_missing_coordinates_stay_null(service, db):
    """Nothing is invented when the provider reports no coordinates."""
    run(service, local_results=[local("Bean & Brew", "https://beanandbrew.com")])
    merchant = db.query(Merchant).one()
    assert merchant.latitude is None and merchant.longitude is None


def test_platform_website_is_not_recorded_as_the_business_domain(service, db):
    """A social page is evidence a business exists, not the business's domain.

    Observed live: a small garage listed its Instagram page as its website, so
    "instagram.com" became its identity domain -- which would make every other
    business doing the same collide on the exact-domain tier and merge.
    """
    result = run(service, local_results=[
        local("Meherun Motors", "https://www.instagram.com/meherunmotors",
              place_id="p1")])

    competitor = result.competitors[0]
    assert competitor.domain is None, "a platform domain is not an identity"
    # The URL itself is still kept as evidence.
    assert competitor.evidence[0].source_url.endswith("meherunmotors")
    # A place id is still strong identity, so the status is unaffected.
    assert competitor.status == "verified"


def test_two_businesses_sharing_a_platform_page_do_not_merge(service, db):
    """The collision the fix above prevents."""
    result = run(service, local_results=[
        local("Garage One", "https://www.instagram.com/garageone", place_id="p1"),
        local("Garage Two", "https://www.instagram.com/garagetwo", place_id="p2"),
    ])

    assert len(result.competitors) == 2
    assert db.query(Merchant).count() == 2
    assert all(c.domain is None for c in result.competitors)


def test_a_real_business_domain_is_still_recorded(service):
    result = run(service, local_results=[
        local("Addons Automotive", "https://addonsautomotive.in", place_id="p1")])
    assert result.competitors[0].domain == "addonsautomotive.in"
