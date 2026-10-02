"""End-to-end Price Intelligence funnel tests against synthetic providers.

No network, no API credits. Covers the funnel invariants: stage reporting,
counter separation, evidence scope, radius filtering and cache identity.
"""
import pytest

from app.services import live_price_service as L
from app.services.live_price_service import LivePriceService, LocationResolutionError

SECAUCUS = (40.798337, -74.064938)


def _maps_place(lat, lon, title="Test Center"):
    return {"place_results": {"title": title,
                              "gps_coordinates": {"latitude": lat, "longitude": lon}}}


def _merchant(title, lat, lon, website="", place_id="p1", address="1 Main St"):
    return {"title": title, "gps_coordinates": {"latitude": lat, "longitude": lon},
            "website": website, "address": address, "place_id": place_id}


class FakeBudget:
    """Stands in for ApiBudgetManager; records every cache key requested."""

    def __init__(self, responses):
        self.responses = responses
        self.keys = []
        self.cache_hits = 0

    def execute_search(self, cache_key, params, endpoint, domain=""):
        self.keys.append(cache_key)
        for pattern, payload in self.responses.items():
            if pattern in cache_key:
                return payload
        return None

    def get_usage_report(self):
        return {"external_calls_used": 0, "merchant_discovery_used": 0,
                "website_provider_used": 0, "shopping_used": 0, "cache_hits": 0}


@pytest.fixture
def service(monkeypatch):
    svc = LivePriceService("test-key")
    # Never reach the network for location canonicalisation.
    monkeypatch.setattr(LivePriceService, "resolve_provider_location",
                        lambda self, a, r: ("Secaucus, New Jersey, United States", "us"))
    return svc


def run(service, monkeypatch, responses, product="Widget 2000",
        area="Secaucus, NJ", radius=25, reference=None):
    budget = FakeBudget(responses)
    monkeypatch.setattr(L, "ApiBudgetManager", lambda db, key: budget)
    result = service.fetch_real_data(product, area, radius, db=None,
                                     reference_merchant_name=reference)
    return result, budget


# ---------------------------------------------------------------- search centre
def test_search_center_is_never_guessed(service, monkeypatch):
    """An unresolvable area must fail loudly, not fall back to a fixed point."""
    with pytest.raises(LocationResolutionError):
        run(service, monkeypatch, {"|geocode|": {"search_metadata": {}}})


def test_search_center_falls_back_to_map_viewport(service, monkeypatch):
    payload = {"search_metadata": {
        "google_maps_url": "https://www.google.com/maps/search/x/@17.3850,78.4867,12z/data=x"}}
    result, _ = run(service, monkeypatch, {"|geocode|": payload}, area="Hyderabad")
    assert result.search_center.latitude == pytest.approx(17.3850)
    assert result.search_center.resolution_method == "maps_viewport_center"


def test_cache_identity_contains_location_and_radius(service, monkeypatch):
    """Spec 36: a different location must never reuse another's response."""
    responses = {"|geocode|": _maps_place(*SECAUCUS)}
    _, budget = run(service, monkeypatch, responses, radius=25)
    maps_key = next(k for k in budget.keys if k.startswith("v2|maps|"))
    assert "40.798337" in maps_key and "-74.064938" in maps_key and "25mi" in maps_key


# ---------------------------------------------------------------- radius
def test_radius_excludes_distant_merchants(service, monkeypatch):
    responses = {
        "|geocode|": _maps_place(*SECAUCUS),
        "v2|maps|": {"local_results": [
            _merchant("Near Store", 40.80, -74.06),
            _merchant("Far Store", 34.05, -118.24),   # Los Angeles
        ]},
    }
    result, _ = run(service, monkeypatch, responses, radius=25)
    assert result.nearby_merchants_discovered == 1
    assert result.nearby_merchants[0].merchant == "Near Store"


# ---------------------------------------------------------------- stage status
def test_failed_shopping_stage_is_an_error_not_a_zero(service, monkeypatch):
    """Spec 50/76: a dead provider must not read as 'no results'."""
    responses = {"|geocode|": _maps_place(*SECAUCUS), "v2|maps|": {"local_results": []}}
    result, _ = run(service, monkeypatch, responses)
    shopping = next(s for s in result.stages if s.stage == "shopping_evidence")
    assert shopping.status == "error"
    assert shopping.results_count is None
    assert result.shopping_results_found == 0


# ---------------------------------------------------------------- website funnel
def _website_responses(organic):
    return {
        "|geocode|": _maps_place(*SECAUCUS),
        "v2|maps|": {"local_results": [
            _merchant("Test Store", 40.80, -74.06, website="https://teststore.com")]},
        "merchant_website_indexed|teststore.com": {"organic_results": organic},
    }


