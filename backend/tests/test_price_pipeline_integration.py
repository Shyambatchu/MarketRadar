"""Price Intelligence against the real ApiBudgetManager.

``test_price_pipeline.py`` drives the funnel through a FakeBudget that returns
``None`` for a missing response. That is the right contract, but it is also why
a regression went unnoticed: the real manager returned an error *dict*, which is
truthy, so every ``is None`` check in the funnel was dead and a provider outage
arrived looking like an empty result set. These tests use the real manager so
the contract is verified rather than assumed.
"""
import pytest
from unittest.mock import patch

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.services.live_price_service import (
    LivePriceService, LocationResolutionError, SerpApiProviderError,
)

from tests.stubs import StubResolver

SECAUCUS = (40.798337, -74.064938)


@pytest.fixture
def db():
    """A session with an empty response cache.

    The cache is persistent by design, so without this every test after the
    first would be served the previous test's payloads under the same keys.
    """
    from sqlalchemy import text

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    session.execute(text("DELETE FROM search_cache"))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def service():
    return LivePriceService("test-key", resolver=StubResolver())


def stage(result, name):
    return next((s for s in result.stages if s.stage == name), None)


class Responses:
    """Routes a GoogleSearch call to a payload by engine, or fails it."""

    def __init__(self, by_engine, failing=()):
        self.by_engine = by_engine
        self.failing = set(failing)
        self.calls = []

    def __call__(self, params):
        engine_name = params.get("engine")
        self.calls.append(engine_name)
        outer = self

        class Search:
            @staticmethod
            def get_dict():
                if engine_name in outer.failing:
                    raise RuntimeError(engine_name + " provider down")
                return outer.by_engine.get(engine_name, {})

        return Search()


MAPS_OK = {
    "place_results": {"title": "Secaucus",
                      "gps_coordinates": {"latitude": SECAUCUS[0],
                                          "longitude": SECAUCUS[1]}},
    "local_results": [{
        "title": "Example Wine",
        "gps_coordinates": {"latitude": 40.80, "longitude": -74.06},
        "website": "https://example.com", "address": "1 Main St",
        "place_id": "p1",
    }],
}


def run(service, db, by_engine, failing=(), product="Widget 2000",
        area="Secaucus, NJ", radius=25):
    responses = Responses(by_engine, failing)
    with patch("app.services.api_budget.GoogleSearch", side_effect=responses):
        result = service.fetch_real_data(product, area, radius, db=db)
    return result, responses


# ------------------------------------------------------- provider error vs no data
def test_shopping_provider_failure_is_an_error_stage_not_zero_results(service, db):
    """Spec 11: a failed provider is never "0 shopping results found"."""
    result, _ = run(service, db, {"google_maps": MAPS_OK, "google": {}},
                    failing=["google_shopping"])

    shopping = stage(result, "shopping_evidence")
    assert shopping.status == "error"
    assert shopping.detail == "provider_request_failed"
    # A count is not reported for a stage that never ran.
    assert shopping.results_count is None


def test_genuinely_empty_shopping_results_are_an_ok_stage(service, db):
    result, _ = run(service, db, {
        "google_maps": MAPS_OK, "google": {},
        "google_shopping": {"shopping_results": []}})

    shopping = stage(result, "shopping_evidence")
    assert shopping.status == "ok"
    assert shopping.results_count == 0
    assert result.shopping_results_found == 0


def test_merchant_discovery_failure_is_reported_as_an_error(service, db):
    """The search centre resolves first, so discovery failure stands alone."""
    responses = Responses({"google_maps": MAPS_OK, "google": {},
                           "google_shopping": {"shopping_results": []}})
    calls = {"n": 0}
    original = responses.__call__

    def fail_second_maps(params):
        if params.get("engine") == "google_maps":
            calls["n"] += 1
            if calls["n"] == 2:  # geocode succeeds, discovery fails
                class Search:
                    @staticmethod
                    def get_dict():
                        raise RuntimeError("maps down")
                return Search()
        return original(params)

    with patch("app.services.api_budget.GoogleSearch", side_effect=fail_second_maps):
        result = service.fetch_real_data("Widget 2000", "Secaucus, NJ", 25, db=db)

    discovery = stage(result, "merchant_discovery")
    assert discovery.status == "error"
    assert discovery.detail == "provider_request_failed"
    assert result.nearby_merchants_discovered == 0


