"""Provider reliability: timeouts, retries, error classification, empty results.

Found in the 2026-10-10 enhancement audit:

* the SerpApi client's default timeout is 60000 seconds and was never
  overridden, so one stalled request could hold a worker for most of a day;
* SerpApi reports "Google hasn't returned any results for this query." in the
  top-level ``error`` key of a *successful* search, and every such search was
  turned into a provider failure (502 in Market Research and Competitors,
  ``provider_request_failed`` for a merchant catalogue in Products);
* nothing was retried, and no failure was classified.

No test here reaches the network or spends a credit.
"""
from unittest.mock import patch

import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.main import app
from app.models.serpapi_models import ApiUsage, SearchCache
from app.services import api_budget
from app.services.api_budget import (
    ERROR_AUTH, ERROR_PROVIDER, ERROR_QUOTA, ERROR_REQUEST, ERROR_TRANSIENT,
    REQUEST_TIMEOUT_SECONDS, classify_error, is_empty_result,
)

EMPTY = {
    "search_metadata": {"status": "Success"},
    "search_information": {"organic_results_state": "Fully empty"},
    "error": "Google hasn't returned any results for this query.",
}


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for table in ("search_cache", "api_usage"):
        session.execute(text("DELETE FROM " + table))
    session.commit()
    yield session
    session.close()


class ScriptedSearch:
    """Plays back one outcome per request: a dict, or an exception to raise."""

    script = []
    created = []

    def __init__(self, params):
        self.params = dict(params)
        self.timeout = None
        ScriptedSearch.created.append(self)

    def get_dict(self):
        outcome = ScriptedSearch.script.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def run(db, *outcomes, key="k"):
    ScriptedSearch.script = list(outcomes)
    ScriptedSearch.created = []
    manager = api_budget.ApiBudgetManager(db, "test-key")
    sleeps = []
    manager._sleep = sleeps.append
    with patch.object(api_budget, "GoogleSearch", ScriptedSearch):
        result = manager.execute_search(key, {"q": "x"}, "google_organic")
    return manager, result, sleeps


# ------------------------------------------------------------ timeout
def test_every_request_carries_a_bounded_timeout(db):
    run(db, {"organic_results": []})
    assert ScriptedSearch.created[0].timeout == REQUEST_TIMEOUT_SECONDS
    assert REQUEST_TIMEOUT_SECONDS <= 60


# ------------------------------------------------------------ empty results
def test_an_empty_search_is_a_result_not_a_failure(db):
    manager, result, _ = run(db, EMPTY)
    assert result == EMPTY
    assert manager.last_error is None
    usage = db.query(ApiUsage).one()
    assert usage.success is True


def test_an_empty_search_is_cached_like_any_answer(db):
    run(db, EMPTY, key="empty")
    assert db.query(SearchCache).filter(SearchCache.cache_key == "empty").count() == 1


def test_an_error_status_is_never_read_as_empty():
    payload = dict(EMPTY, search_metadata={"status": "Error"})
    assert not is_empty_result(payload)


def test_market_research_reports_no_results_rather_than_502(db):
    client = TestClient(app)
    with patch("app.routes.serpapi.settings") as settings, \
            patch.object(api_budget, "GoogleSearch", ScriptedSearch):
        settings.SERPAPI_API_KEY = "test-key"
        ScriptedSearch.script = [EMPTY]
        r = client.get("/api/serpapi/search?q=nothing+matches+this")
    assert r.status_code == 200
    assert r.json()["provider_status"] == "no_results"


# ------------------------------------------------------------ retries
def test_a_timeout_is_retried_then_succeeds(db):
    manager, result, sleeps = run(
        db, requests.Timeout("slow"), {"organic_results": [{"title": "a"}]})
    assert result == {"organic_results": [{"title": "a"}]}
    assert len(ScriptedSearch.created) == 2
    assert sleeps == [api_budget.RETRY_BACKOFF_SECONDS]
    # One logical request, one usage row, settled as a success.
    usage = db.query(ApiUsage).one()
    assert usage.success is True and usage.credits_used == 1


def test_retries_stop_after_the_limit_and_back_off_exponentially(db):
    failures = [requests.ConnectionError("down")] * (api_budget.MAX_RETRIES + 1)
    manager, result, sleeps = run(db, *failures)
    assert result is None
    assert len(ScriptedSearch.created) == api_budget.MAX_RETRIES + 1
    assert sleeps == [api_budget.RETRY_BACKOFF_SECONDS * 2 ** i
                      for i in range(api_budget.MAX_RETRIES)]
    assert manager.last_error_kind == ERROR_TRANSIENT
    usage = db.query(ApiUsage).one()
    assert usage.success is False and usage.credits_used == 0


@pytest.mark.parametrize("message,kind", [
    ("Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key",
     ERROR_AUTH),
    ("Your account has run out of searches.", ERROR_QUOTA),
    ("Unsupported `Nowhere` location - location parameter.", ERROR_REQUEST),
])
def test_a_permanent_failure_is_not_retried(db, message, kind):
    manager, result, sleeps = run(db, {"error": message})
    assert result is None
    assert len(ScriptedSearch.created) == 1
    assert sleeps == []
    assert manager.last_error_kind == kind
    assert manager.last_error == message


def test_an_unclassified_fault_is_not_retried(db):
    manager, result, sleeps = run(db, RuntimeError("down"))
    assert result is None and sleeps == []
    assert manager.last_error_kind == ERROR_PROVIDER


def test_the_providers_try_again_later_is_retried(db):
    manager, result, _ = run(
        db, {"error": "We couldn't get valid results for this search. Please try again later."},
        {"organic_results": []})
    assert result == {"organic_results": []}


def test_classification_of_network_exceptions():
    assert classify_error("x", requests.Timeout()) == ERROR_TRANSIENT
    assert classify_error("x", requests.ConnectionError()) == ERROR_TRANSIENT
