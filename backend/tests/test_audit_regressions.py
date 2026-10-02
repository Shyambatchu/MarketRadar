"""Regression tests for defects found in the 2026-10-02 pre-submission audit.

Each test reproduces one confirmed bug exactly as it was observed, so the
failure mode cannot quietly return. See docs/audit/.
"""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine, get_db
from app.main import app
from app.models.competitor import CompetitorObservation
from app.models.merchant import Merchant
from app.models.product_observation import ProductObservation
from app.models.serpapi_models import SearchCache
from app.services import api_budget
from app.services.analyst_service import validate_summary
from app.services.location_service import (
    LocationConflictError, LocationResolutionError, LocationResolver,
)
from app.services.product_identity import match_product
from app.services.pulse_service import MarketPulseService
from app.services.result_classifier import (
    BUSINESS, classify_local_result, classify_organic_result,
)
from app.services.serpapi_organic_service import SerpApiOrganicService
from app.services.trends_service import TrendsService

AUSTIN = "Austin,Texas,United States"
HOLMDEL = "Holmdel,New Jersey,United States"
BASE = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for table in ("product_observations", "competitor_observations", "merchants",
                  "search_cache", "api_usage", "serp_search_results",
                  "serp_local_results", "serp_searches"):
        session.execute(text("DELETE FROM " + table))
    session.commit()
    yield session
    session.close()


def merchant(db, name, domain=None):
    row = Merchant(name=name, normalized_name=name.lower().replace(" ", ""),
                   normalized_domain=domain, status="verified",
                   entity_type="business", address="1 Main St")
    db.add(row)
    db.commit()
    return row


def product_obs(db, m, price, location, market="Wine Retail", hours=0,
                status="found", price_status="verified", reason=None):
    db.add(ProductObservation(
        merchant_id=m.id, product_query="Widget", normalized_query="widget",
        market=market, location_resolved=location, product_name="Widget",
        product_status=status, price_status=price_status, price=price,
        verification_reason=reason, currency="USD" if price else None,
        evidence_scope="catalog", inventory_confirmed=False,
        observed_at=BASE + timedelta(hours=hours)))
    db.commit()


# ------------------------------------------------- SB-1: expired cache refresh
class _FakeSearch:
    calls = 0

    def __init__(self, params):
        _FakeSearch.calls += 1

    def get_dict(self):
        return {"organic_results": [{"title": "fresh"}]}


def test_an_expired_cache_row_is_refreshed_not_duplicated(db):
    """Observed: IntegrityError (500) after the credit was spent."""
    db.add(SearchCache(cache_key="k", response_data=json.dumps({"old": True}),
                       expires_at=datetime.now(timezone.utc) - timedelta(days=1)))
    db.commit()

    with patch.object(api_budget, "GoogleSearch", _FakeSearch):
        manager = api_budget.ApiBudgetManager(db, "test-key")
        result = manager.execute_search("k", {"q": "x"}, "google_organic")

    assert result == {"organic_results": [{"title": "fresh"}]}
    rows = db.query(SearchCache).filter(SearchCache.cache_key == "k").all()
    assert len(rows) == 1
    assert json.loads(rows[0].response_data) == result
    assert rows[0].expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)


def test_a_refreshed_row_is_then_served_from_cache(db):
    db.add(SearchCache(cache_key="k2", response_data="{}",
                       expires_at=datetime.now(timezone.utc) - timedelta(days=1)))
    db.commit()
    _FakeSearch.calls = 0
    with patch.object(api_budget, "GoogleSearch", _FakeSearch):
        api_budget.ApiBudgetManager(db, "test-key").execute_search("k2", {"q": "x"}, "e")
        second = api_budget.ApiBudgetManager(db, "test-key")
        second.execute_search("k2", {"q": "x"}, "e")
    assert _FakeSearch.calls == 1
    assert second.cache_hits == 1


# ------------------------------------------------ malformed provider payload
def test_a_malformed_provider_payload_is_read_as_empty(db):
    service = SerpApiOrganicService(db=db, api_key="test-key")
    out = service._process_response(
        {"organic_results": None, "local_results": {"places": None}},
        "q", None, cache_hit=False)
    assert out["provider_status"] == "no_results"
    out = service._process_response(
        {"organic_results": "oops", "local_results": ["bad", {"title": "Ok"}]},
        "q", None, cache_hit=False)
    assert [r["title"] for r in out["local_results"]] == ["Ok"]


