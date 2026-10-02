"""Competitor identity and discovery-context integrity.

Every test here exists because of something observed in the running
application, not because of a hypothetical. The recurring theme is that
evidence must never be promoted into identity: a platform page proves a
business exists, an organic result proves a website exists, and neither proves
where a business is or which domain it owns.
"""
import pytest
from unittest.mock import patch
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.models.competitor import CompetitorObservation
from app.models.merchant import Merchant
from app.services.competitor_service import CompetitorService
from app.services.result_classifier import is_platform_domain
from app.services.serpapi_organic_service import SerpApiOrganicService

from tests.stubs import StubResolver, no_account


@pytest.fixture
def db():
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
          rating=None, reviews=None, position=1, gps=None):
    row = {"title": title, "website": website, "address": address,
           "place_id": place_id, "rating": rating, "reviews": reviews,
           "position": position}
    if gps:
        row["gps_coordinates"] = {"latitude": gps[0], "longitude": gps[1]}
    return row


def organic_row(title, link, snippet="", position=1):
    return {"title": title, "link": link, "snippet": snippet,
            "position": position}


def run(service, local_results=(), organic_results=(), market="Coffee Shops",
        query="coffee shops", location="Austin, Texas"):
    payload = {"local_results": list(local_results),
               "organic_results": list(organic_results)}
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = payload
        return service.discover(market=market, query=query, location=location)


# ============================================================ 1-3: platform URLs
@pytest.mark.parametrize("platform_url, platform", [
    ("https://www.instagram.com/meherun_motors?igshid=YmMyMTA2M2Y=", "instagram"),
    ("https://www.facebook.com/some-business-page", "facebook"),
    ("https://www.youtube.com/@somebusiness", "youtube"),
    ("https://m.yelp.com/biz/some-business", "yelp directory"),
    ("https://www.mapquest.com/us/somewhere/biz-123", "mapquest directory"),
    ("https://www.amazon.com/stores/somebrand", "amazon marketplace"),
])
def test_platform_url_never_becomes_the_merchant_domain(service, db,
                                                        platform_url, platform):
    """Observed live: a garage listed its Instagram page as its website.

    The URL is real evidence and is kept, but it is not a domain the business
    owns. Recording it as identity would make every business sharing that
    platform collide on the exact-domain tier and merge into one record.
    """
    result = run(service, local_results=[
        local("Some Business", platform_url, place_id="p1")])

    competitor = result.competitors[0]
    assert competitor.domain is None, platform + " became an identity domain"

    merchant = db.query(Merchant).one()
    assert merchant.normalized_domain is None, \
        platform + " was persisted as merchant.normalized_domain"

    # The URL survives as evidence, exactly as the spec requires.
    assert merchant.website == platform_url
    observation = db.query(CompetitorObservation).one()
    assert observation.source_url == platform_url


def test_no_saved_merchant_may_hold_a_platform_identity_domain(service, db):
    """A standing audit over whatever is persisted, not one fixed case."""
    run(service, local_results=[
        local("A", "https://www.instagram.com/a", place_id="p1"),
        local("B", "https://realbusiness.example", place_id="p2"),
        local("C", "https://www.facebook.com/c", place_id="p3"),
    ])

    for merchant in db.query(Merchant).all():
        assert not is_platform_domain(merchant.normalized_domain or ""), \
            merchant.name + " holds a platform domain as identity"


def test_businesses_sharing_a_platform_do_not_collide(service, db):
    result = run(service, local_results=[
        local("Garage One", "https://instagram.com/one", place_id="p1"),
        local("Garage Two", "https://instagram.com/two", place_id="p2"),
    ])
    assert len(result.competitors) == 2
    assert db.query(Merchant).count() == 2


# ============================================================ 4: local identity
def test_local_business_without_a_website_is_still_verified(service, db):
    """A reliable place id is strong identity on its own."""
    result = run(service, local_results=[
        local("Torque Auto", website="", place_id="strong-place-id")])

    competitor = result.competitors[0]
    assert competitor.status == "verified"
    assert competitor.domain is None
    assert competitor.place_id == "strong-place-id"


def test_local_business_with_a_platform_url_is_verified_via_place_id(service):
    """Meherun Motors exactly: verified, but not on the platform domain."""
    result = run(service, local_results=[
        local("Meherun Motors", "https://instagram.com/meherun_motors",
              place_id="pid-9")])
    competitor = result.competitors[0]
    assert competitor.status == "verified"
    assert competitor.status_reason is None
    assert competitor.domain is None