def test_website_provider_failure_degrades_the_stage(service, db):
    result, _ = run(service, db, {"google_maps": MAPS_OK,
                                  "google_shopping": {"shopping_results": []}},
                    failing=["google"])

    website = stage(result, "merchant_website_evidence")
    assert website.status == "degraded"
    assert "failed" in website.detail
    # A merchant whose evidence never arrived stays unknown, not "not stocked".
    assert result.nearby_merchants[0].product_status == "unknown"
    assert result.product_evidence_not_found == 0


def test_geocode_failure_says_the_provider_did_not_respond(service, db):
    """A provider outage must not be reported as an unknown place."""
    with pytest.raises(SerpApiProviderError) as excinfo:
        run(service, db, {}, failing=["google_maps"])
    assert "did not respond" in str(excinfo.value)


# ------------------------------------------------------- location resolution
def test_postal_code_resolves_for_the_shopping_provider(service, db):
    """Postal codes used to be stripped out, leaving "08807" unresolvable."""
    result, responses = run(service, db, {
        "google_maps": MAPS_OK, "google": {},
        "google_shopping": {"shopping_results": []}}, area="08807")

    shopping = stage(result, "shopping_evidence")
    assert shopping.status == "ok"
    assert shopping.detail is None, "the location was resolved, so not degraded"


def test_unresolvable_provider_location_degrades_shopping_only(service, db):
    """An unresolved provider location must not fail the whole search."""
    svc = LivePriceService("test-key", resolver=StubResolver(table={}))
    responses = Responses({"google_maps": MAPS_OK, "google": {},
                           "google_shopping": {"shopping_results": []}})
    with patch("app.services.api_budget.GoogleSearch", side_effect=responses):
        result = svc.fetch_real_data("Widget 2000", "Nowhereville", 25, db=db)

    shopping = stage(result, "shopping_evidence")
    assert shopping.status == "degraded"
    assert shopping.detail == "location_not_resolved_results_not_localised"
    # The search centre came from geocoding, so the search still ran.
    assert result.search_center is not None


def test_resolved_location_is_what_the_provider_receives(service, db):
    sent = []

    class Capturing(Responses):
        def __call__(self, params):
            if params.get("engine") == "google_shopping":
                sent.append(params.get("location"))
            return super().__call__(params)

    responses = Capturing({"google_maps": MAPS_OK, "google": {},
                           "google_shopping": {"shopping_results": []}})
    with patch("app.services.api_budget.GoogleSearch", side_effect=responses):
        service.fetch_real_data("Widget 2000", "Secaucus, NJ", 25, db=db)

    assert sent == ["Secaucus,New Jersey,United States"]


def test_shopping_cache_key_tracks_the_resolved_location(service, db):
    """Spec 14: two different places must never share one cached response."""
    keys = []
    real = None

    from app.services import api_budget as ab
    original = ab.ApiBudgetManager.execute_search

    def recording(self, cache_key, params, endpoint, domain=""):
        if endpoint == "google_shopping":
            keys.append(cache_key)
        return original(self, cache_key, params, endpoint, domain)

    with patch.object(ab.ApiBudgetManager, "execute_search", recording):
        run(service, db, {"google_maps": MAPS_OK, "google": {},
                          "google_shopping": {"shopping_results": []}},
            area="Secaucus, NJ")
        run(service, db, {"google_maps": MAPS_OK, "google": {},
                          "google_shopping": {"shopping_results": []}},
            area="Holmdel, NJ")

    assert len(keys) == 2 and keys[0] != keys[1]
    assert "Secaucus,New Jersey,United States" in keys[0]
    assert "Holmdel,New Jersey,United States" in keys[1]


# ------------------------------------------------------- evidence states
def test_merchant_found_but_product_unknown(service, db):
    """Discovery alone proves nothing about what a store sells."""
    result, _ = run(service, db, {"google_maps": MAPS_OK, "google": {},
                                  "google_shopping": {"shopping_results": []}})

    assert result.nearby_merchants_discovered == 1
    merchant = result.nearby_merchants[0]
    assert merchant.product_status == "unknown"
    assert merchant.price_status == "unknown"
    assert merchant.verification_reason == "insufficient_evidence"
    assert result.verified_local_prices == 0