# ---------------------------------------------- SB-2: Pulse context leakage
def test_pulse_trends_never_include_another_location(db):
    """Observed: Wine Retail @ Austin (no data) showed a Holmdel price trend."""
    m = merchant(db, "Circle Wine", "circle.example")
    product_obs(db, m, 19.99, HOLMDEL)
    product_obs(db, m, 21.99, HOLMDEL, hours=200)

    snapshot = MarketPulseService(db=db).snapshot(market="Wine Retail", location=AUSTIN)
    assert snapshot.has_data is False
    assert snapshot.trends == []

    holmdel = MarketPulseService(db=db).snapshot(market="Wine Retail", location=HOLMDEL)
    assert [t.metric for t in holmdel.trends] == ["price"]


def test_one_merchants_prices_in_two_cities_are_two_series(db):
    chain = merchant(db, "Chain Wine", "chain.example")
    product_obs(db, chain, 10.00, HOLMDEL)
    product_obs(db, chain, 30.00, AUSTIN, hours=200)

    series = TrendsService(db=db).price_trends().series
    assert len(series) == 2
    assert all(s.status == "insufficient_history" for s in series)


def test_a_failed_lookup_is_not_an_availability_reading(db):
    m = merchant(db, "Circle Wine", "circle.example")
    product_obs(db, m, None, HOLMDEL, price_status="unknown")
    product_obs(db, m, None, HOLMDEL, hours=200, status="unknown",
                price_status="unknown", reason="provider_request_failed")

    series = TrendsService(db=db).availability_trends().series
    assert len(series) == 1
    assert series[0].status == "insufficient_history"


# ------------------------------------------- SB-3: numeric grounding bypass
FACTS = ["3 verified businesses were observed.", "Wine at 19.99 USD."]


@pytest.mark.parametrize("summary", [
    "There are 250 stores.",          # began with "2", always "known"
    "Prices average 1000 dollars.",   # began with "1"
    "Prices are about 20.",           # rounded 19.99
    "One price was 19.9.",            # truncated 19.99
    "Revenue is 2.5 million.",
])
def test_an_invented_or_altered_figure_is_rejected(summary):
    ok, reason = validate_summary(summary, FACTS)
    assert ok is False and "figure" in reason


def test_a_restated_figure_is_still_accepted():
    assert validate_summary("3 businesses; one price of 19.99.", FACTS) == (True, None)


@pytest.mark.parametrize("summary", [
    "Total Wine leads the market.",
    "Total Wine is the clear leader here.",
    "I recommend matching its prices.",
    "Store X is the strongest player.",
    "Demand is strong in this area.",
])
def test_paraphrased_conclusions_are_rejected(summary):
    ok, reason = validate_summary(summary, FACTS)
    assert ok is False and "conclusion" in reason


# ------------------------------------ SB-4: silent location substitution
def _entry(canonical, target_type="City"):
    return {"canonical_name": canonical, "target_type": target_type,
            "country_code": "US"}


def resolver_with(table):
    resolver = LocationResolver()
    resolver._lookup = lambda candidate: table.get(candidate, [])
    return resolver


def test_a_state_resolves_to_the_state_not_its_largest_city():
    resolver = resolver_with({"Texas": [
        _entry("Texas,United States", "State"),
        _entry("Dallas,Texas,United States"),
        _entry("Houston,Texas,United States")]})
    assert resolver.resolve("Texas").canonical_name == "Texas,United States"


@pytest.mark.parametrize("raw, table", [
    ("Xyzzyville, New Jersey", {"New Jersey": [
        _entry("New Jersey,United States", "State"),
        _entry("Newark,New Jersey,United States")]}),
    ("Holmdel, Germany", {"Holmdel": [_entry(HOLMDEL)]}),
])
def test_a_contradicted_component_is_not_silently_dropped(raw, table):
    resolver = resolver_with(table)
    with pytest.raises(LocationConflictError):
        resolver.resolve(raw)
    # Cached like any other stable answer, and still a resolution error.
    with pytest.raises(LocationResolutionError):
        resolver.resolve(raw)


@pytest.mark.parametrize("raw", ["Holmdel, NJ", "Holmdel, New Jersey",
                                 "10 Main St, Holmdel, NJ 07733"])