def test_local_business_with_neither_place_id_nor_domain_is_not_verified(service):
    result = run(service, local_results=[
        local("Nameless Shop", website="", place_id="")])
    competitor = result.competitors[0]
    assert competitor.status == "discovered"
    assert competitor.status_reason == "local_result_without_place_id_or_domain"


# ============================================================ 5: geography
def test_organic_business_without_geographic_evidence_stays_discovered(service):
    """Observed live: a Hampton Bays garage surfaced in a Hyderabad search."""
    result = run(service, organic_results=[
        organic_row("Plymouth Auto Repair - C & C Automotive Repair",
                    "https://www.cncautohamptonbays.net/vehicles/plymouth",
                    "Specialized Plymouth auto repair services in Hampton Bays, NY.")],
        market="Automotive Repair", query="automotive repair",
        location="Hyderabad")

    competitor = result.competitors[0]
    assert competitor.status == "discovered"
    assert competitor.status_reason == "organic_only_evidence"
    # Nothing is inferred about where it is.
    assert competitor.address is None
    assert competitor.latitude is None
    assert competitor.has_location_evidence is False


def test_location_evidence_flag_is_true_only_when_a_provider_supplied_it(service):
    result = run(service, local_results=[
        local("Bean & Brew", "https://beanandbrew.com", address="1 Main St",
              place_id="p1", gps=(30.2672, -97.7431))])
    assert result.competitors[0].has_location_evidence is True


def test_geography_is_never_inferred_from_a_domain(service):
    """A country-coded domain must not imply a location."""
    result = run(service, organic_results=[
        organic_row("Addons Automotive", "https://addonsautomotive.in/")],
        market="Automotive Repair", location="Hyderabad")
    competitor = result.competitors[0]
    assert competitor.address is None
    assert competitor.latitude is None and competitor.longitude is None
    assert competitor.has_location_evidence is False


# ============================================================ 6: context
def test_saved_competitors_retain_market_and_location_context(service, db):
    run(service, market="Coffee Shops", query="coffee shops",
        location="Austin, Texas",
        local_results=[local("Bean & Brew", "https://beanandbrew.com", place_id="p1")])

    _, competitors = service.list_saved()
    competitor = competitors[0]
    assert competitor.markets == ["Coffee Shops"]
    assert competitor.locations == ["Austin,Texas,United States"]
    assert competitor.market == "Coffee Shops"
    assert competitor.location_resolved == "Austin,Texas,United States"


def test_a_business_found_in_two_markets_keeps_both(service, db):
    """History accumulates; a later search does not overwrite an earlier one."""
    run(service, market="Coffee Shops", query="coffee shops",
        location="Austin, Texas",
        local_results=[local("Bean & Brew", "https://beanandbrew.com", place_id="p1")])
    run(service, market="Cafes", query="cafes", location="Hyderabad",
        local_results=[local("Bean & Brew", "https://beanandbrew.com", place_id="p1")])

    _, competitors = service.list_saved()
    assert len(competitors) == 1, "still one business"
    competitor = competitors[0]
    assert set(competitor.markets) == {"Coffee Shops", "Cafes"}
    assert set(competitor.locations) == {"Austin,Texas,United States",
                                         "Hyderabad,Telangana,India"}


# ============================================================ 7: no overwriting
def test_different_searches_do_not_overwrite_observations(service, db):
    run(service, market="Coffee Shops", query="coffee shops",
        location="Austin, Texas",
        local_results=[local("Bean & Brew", "https://beanandbrew.com", place_id="p1")])
    run(service, market="Cafes", query="cafes", location="Hyderabad",
        local_results=[local("Bean & Brew", "https://beanandbrew.com", place_id="p1")])

    observations = db.query(CompetitorObservation).all()
    assert len(observations) == 2
    assert {o.market for o in observations} == {"Coffee Shops", "Cafes"}


# ============================================================ 8: dedup
def test_same_merchant_across_searches_deduplicates(service, db):
    for _ in range(3):
        run(service, local_results=[
            local("Bean & Brew", "https://beanandbrew.com", place_id="p1")])

    assert db.query(Merchant).count() == 1
    assert db.query(CompetitorObservation).count() == 3
    _, competitors = service.list_saved()
    assert competitors[0].evidence_count == 3


