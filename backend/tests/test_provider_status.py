"""Provider outcomes stay distinguishable: success, no_results, error, cache hit.

The failure this file guards against is silent: ``ApiBudgetManager`` used to
return ``{"error": ...}`` on a failed request, while every caller tested for
``None``. A truthy error dict therefore flowed on as a perfectly good response
that happened to contain no results -- so a provider outage was reported as
"0 shopping results" and a store as "unable to verify", with the stage marked
"ok". Tests passed throughout, because the fakes returned ``None`` like the
real manager was supposed to.
"""
import pytest
from unittest.mock import patch

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.services.api_budget import ApiBudgetManager
from app.services.serpapi_organic_service import (
    SerpApiOrganicService, SerpApiProviderError,
)

from tests.stubs import StubResolver, no_account


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def organic(db):
    return SerpApiOrganicService(api_key="test_key", db=db,
                                 resolver=StubResolver(),
                                 account_fetcher=no_account)


# ---------------------------------------------------------- budget manager contract
def test_failed_request_returns_none_not_an_error_dict(db):
    """``None`` is the one signal callers test for; a dict would look like data."""
    budget = ApiBudgetManager(db, "test_key")
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.side_effect = RuntimeError("connection reset")
        result = budget.execute_search("k|fail", {"q": "x"}, "google_organic")

    assert result is None, "a failed request must not return a response-shaped dict"
    assert "connection reset" in budget.last_error


def test_provider_error_payload_is_also_a_failure(db):
    """SerpApi reports some failures in-band, as an ``error`` key."""
    budget = ApiBudgetManager(db, "test_key")
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = {
            "error": "Unsupported `Holmdel, NJ` location - location parameter."}
        result = budget.execute_search("k|inband", {"q": "x"}, "google_organic")

    assert result is None
    assert "Unsupported" in budget.last_error


def test_empty_result_set_is_a_success_not_a_failure(db):
    """A search that ran and found nothing is data, and is cached as data."""
    budget = ApiBudgetManager(db, "test_key")
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = {"organic_results": []}
        result = budget.execute_search("k|empty", {"q": "x"}, "google_organic")

    assert result == {"organic_results": []}
    assert budget.last_error is None


def test_failed_request_is_not_cached(db):
    """A failure must not be served as though it were a result."""
    budget = ApiBudgetManager(db, "test_key")
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.side_effect = RuntimeError("boom")
        budget.execute_search("k|nocache", {"q": "x"}, "google_organic")
        MockSearch.return_value.get_dict.side_effect = None
        MockSearch.return_value.get_dict.return_value = {"organic_results": [{"position": 1}]}
        second = budget.execute_search("k|nocache", {"q": "x"}, "google_organic")

    assert second == {"organic_results": [{"position": 1}]}


def test_failed_request_consumes_no_credit(db):
    """The provider does not bill a failed search, so neither do our counters."""
    budget = ApiBudgetManager(db, "test_key")
    from sqlalchemy import text

    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.side_effect = RuntimeError("boom")
        budget.execute_search("k|credit", {"q": "unique-failing-query"}, "google_organic")

    row = db.execute(text(
        "SELECT success, credits_used FROM api_usage"
        " WHERE query = 'unique-failing-query' ORDER BY id DESC LIMIT 1")).first()
    assert row[0] == 0
    assert row[1] == 0


# ---------------------------------------------------------- organic search statuses
def test_organic_success_reports_success(db):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = {
            "organic_results": [{"position": 1, "title": "A", "link": "https://a.com"}]}
        res = organic(db).search_google(query="status-success", location="Holmdel, NJ")

    assert res["provider_status"] == "success"
    assert res["resolved_location"] == "Holmdel,New Jersey,United States"


def test_organic_no_results_is_not_an_error(db):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = {"organic_results": []}
        res = organic(db).search_google(query="status-empty", location="Holmdel, NJ")

    assert res["provider_status"] == "no_results"
    assert res["results"] == []


def test_organic_provider_error_raises_rather_than_returning_empty(db):
    """The one thing that must never happen: error rendered as zero results."""
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.side_effect = RuntimeError("provider down")
        with pytest.raises(SerpApiProviderError) as excinfo:
            organic(db).search_google(query="status-error", location="Holmdel, NJ")

    assert "provider down" in str(excinfo.value)


def test_organic_cache_hit_spends_nothing(db):
    svc = organic(db)
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = {
            "organic_results": [{"position": 1, "title": "A", "link": "https://a.com"}]}
        first = svc.search_google(query="status-cache", location="Holmdel, NJ")
        second = svc.search_google(query="status-cache", location="Holmdel, NJ")
        assert MockSearch.return_value.get_dict.call_count == 1

    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert second["provider_status"] == "success"


def test_unresolvable_location_never_reaches_the_provider(db):
    """No search is attempted, so no credit is risked on a doomed request."""
    from app.services.location_service import LocationResolutionError

    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        with pytest.raises(LocationResolutionError):
            organic(db).search_google(query="q", location="Zzzqqxinvalidplace")
        assert MockSearch.call_count == 0


# ---------------------------------------------------------- merchant website provider
def test_website_provider_reports_error_on_failed_request(db):
    """With the real manager, not a fake: the contract has to hold end to end."""
    from app.providers.merchant_website_provider import MerchantWebsitePriceProvider

    budget = ApiBudgetManager(db, "test_key")
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.side_effect = RuntimeError("provider down")
        out = MerchantWebsitePriceProvider().discover_prices(
            {"domain": "example.com", "name": "Example"}, "Widget", budget, "v2")

    assert out["status"] == "error"
    assert out["detail"] == "provider_request_failed"
    assert out["observations"] == []


def test_website_provider_reports_ok_on_genuinely_empty_results(db):
    from app.providers.merchant_website_provider import MerchantWebsitePriceProvider

    budget = ApiBudgetManager(db, "test_key")
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = {"organic_results": []}
        out = MerchantWebsitePriceProvider().discover_prices(
            {"domain": "example.com", "name": "Example"}, "Widget", budget, "v2")

    assert out["status"] == "ok"
    assert out["rows_returned"] == 0


# ---------------------------------------------------------- cache identity
def test_language_and_country_are_part_of_website_cache_identity(db):
    """Spec 14: a key must cover every parameter that changes the response."""
    from app.providers.merchant_website_provider import MerchantWebsitePriceProvider

    provider = MerchantWebsitePriceProvider()
    seen = []

    class RecordingBudget:
        last_error = None

        def execute_search(self, cache_key, params, endpoint, domain=""):
            seen.append(cache_key)
            return {"organic_results": []}

    budget = RecordingBudget()
    merchant = {"domain": "example.com", "name": "Example"}
    provider.discover_prices(merchant, "Widget", budget, "v2", hl="en", gl="us")
    provider.discover_prices(merchant, "Widget", budget, "v2", hl="fr", gl="fr")

    assert seen[0] != seen[1], "hl/gl must change the cache key"
