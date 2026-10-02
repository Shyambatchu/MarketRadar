"""Market Research (organic) service: caching, usage reporting, no budget.

No network and no API credits: the SerpApi client, the location catalogue and
the account endpoint are all stubbed.
"""
import pytest
from unittest.mock import patch
from app.services.serpapi_organic_service import SerpApiOrganicService
from app.database.connection import engine, SessionLocal
from app.database.base import Base

from tests.stubs import StubResolver, no_account


@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


def make_service(db, **kwargs):
    kwargs.setdefault("resolver", StubResolver())
    kwargs.setdefault("account_fetcher", no_account)
    return SerpApiOrganicService(api_key="test_key", db=db, **kwargs)


def test_serpapi_organic_service_caching(setup_db):
    db = setup_db
    service = make_service(db)

    mock_response = {
        "organic_results": [
            {
                "position": 1,
                "title": "Wine Store A",
                "link": "https://store-a.com",
                "snippet": "Great wine."
            }
        ]
    }

    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        instance = MockSearch.return_value
        instance.get_dict.return_value = mock_response

        # 1. First call (Cache Miss)
        res1 = service.search_google(query="wine stores in nj", location="Secaucus, NJ")
        assert res1["cache_hit"] is False
        assert len(res1["results"]) == 1
        assert res1["results"][0]["title"] == "Wine Store A"

        # 2. Second call (Cache Hit)
        res2 = service.search_google(query="wine stores in nj", location="Secaucus, NJ")
        assert res2["cache_hit"] is True
        assert len(res2["results"]) == 1

        # Ensure API was called only once: a cache hit spends no credit.
        assert instance.get_dict.call_count == 1

        # Usage reflects real spend; there is no artificial budget (spec 34).
        stats = service.get_usage_stats()
        assert stats["local_requests_recorded"] == 1
        assert stats["local_credits_used"] == 1
        assert stats["local_cache_hits"] == 1


def test_no_artificial_budget_is_enforced(setup_db):
    """Spec 34: application-level API budgets were removed and must not return."""
    db = setup_db
    service = make_service(db)
    assert not hasattr(service, "max_credits")

    stats = service.get_usage_stats()
    for forbidden in ("searches_remaining", "daily_limit", "daily_used",
                      "max_credits", "limit", "budget_exhausted",
                      "searches_per_day", "daily_remaining"):
        assert forbidden not in stats, forbidden + " is an artificial budget field"


def test_serpapi_organic_batch(setup_db):
    db = setup_db
    service = make_service(db)

    mock_response = {"organic_results": [{"position": 1, "title": "Store X"}]}

    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        instance = MockSearch.return_value
        instance.get_dict.return_value = mock_response

        from app.routes.serpapi import batch_search
        from app.schemas.serpapi_schemas import BatchSearchRequest

        req = BatchSearchRequest(queries=["query1", "query2"], location="Secaucus, NJ")
        batch_res = batch_search(req=req, service=service)

        assert batch_res["total_requested"] == 2
        assert batch_res["successful"] == 2
        assert batch_res["failed"] == 0
        assert instance.get_dict.call_count == 2