# ============================================================ 9: source label
def test_source_comes_from_the_discovery_method_not_a_persistence_state(service, db):
    run(service,
        local_results=[local("Bean & Brew", "https://beanandbrew.com", place_id="p1")],
        organic_results=[organic_row("Bean & Brew - Menu",
                                     "https://beanandbrew.com/menu")])

    _, competitors = service.list_saved()
    competitor = competitors[0]
    assert competitor.discovery_sources == ["local", "organic"]
    assert competitor.discovery_methods == ["google_maps_local", "google_organic"]
    # "recorded"/"saved" describe persistence, never discovery.
    assert "recorded" not in competitor.discovery_sources
    assert "saved" not in competitor.discovery_sources


def test_organic_only_business_reports_only_organic(service, db):
    run(service, organic_results=[
        organic_row("Iron Works Fitness", "https://ironworksfitness.com/")])
    _, competitors = service.list_saved()
    assert competitors[0].discovery_methods == ["google_organic"]


def test_first_sighting_reports_new_rather_than_unmatched(service, db):
    """"unmatched" reads as a failed match; a first sighting is simply new."""
    run(service, local_results=[
        local("Bean & Brew", "https://beanandbrew.com", place_id="p1")])
    _, competitors = service.list_saved()
    assert competitors[0].match_method == "new"


# ============================================================ standing audit
def test_every_verified_record_satisfies_the_strong_evidence_rule(service, db):
    """Runs over whatever the pipeline persisted, not a fixed expectation."""
    run(service, market="Coffee Shops", location="Austin, Texas",
        local_results=[
            local("With Domain", "https://withdomain.example", place_id="p1"),
            local("Place Id Only", website="", place_id="p2"),
            local("Platform Only", "https://instagram.com/x", place_id="p3"),
        ],
        organic_results=[
            organic_row("Organic Only", "https://organiconly.example/"),
        ])

    for merchant in db.query(Merchant).all():
        if merchant.status != "verified":
            continue
        assert not is_platform_domain(merchant.normalized_domain or ""), \
            merchant.name + " is verified on a platform domain"
        assert merchant.place_id or merchant.normalized_domain, \
            merchant.name + " is verified with neither place id nor domain"
        assert merchant.entity_type == "business", \
            merchant.name + " is verified but is not a business"


# ============================================================ reference business
def test_no_business_is_special_cased_anywhere(service, db):
    """Discovery must stay industry- and company-agnostic.

    A "that's our own shop, not a competitor" exclusion is a real need, but it
    can only be met by a tracked/reference-business capability -- never by
    naming a company in the code.
    """
    import ast
    import inspect
    from app.services import competitor_service, result_classifier

    for module in (competitor_service, result_classifier):
        tree = ast.parse(inspect.getsource(module))
        literals = " ".join(
            n.value.lower() for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str))
        for name in ("wine outlet", "total wine", "hazlet", "buy rite",
                     "meherun", "torque auto", "addons", "cenizo"):
            assert name not in literals, \
                name + " is special-cased in " + module.__name__


def test_every_verified_business_is_treated_as_a_candidate(service, db):
    """Documents today's behaviour, so a future change to it is deliberate.

    Price Intelligence has a partial reference-business notion
    (``reference_merchant_name``), but it is request-scoped, matched on a name
    string rather than merchant identity, and never persisted. Competitors has
    no equivalent, so every verified business -- including the user's own --
    is returned as a candidate.
    """
    result = run(service, local_results=[
        local("Our Own Shop", "https://ourownshop.example", place_id="p1"),
        local("A Rival", "https://arival.example", place_id="p2"),
    ])
    assert len(result.competitors) == 2
    assert all(c.status == "verified" for c in result.competitors)

    # No field exists today to mark one of them as the user's own business.
    from app.schemas.competitor import Competitor
    for field in ("is_reference", "is_own_business", "tracked"):
        assert field not in Competitor.model_fields


def test_price_intelligence_reference_store_is_not_shared_with_competitors():
    """The existing notion is request-scoped and name-based, not identity-based."""
    from app.models.merchant import Merchant

    for field in ("is_reference", "is_own_business", "tracked"):
        assert not hasattr(Merchant, field), \
            field + " exists on Merchant; update this documentation test"
