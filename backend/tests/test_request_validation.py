"""An unusable request must not persist anything.

Discovery is not a read: it writes businesses into the shared ``merchants``
table and observations against them, and every later module inherits whatever
lands there. So a request that cannot produce meaningful evidence has to be
rejected *before* anything is searched or written -- returning an empty result
is not enough.

The case that prompted this: a diagnostic probe of
``/api/competitors/search?market=x`` with no location ran an unscoped global
search for "x" and persisted a government space-weather page as a competitor.

Two independent gaps produced it, and both are covered here:

1. no location was required, so the search had no geographic scoping at all;
2. the classifier read a government URL's shallow path as a business homepage.
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine, get_db
from app.main import app
from app.models.competitor import CompetitorObservation
from app.models.merchant import Merchant
from app.models.product_observation import ProductObservation
from app.routes.competitors import get_competitor_service
from app.routes.products import get_product_service
from app.services.competitor_service import (
    CompetitorService, validate_discovery_request,
)
from app.services.product_service import ProductService
from app.services.result_classifier import (
    BUSINESS, classify_organic_result, is_non_commercial_domain,
)
from app.services.serpapi_organic_service import SerpApiOrganicService

from tests.stubs import StubResolver, no_account


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for table in ("search_cache", "product_observations",
                  "competitor_observations", "merchants"):
        session.execute(text("DELETE FROM " + table))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def competitor_service(db):
    organic = SerpApiOrganicService(api_key="test_key", db=db,
                                   resolver=StubResolver(),
                                   account_fetcher=no_account)
    return CompetitorService(db=db, organic_service=organic)


@pytest.fixture
def client(db, competitor_service):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_competitor_service] = lambda: competitor_service
    app.dependency_overrides[get_product_service] = lambda: ProductService(
        db=db, competitor_service=competitor_service)
    yield TestClient(app)
    app.dependency_overrides.clear()


def nothing_persisted(db) -> bool:
    return (db.query(Merchant).count() == 0
            and db.query(CompetitorObservation).count() == 0
            and db.query(ProductObservation).count() == 0)


# ============================================================ the exact case
def test_the_observed_diagnostic_request_is_now_rejected(client, db):
    """?market=x with no location -- the request that created the artifact."""
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        response = client.get("/api/competitors/search", params={"market": "x"})
        assert MockSearch.call_count == 0, "no search may run"

    assert response.status_code == 400
    assert nothing_persisted(db), "an unusable request must persist nothing"


def test_a_government_page_is_not_a_competitor():
    """The second half of the root cause, independent of validation.

    Even for a perfectly valid search, a government namespace is not a
    business competing in a market.
    """
    verdict = classify_organic_result(
        "GOES X-ray Flux",
        "http://www.spaceweather.gov/products/goes-x-ray-flux")
    assert verdict.entity_type != BUSINESS
    assert verdict.reason == "non_commercial_domain"
    assert not verdict.is_competitor_candidate


@pytest.mark.parametrize("domain, expected", [
    ("spaceweather.gov", True),
    ("www.spaceweather.gov", True),
    ("x.gov.uk", True),
    ("army.mil", True),
    ("defence.mil.au", True),
    ("a.b.defence.mil.au", True),
    # Ordinary commercial domains that merely contain the letters.
    ("mil.com", False),
    ("govinda.com", False),
    ("government-supplies.com", False),
    ("beanandbrew.example", False),
    ("", False),
])
def test_non_commercial_namespace_detection(domain, expected):
    assert is_non_commercial_domain(domain) is expected


def test_a_government_result_is_still_reported_as_rejected(competitor_service, db):
    """Rejected, not silently dropped: the funnel must stay honest."""
    payload = {"local_results": [], "organic_results": [
        {"title": "GOES X-ray Flux",
         "link": "http://www.spaceweather.gov/products/goes-x-ray-flux",
         "snippet": "solar activity", "position": 6}]}
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = payload
        result = competitor_service.discover(
            market="Coffee Shops", query="coffee shops", location="Austin, Texas")

    assert result.competitors == []
    assert result.rejected_non_business == 1
    assert result.rejected_results[0].reason == "non_commercial_domain"
    assert db.query(Merchant).count() == 0


# ============================================================ validation unit
@pytest.mark.parametrize("market, query, location, fragment", [
    ("", "", "Austin, Texas", "market/industry or a search query"),
    ("   ", "   ", "Austin, Texas", "market/industry or a search query"),
    ("x", "", "Austin, Texas", "too short"),
    ("1", "", "Austin, Texas", "too short"),
    ("?", "", "Austin, Texas", "too short"),
    ("12", "", "Austin, Texas", "too short"),
    ("Coffee Shops", "", "", "location is required"),
    ("Coffee Shops", "", "   ", "location is required"),
    ("Coffee Shops", "", None, "location is required"),
])
def test_unusable_requests_are_rejected(market, query, location, fragment):
    with pytest.raises(ValueError) as excinfo:
        validate_discovery_request(market, query, location)
    assert fragment in str(excinfo.value)


@pytest.mark.parametrize("market, query, location", [
    ("Coffee Shops", "", "Austin, Texas"),
    ("", "automotive repair", "Hyderabad"),
    # Short but genuine markets must still pass: no industry list exists.
    ("AI", "", "Austin, Texas"),
    ("IT", "", "Austin, Texas"),
])
def test_valid_requests_are_accepted(market, query, location):
    assert validate_discovery_request(market, query, location)


def test_validation_holds_no_list_of_acceptable_industries():
    """Validation must stay structural; MarketRadar is industry-agnostic."""
    import ast
    import inspect
    from app.services import competitor_service

    source = inspect.getsource(competitor_service.validate_discovery_request)
    tree = ast.parse(source.strip())
    literals = [n.value.lower() for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    for forbidden in ("coffee", "wine", "retail", "automotive", "fitness",
                      "grocery", "electronics"):
        assert not any(forbidden in lit for lit in literals), \
            forbidden + " appears in validation"


# ============================================================ API surface
@pytest.mark.parametrize("params", [
    {"market": "x", "location": "Austin, Texas"},
    {"market": "Coffee Shops"},                       # no location
    {"location": "Austin, Texas"},                    # no market or query
    {},
])
def test_competitor_search_rejects_unusable_requests(client, db, params):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        response = client.get("/api/competitors/search", params=params)
        assert MockSearch.call_count == 0

    assert response.status_code == 400
    assert response.json()["detail"]
    assert nothing_persisted(db)


@pytest.mark.parametrize("params", [
    {"q": "x", "location": "Austin, Texas"},
    {"q": "Widget 2000"},                             # no location
    {"location": "Austin, Texas"},                    # no product
    {},
])
def test_product_search_rejects_unusable_requests(client, db, params):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        response = client.get("/api/products/search", params=params)
        assert MockSearch.call_count == 0

    assert response.status_code == 400
    assert nothing_persisted(db)


def test_validation_precedes_location_resolution(client, db):
    """A too-short market fails as 400, not 422: the query is the problem."""
    response = client.get("/api/competitors/search",
                          params={"market": "x", "location": "Zzzqqxinvalidplace"})
    assert response.status_code == 400


# ============================================================ later gates
def test_an_unresolvable_location_persists_nothing(client, db):
    """Resolution runs before the search, so a bad place writes nothing."""
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        response = client.get("/api/competitors/search", params={
            "market": "Coffee Shops", "location": "Zzzqqxinvalidplace"})
        assert MockSearch.call_count == 0

    assert response.status_code == 422
    assert nothing_persisted(db)


def test_a_provider_failure_persists_nothing(client, db):
    """502 means we never got an answer, so there is nothing to record."""
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.side_effect = RuntimeError("provider down")
        response = client.get("/api/competitors/search", params={
            "market": "Coffee Shops", "location": "Austin, Texas"})

    assert response.status_code == 502
    assert nothing_persisted(db)


def test_a_product_provider_failure_persists_nothing(client, db):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.side_effect = RuntimeError("provider down")
        response = client.get("/api/products/search", params={
            "q": "Widget 2000", "location": "Austin, Texas"})

    assert response.status_code == 502
    assert nothing_persisted(db)


def test_a_search_that_finds_nothing_persists_nothing(client, db):
    """An empty result is a valid answer, but there is no business to record."""
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = {
            "local_results": [], "organic_results": []}
        response = client.get("/api/competitors/search", params={
            "market": "Coffee Shops", "location": "Austin, Texas"})

    assert response.status_code == 200
    assert response.json()["provider_status"] == "no_results"
    assert nothing_persisted(db)


def test_a_valid_request_still_persists(client, db):
    """The gates must not have blocked legitimate discovery."""
    payload = {"local_results": [
        {"title": "Bean & Brew", "website": "https://beanandbrew.example",
         "place_id": "p1", "address": "1 Main St", "position": 1}],
        "organic_results": []}
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = payload
        response = client.get("/api/competitors/search", params={
            "market": "Coffee Shops", "location": "Austin, Texas"})

    assert response.status_code == 200
    assert db.query(Merchant).count() == 1
    assert db.query(CompetitorObservation).count() == 1


# ============================================================ products, in full
@pytest.mark.parametrize("q", ["x", "1", "?", "12", " ", ""])
def test_product_query_must_be_structurally_usable(client, db, q):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        response = client.get("/api/products/search",
                              params={"q": q, "location": "Austin, Texas"})
        assert MockSearch.call_count == 0

    assert response.status_code == 400
    assert nothing_persisted(db)


@pytest.mark.parametrize("q", ["AI", "IT", "Widget 2000"])
def test_short_but_genuine_product_queries_are_accepted(client, db, q):
    """No list of acceptable products exists, so "AI" must pass."""
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = {
            "local_results": [], "organic_results": []}
        response = client.get("/api/products/search",
                              params={"q": q, "location": "Austin, Texas"})

    assert response.status_code == 200


def test_product_search_with_an_invalid_location_is_422(client, db):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        response = client.get("/api/products/search", params={
            "q": "Widget 2000", "location": "Zzzqqxinvalidplace"})
        assert MockSearch.call_count == 0

    assert response.status_code == 422
    assert nothing_persisted(db)


def test_product_search_with_no_merchants_is_no_results(client, db):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = {
            "local_results": [], "organic_results": []}
        response = client.get("/api/products/search", params={
            "q": "Widget 2000", "location": "Austin, Texas"})

    assert response.status_code == 200
    body = response.json()
    assert body["provider_status"] == "no_results"
    assert body["merchants_considered"] == 0
    assert nothing_persisted(db)


def test_a_valid_product_search_persists_its_observation(client, db):
    """Positive control: the gates must not block legitimate discovery."""
    merchant_row = {"title": "Rivertown Supply", "website": "https://rivertown.example",
                    "place_id": "p1", "address": "1 Main St", "position": 1}
    product_row = {"title": "Widget 2000",
                   "link": "https://rivertown.example/product/widget-2000",
                   "snippet": "Widget 2000 $10.00", "position": 1}

    def router(params):
        q = params.get("q", "")

        class Search:
            @staticmethod
            def get_dict():
                if q.startswith("site:"):
                    return {"organic_results": [product_row]}
                return {"local_results": [merchant_row], "organic_results": []}

        return Search()

    with patch("app.services.api_budget.GoogleSearch", side_effect=router):
        response = client.get("/api/products/search", params={
            "q": "Widget 2000", "market": "Hardware", "location": "Austin, Texas"})

    assert response.status_code == 200
    assert response.json()["products_found"] == 1
    assert db.query(ProductObservation).count() == 1
    assert db.query(Merchant).count() == 1


# ============================================================ nested namespaces
@pytest.mark.parametrize("host", [
    "spaceweather.gov",
    "www.spaceweather.gov",
    "data.services.spaceweather.gov",     # nested government host
    "some.agency.gov.uk",                 # nested, country-coded
    "army.mil",
    "www.army.mil",
    "logistics.eastern.defence.mil.au",   # nested military host
])
def test_nested_government_and_military_hosts_are_non_commercial(host):
    assert is_non_commercial_domain(host) is True


@pytest.mark.parametrize("host", [
    # A name that merely contains the letters is an ordinary business.
    "mil.com",
    "govinda.com",
    "government-supplies.com",
    "governor-hotel.co.uk",
    "milford-motors.com",
    "thegovshop.example",
    "millers-coffee.com",
])
def test_commercial_domains_containing_those_words_are_unaffected(host):
    assert is_non_commercial_domain(host) is False
    # And they must still be able to classify as a business.
    verdict = classify_organic_result("Some Business", "https://" + host + "/")
    assert verdict.entity_type == BUSINESS