def test_product_found_but_price_unverifiable_on_a_listing_page(service, db):
    website = {"organic_results": [{
        "title": "Widget 2000",
        "link": "https://example.com/collections/widgets?brand=widget",
        "snippet": "Widget 2000 $19.99",
    }]}
    result, _ = run(service, db, {"google_maps": MAPS_OK, "google": website,
                                  "google_shopping": {"shopping_results": []}})

    merchant = result.nearby_merchants[0]
    assert merchant.product_status == "found"
    assert merchant.price_status == "unavailable"
    assert merchant.verification_reason == "price_not_product_specific"
    assert result.verified_local_prices == 0


def test_verified_price_from_a_product_page_is_catalog_scope(service, db):
    website = {"organic_results": [{
        "title": "Widget 2000",
        "link": "https://example.com/product/widget-2000",
        "snippet": "Widget 2000 $19.99 add to cart",
    }]}
    result, _ = run(service, db, {"google_maps": MAPS_OK, "google": website,
                                  "google_shopping": {"shopping_results": []}})

    merchant = result.nearby_merchants[0]
    assert merchant.product_status == "found"
    assert merchant.price_status == "verified"
    assert merchant.price == 19.99
    # A catalogue page proves the merchant offers it, not that this store
    # currently holds stock.
    assert merchant.evidence_scope == "catalog"
    assert merchant.inventory_confirmed is False
    assert result.verified_local_prices == 1


def test_wrong_size_does_not_verify_a_price(service, db):
    website = {"organic_results": [{
        "title": "Widget 2000 50ml",
        "link": "https://example.com/product/widget-2000-50ml",
        "snippet": "Widget 2000 50ml $9.99",
    }]}
    result, _ = run(service, db, {"google_maps": MAPS_OK, "google": website,
                                  "google_shopping": {"shopping_results": []}},
                    product="Widget 2000 750ml")

    merchant = result.nearby_merchants[0]
    assert merchant.price_status != "verified"
    assert result.verified_local_prices == 0


def test_uncertain_merchant_identity_never_yields_a_verified_price(service, db):
    """Spec 8: low-confidence identity may not attribute a verified price.

    Two stores of one chain are in radius, so a shopping row naming the chain
    cannot say which physical store it concerns.
    """
    maps = {
        "place_results": MAPS_OK["place_results"],
        "local_results": [
            {"title": "Chain Wine", "gps_coordinates": {"latitude": 40.80, "longitude": -74.06},
             "website": "https://chainwine.com", "address": "1 Main St", "place_id": "p1"},
            {"title": "Chain Wine", "gps_coordinates": {"latitude": 40.81, "longitude": -74.07},
             "website": "https://chainwine.com", "address": "2 Other St", "place_id": "p2"},
        ],
    }
    shopping = {"shopping_results": [{
        "title": "Widget 2000", "source": "chainwine.com",
        "link": "https://chainwine.com/product/widget-2000", "price": "$19.99",
    }]}
    result, _ = run(service, db, {"google_maps": maps, "google": {},
                                  "google_shopping": shopping})

    assert result.merchant_uncertain_count >= 1
    assert result.verified_local_prices == 0
    assert all(m.price_status != "verified" for m in result.nearby_merchants)


def test_nearby_stores_remain_visible_without_product_evidence(service, db):
    """Spec 16: discovery results are shown even when nothing could be verified."""
    result, _ = run(service, db, {"google_maps": MAPS_OK, "google": {},
                                  "google_shopping": {"shopping_results": []}})

    assert len(result.nearby_merchants) == 1
    assert result.nearby_merchants[0].merchant == "Example Wine"
    assert result.verified_price_observations == []


def test_counters_stay_semantically_distinct(service, db):
    """Spec 13: website and shopping counters must not alias each other."""
    website = {"organic_results": [
        {"title": "Widget 2000", "link": "https://example.com/product/widget-2000",
         "snippet": "Widget 2000 $19.99"},
        # Off-domain: excluded from website_results_found entirely.
        {"title": "Widget 2000", "link": "https://elsewhere.com/product/widget-2000",
         "snippet": "Widget 2000 $18.99"},
    ]}
    result, _ = run(service, db, {"google_maps": MAPS_OK, "google": website,
                                  "google_shopping": {"shopping_results": []}})

    assert result.website_results_found == 1, "off-domain rows are not merchant evidence"
    assert result.website_off_domain_rejected == 1
    assert result.shopping_candidates == 0
    assert result.website_candidates == 1
    assert result.candidate_product_matches == (
        result.website_candidates + result.shopping_candidates)