def test_abbreviations_and_street_lines_still_resolve(raw):
    resolver = resolver_with({"Holmdel": [_entry(HOLMDEL)]})
    assert resolver.resolve(raw).canonical_name == HOLMDEL


def test_a_catalogue_http_error_is_an_outage_not_no_such_place():
    class Resp:
        def raise_for_status(self):
            raise RuntimeError("503")

    resolver = LocationResolver()
    with patch("app.services.location_service.requests.get", return_value=Resp()):
        with pytest.raises(LocationResolutionError) as excinfo:
            resolver.resolve("Holmdel")
    assert "could not be reached" in str(excinfo.value)
    assert "holmdel" not in resolver._cache


# -------------------------------------- SB-5: Price Intelligence error codes
@pytest.fixture
def client(db):
    def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_price_search_without_a_key_is_503_not_a_location_error(client):
    with patch("app.routes.prices.settings") as settings:
        settings.SERPAPI_API_KEY = None
        r = client.get("/api/prices/local?product=Merlot&area=Austin&radius=10")
    assert r.status_code == 503


@pytest.mark.parametrize("query", ["radius=0", "radius=-5", "radius=500", ""])
def test_price_search_rejects_an_unusable_radius(client, query):
    r = client.get("/api/prices/local?product=Merlot&area=Austin&" + query)
    assert r.status_code == 400
    assert "Radius" in r.json()["detail"]


def test_a_geocode_outage_is_502_not_422(client):
    with patch("app.routes.prices.settings") as settings, \
            patch.object(api_budget, "GoogleSearch", side_effect=RuntimeError("down")):
        settings.SERPAPI_API_KEY = "test-key"
        r = client.get("/api/prices/local?product=Merlot&area=Austin&radius=10")
    assert r.status_code == 502
    assert "did not respond" in r.json()["detail"]


# ------------------------------------------------ classifier namespaces
@pytest.mark.parametrize("url", ["https://www.gov.uk/x", "https://defence.mil.au/"])
def test_country_coded_government_hosts_are_not_businesses(url):
    assert classify_organic_result("Agency", url).entity_type != BUSINESS


def test_a_government_website_on_a_local_result_is_not_a_business():
    verdict = classify_local_result({"place_id": "p", "website": "https://city.gov"})
    assert verdict.entity_type != BUSINESS


@pytest.mark.parametrize("url", ["https://mil.com/", "https://govinda.com/",
                                 "https://government-supplies.com/"])
def test_commercial_domains_containing_gov_or_mil_are_still_businesses(url):
    assert classify_organic_result("Acme", url).entity_type == BUSINESS


# ------------------------------------------------------- product identity
@pytest.mark.parametrize("query, title", [
    ("iPhone 15", "iPhone 15 Silicone Case"),
    ("Coca Cola", "Coca Cola Bottle Opener Keychain"),
])
def test_an_accessory_is_not_the_product(query, title):
    verdict = match_product(query, title)
    assert verdict["matched"] is False
    assert verdict["reason"] == "accessory_or_related_item"


def test_equivalent_units_are_the_same_size():
    verdict = match_product("Chardonnay 750ml", "Chardonnay 75cl")
    assert verdict["matched"] and verdict["size_confirmed"]


def test_other_sizes_in_a_snippet_do_not_contradict_the_product():
    verdict = match_product("Chardonnay 750ml", "Chardonnay",
                            snippet="Also available as a 1.5l magnum")
    assert verdict["matched"] is True
    assert verdict["size_confirmed"] is False  # price stays unverified


def test_count_is_an_alias_of_ct():
    assert match_product("Pods 42 ct", "Pods 42 count")["size_confirmed"] is True


# ------------------------------------------------------ merchant identity
def test_same_named_businesses_in_different_cities_stay_separate(db):
    from app.services.competitor_service import CompetitorService

    existing = merchant(db, "Joes Pizza")
    db.add(CompetitorObservation(merchant_id=existing.id, market="Pizza",
                                 location_resolved=AUSTIN, source_type="local"))
    db.commit()

    service = CompetitorService(db=db, organic_service=None)
    candidate = {"domain": "", "place_id": None, "normalized_name": "joespizza"}
    assert service._find_existing(candidate, AUSTIN).id == existing.id
    assert service._find_existing(candidate, HOLMDEL) is None
