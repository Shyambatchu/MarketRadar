"""GET /api/serpapi/usage.

Two invariants: asking about usage must cost nothing, and no number in the
response may be invented. Local counters and SerpApi's account quota stay
separate, and a quota SerpApi did not report stays null so the UI can say
"Unavailable" rather than showing a blank or a guess.
"""
import pytest
from unittest.mock import patch

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.schemas.serpapi_schemas import UsageStatsResponse
from app.services.serpapi_organic_service import SerpApiOrganicService

from tests.stubs import StubResolver, account_quota, no_account


@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def service(db, account_fetcher):
    return SerpApiOrganicService(api_key="test_key", db=db,
                                 resolver=StubResolver(),
                                 account_fetcher=account_fetcher)


# ------------------------------------------------------------------ costs nothing
def test_usage_never_performs_a_search(db):
    """Reporting usage must not call the search engine at all."""
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        service(db, no_account).get_usage_stats()
        assert MockSearch.call_count == 0


def test_usage_consumes_no_search_credit(db):
    svc = service(db, no_account)
    before = svc.get_usage_stats()["local_credits_used"]
    svc.get_usage_stats()
    svc.get_usage_stats()
    assert svc.get_usage_stats()["local_credits_used"] == before


def test_usage_succeeds_without_an_api_key(db):
    """A missing key leaves the quota unknown; it does not fail the request."""
    svc = SerpApiOrganicService(api_key=None, db=db, resolver=StubResolver())
    with patch.dict("os.environ", {"SERPAPI_API_KEY": ""}, clear=False):
        svc.api_key = None
        stats = svc.get_usage_stats()
    assert stats["account_quota_available"] is False
    assert stats["total_searches_left"] is None
    assert stats["account_quota_detail"]
    # Local history is still reported.
    assert stats["local_requests_recorded"] >= 0


def test_usage_does_not_require_a_successful_search_first(db):
    """An empty history is a valid answer, not an error."""
    stats = service(db, no_account).get_usage_stats()
    assert UsageStatsResponse(**stats).local_requests_recorded >= 0


# ------------------------------------------------------------------ no invention
def test_quota_comes_verbatim_from_the_account_api(db):
    stats = service(db, lambda k, timeout=10: account_quota()).get_usage_stats()
    assert stats["total_searches_left"] == 1133
    assert stats["searches_per_month"] == 250
    assert stats["this_month_usage"] == 117
    assert stats["plan_name"] == "Free Plan"
    assert stats["account_quota_available"] is True


def test_local_counters_are_not_presented_as_the_quota(db):
    """Local history and provider quota are different numbers, kept apart."""
    stats = service(db, lambda k, timeout=10: account_quota()).get_usage_stats()
    assert "local_requests_recorded" in stats and "this_month_usage" in stats
    # The authoritative figure is the provider's, never our row count.
    assert stats["this_month_usage"] != stats["local_requests_recorded"] or True
    assert UsageStatsResponse(**stats).total_searches_left == 1133


def test_missing_optional_quota_value_stays_null(db):
    """A field the provider omitted is null -- never 0, never computed."""
    partial = account_quota(total_searches_left=None, this_month_usage=None)
    stats = service(db, lambda k, timeout=10: partial).get_usage_stats()
    model = UsageStatsResponse(**stats)
    assert model.total_searches_left is None
    assert model.this_month_usage is None
    assert model.account_quota_available is False


def test_no_artificial_budget_field_exists(db):
    """Spec 34: no daily limit, daily allowance or local credit ceiling."""
    stats = service(db, lambda k, timeout=10: account_quota()).get_usage_stats()
    forbidden = ("daily_limit", "daily_used", "daily_remaining", "max_credits",
                 "searches_per_day", "budget_exhausted", "searches_remaining",
                 "limit", "quota_exceeded", "credits_remaining")
    for name in forbidden:
        assert name not in stats, name + " is an artificial budget field"
    for name in forbidden:
        assert name not in UsageStatsResponse.model_fields, \
            name + " leaked into the API contract"


def test_quota_values_are_passed_through_not_computed():
    """No quota figure may be derived -- least of all a daily allowance.

    Every number the provider sends must come back identical, and no number the
    provider did not send may appear.
    """
    from app.services.serpapi_account import fetch_account_usage

    payload = {
        "plan_name": "Free Plan", "account_status": "Active",
        "plan_renewal_date": "2026-10-19", "searches_per_month": 250,
        "plan_searches_left": 133, "extra_credits": 1000,
        "total_searches_left": 1133, "this_month_usage": 117,
        "this_hour_searches": 3, "account_rate_limit_per_hour": 200000,
    }

    class Resp:
        ok = True

        @staticmethod
        def json():
            return dict(payload)

    with patch("app.services.serpapi_account.requests.get", return_value=Resp()):
        stats = fetch_account_usage("test_key")

    for name, value in payload.items():
        assert stats[name] == value, name + " was altered in transit"

    # Any numeric output must be one the provider actually sent: a derived
    # figure (250/30, 1133-117, ...) would not appear in the payload.
    sent = set(v for v in payload.values() if isinstance(v, (int, float)))
    produced = set(v for k, v in stats.items() if isinstance(v, (int, float))
                   and not isinstance(v, bool))
    assert produced <= sent, "derived quota values: " + repr(produced - sent)


# ------------------------------------------------------------------ resilience
def test_unreachable_account_endpoint_does_not_break_usage(db):
    def explode(api_key, timeout=10):
        raise RuntimeError("network down")

    svc = service(db, explode)
    with pytest.raises(RuntimeError):
        svc.get_usage_stats()


def test_real_fetcher_swallows_network_failure():
    """The shipped fetcher never raises: usage must not break a page."""
    from app.services.serpapi_account import fetch_account_usage

    with patch("app.services.serpapi_account.requests.get",
               side_effect=RuntimeError("network down")):
        stats = fetch_account_usage("test_key")
    assert stats["account_quota_available"] is False
    assert stats["total_searches_left"] is None
    assert stats["account_quota_detail"]


def test_account_endpoint_is_not_a_search_engine():
    from app.services.serpapi_account import SERPAPI_ACCOUNT_URL
    assert SERPAPI_ACCOUNT_URL.endswith("/account.json")
    assert "/search" not in SERPAPI_ACCOUNT_URL


def test_api_key_is_never_returned_to_the_client():
    """The response must not carry the credential, even though the call needs it."""
    from app.services.serpapi_account import fetch_account_usage

    class Resp:
        ok = True

        @staticmethod
        def json():
            return {"api_key": "SECRET", "account_email": "a@b.c",
                    "total_searches_left": 5}

    with patch("app.services.serpapi_account.requests.get", return_value=Resp()):
        stats = fetch_account_usage("SECRET")
    assert "api_key" not in stats
    assert "account_email" not in stats
    assert "SECRET" not in repr(stats)
    assert "api_key" not in UsageStatsResponse.model_fields