def test_off_domain_rows_never_become_merchant_evidence(service, monkeypatch):
    organic = [
        {"title": "Widget 2000 Song", "link": "https://youtube.com/watch?v=1", "snippet": ""},
        {"title": "Widget 2000", "link": "https://teststore.com/products/widget-2000",
         "snippet": "Widget 2000 $39.99 Add to Cart"},
    ]
    result, _ = run(service, monkeypatch, _website_responses(organic))
    assert result.website_off_domain_rejected == 1
    assert result.website_results_found == 1
    assert result.verified_local_prices == 1


def test_listing_page_price_is_never_verified(service, monkeypatch):
    """Spec 22/51: a price on a brand listing belongs to no single product."""
    organic = [{"title": "Widget 2000", "link": "https://teststore.com/shop/?brand=Widget",
                "snippet": "Widget 2000 $32.95"}]
    result, _ = run(service, monkeypatch, _website_responses(organic))
    assert result.website_listing_pages == 1
    assert result.verified_local_prices == 0
    merchant = result.nearby_merchants[0]
    assert merchant.product_status == "found"
    assert merchant.price_status == "unavailable"
    assert merchant.verification_reason == "price_not_product_specific"


def test_website_evidence_is_catalog_scope_not_store_inventory(service, monkeypatch):
    """Spec 38: a catalogue listing is not proof of stock at one address."""
    organic = [{"title": "Widget 2000", "link": "https://teststore.com/products/widget-2000",
                "snippet": "Widget 2000 $39.99 Add to Cart"}]
    result, _ = run(service, monkeypatch, _website_responses(organic))
    obs = result.verified_price_observations[0]
    assert obs.evidence_scope == "catalog"
    assert obs.inventory_confirmed is False
    assert result.nearby_merchants[0].inventory_confirmed is False


def test_missing_price_keeps_product_evidence(service, monkeypatch):
    """Spec 52: no price must never be reported as no product."""
    organic = [{"title": "Widget 2000", "link": "https://teststore.com/products/widget-2000",
                "snippet": "Widget 2000 - currently unavailable"}]
    result, _ = run(service, monkeypatch, _website_responses(organic))
    merchant = result.nearby_merchants[0]
    assert merchant.product_status == "found"
    assert merchant.price_status == "unavailable"
    assert result.product_evidence_found == 1
    assert result.product_evidence_not_found == 0


def test_website_results_do_not_increment_shopping_counters(service, monkeypatch):
    """Spec 29: the two pipelines stay separated."""
    organic = [{"title": "Widget 2000", "link": "https://teststore.com/products/widget-2000",
                "snippet": "Widget 2000 $39.99"}]
    result, _ = run(service, monkeypatch, _website_responses(organic))
    assert result.shopping_results_found == 0
    assert result.shopping_candidates == 0
    assert result.shopping_merchant_matches == 0
    assert result.website_merchant_matches == 1
    # The cross-source total is the sum of its per-source parts.
    assert result.merchant_matches == (result.website_merchant_matches
                                       + result.shopping_merchant_matches)
    assert result.candidate_product_matches == (result.website_candidates
                                                + result.shopping_candidates)


def test_statistics_only_include_verified_prices(service, monkeypatch):
    organic = [
        {"title": "Widget 2000", "link": "https://teststore.com/products/widget-2000",
         "snippet": "Widget 2000 $39.99"},
        {"title": "Widget 2000", "link": "https://teststore.com/shop/?brand=Widget",
         "snippet": "Widget 2000 $9.99"},
    ]
    result, _ = run(service, monkeypatch, _website_responses(organic))
    assert result.lowest_price == 39.99
    assert result.highest_price == 39.99
    assert result.average_price == 39.99


def test_reference_store_is_excluded_from_competitor_statistics(service, monkeypatch):
    """Spec 25: reference observations stay separate from competitors."""
    organic = [{"title": "Widget 2000", "link": "https://teststore.com/products/widget-2000",
                "snippet": "Widget 2000 $39.99"}]
    result, _ = run(service, monkeypatch, _website_responses(organic),
                    reference="Test Store")
    assert result.reference_store is not None
    assert result.reference_price == 39.99
    assert result.verified_price_observations == []


def test_no_reference_store_still_works(service, monkeypatch):
    """Spec 25: the reference retailer is optional."""
    organic = [{"title": "Widget 2000", "link": "https://teststore.com/products/widget-2000",
                "snippet": "Widget 2000 $39.99"}]
    result, _ = run(service, monkeypatch, _website_responses(organic))
    assert result.reference_store is None
    assert result.reference_price is None
    assert result.verified_local_prices == 1


def test_response_echoes_the_request_it_belongs_to(service, monkeypatch):
    """Spec 33: the client must be able to tell which request answered."""
    responses = {"|geocode|": _maps_place(*SECAUCUS), "v2|maps|": {"local_results": []}}
    result, _ = run(service, monkeypatch, responses, product="Widget 2000",
                    area="Secaucus, NJ", radius=25)
    assert result.searched_product == "Widget 2000"
    assert result.searched_area == "Secaucus, NJ"
    assert result.searched_radius == 25
