"""Google Trends, Google News, related questions, usage breakdown and budget.

All provider responses are mocked; nothing reaches the network.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.main import app
from app.models.news_article import NewsArticle
from app.models.trend_observation import TrendObservation
from app.services import api_budget
from app.services.search_interest_service import relative_change


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for table in ("search_cache", "api_usage", "trend_observations", "news_articles"):
        session.execute(text("DELETE FROM " + table))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


class Provider:
    """Returns ``payload`` and records the params of every live request."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def __call__(self, params):
        self.calls.append(dict(params))
        payload = self.payload

        class S:
            timeout = None

            @staticmethod
            def get_dict():
                return payload
        return S()


def live(client, path, payload, key="test-key"):
    provider = Provider(payload)
    with patch("app.routes.signals.settings") as s, \
            patch.object(api_budget, "GoogleSearch", side_effect=provider):
        s.SERPAPI_API_KEY = key
        return client.get(path), provider


def timeline(n, a_values, b_values=None):
    data = []
    for i in range(n):
        values = [{"query": "coffee", "extracted_value": a_values[i]}]
        if b_values:
            values.append({"query": "tea", "extracted_value": b_values[i]})
        data.append({"date": "w" + str(i), "timestamp": str(1700000000 + i * 604800),
                     "values": values})
    return {"interest_over_time": {"timeline_data": data}}


# ------------------------------------------------------------ search interest
def test_interest_over_time_builds_series_and_persists(db, client):
    payload = timeline(8, [10, 10, 20, 20, 30, 30, 40, 40], [5] * 8)
    r, provider = live(client, "/api/signals/search-interest?q=coffee,tea&geo=US", payload)
    assert r.status_code == 200
    body = r.json()
    assert provider.calls[0]["engine"] == "google_trends"
    assert provider.calls[0]["q"] == "coffee,tea"
    coffee = next(s for s in body["series"] if s["term"] == "coffee")
    assert coffee["point_count"] == 8 and coffee["relative_change_percent"] == 300.0
    assert "not search volume" in body["disclaimer"]
    assert db.query(TrendObservation).count() == 16


def test_a_cached_comparison_is_not_stored_twice(db, client):
    payload = timeline(8, [1] * 8)
    live(client, "/api/signals/search-interest?q=coffee", payload)
    r, provider = live(client, "/api/signals/search-interest?q=coffee", payload)
    assert r.json()["cache_hit"] is True and provider.calls == []
    assert db.query(TrendObservation).count() == 8


def test_too_few_points_report_no_change():
    assert relative_change([1, 2, 3]) is None
    assert relative_change([0, 0, 5, 5, 5, 5, 5, 5]) is None


@pytest.mark.parametrize("path", [
    "/api/signals/search-interest?q=",
    "/api/signals/search-interest?q=a,b,c,d,e,f",
    "/api/signals/search-interest?q=coffee&geo=usa",
    "/api/signals/search-interest?q=coffee&date=yesterday",
    "/api/signals/search-interest/regions?q=coffee&region=PLANET",
])
def test_unusable_requests_spend_nothing(client, path):
    r, provider = live(client, path, {})
    assert r.status_code == 400 and provider.calls == []


def test_no_key_is_503(client):
    r, _ = live(client, "/api/signals/search-interest?q=coffee", {}, key=None)
    assert r.status_code == 503


def test_regions_and_related(db, client):
    r, _ = live(client, "/api/signals/search-interest/regions?q=coffee&geo=US", {
        "interest_by_region": [{"location": "Oregon", "geo": "US-OR", "extracted_value": 100},
                               {"location": "Texas", "geo": "US-TX", "extracted_value": 40}]})
    assert [x["location"] for x in r.json()["regions"]] == ["Oregon", "Texas"]
    r, _ = live(client, "/api/signals/search-interest/related?q=coffee", {
        "related_queries": {"rising": [{"query": "cold brew", "value": "Breakout",
                                        "extracted_value": 5000}],
                            "top": [{"query": "coffee near me", "value": "100",
                                     "extracted_value": 100}]}})
    assert r.json()["rising"][0]["value_label"] == "Breakout"


def test_history_is_free(db, client):
    live(client, "/api/signals/search-interest?q=coffee", timeline(8, [1] * 8))
    r = client.get("/api/signals/search-interest/history")
    assert r.json()["requests"][0]["terms"] == ["coffee"]


def test_a_provider_failure_is_502(db, client):
    r, _ = live(client, "/api/signals/search-interest?q=coffee",
                {"error": "Something broke"})
    assert r.status_code == 502


# ------------------------------------------------------------ news
NEWS = {"news_results": [
    {"position": 1, "title": "Coffee prices rise", "link": "https://n.example/a",
     "source": {"name": "Example News"}, "date": "x", "iso_date": "2026-10-01T10:00:00Z"},
    {"position": 2, "title": "Cluster", "link": "https://n.example/b",
     "source": {"name": "Other"}, "iso_date": "2026-10-03T10:00:00Z",
     "stories": [{"title": "Nested", "link": "https://n.example/c",
                  "source": {"name": "Third"}, "iso_date": "2026-10-02T10:00:00Z"}]},
]}


def test_news_flattens_dates_and_dedupes(db, client):
    r, provider = live(client, "/api/signals/news?q=coffee+market&sort=date", NEWS)
    body = r.json()
    assert provider.calls[0]["engine"] == "google_news" and provider.calls[0]["so"] == "1"
    assert [a["link"][-1] for a in body["articles"]] == ["b", "c", "a"]
    assert body["articles"][0]["source_name"] == "Other"
    assert db.query(NewsArticle).count() == 3
    db.execute(text("DELETE FROM search_cache"))
    db.commit()
    live(client, "/api/signals/news?q=Coffee  Market&sort=date", NEWS)
    assert db.query(NewsArticle).count() == 3
    saved = client.get("/api/signals/news/saved?q=coffee market").json()
    assert saved["total"] == 3


def test_news_validation(client):
    assert live(client, "/api/signals/news?q=x", NEWS)[0].status_code == 400
    assert live(client, "/api/signals/news?q=coffee&gl=usa", NEWS)[0].status_code == 400


# ------------------------------------------------------------ related questions
def test_market_research_returns_related_questions(db, client):
    payload = {"organic_results": [{"position": 1, "title": "t", "link": "https://x.example"}],
               "related_questions": [{"question": "Is coffee healthy?", "snippet": "s",
                                      "link": "https://q.example"}],
               "related_searches": [{"query": "coffee beans"}, {"query": "coffee beans"}]}
    with patch("app.routes.serpapi.settings") as s, \
            patch.object(api_budget, "GoogleSearch", side_effect=Provider(payload)):
        s.SERPAPI_API_KEY = "test-key"
        body = client.get("/api/serpapi/search?q=coffee").json()
    assert body["related_questions"][0]["question"] == "Is coffee healthy?"
    assert body["related_searches"] == ["coffee beans"]


# ------------------------------------------------------------ budget and usage
def test_budget_blocks_live_searches_but_serves_cache(db, client):
    live(client, "/api/signals/search-interest?q=coffee", timeline(8, [1] * 8))
    with patch.object(api_budget.settings, "SERPAPI_MONTHLY_BUDGET", 1):
        cached, _ = live(client, "/api/signals/search-interest?q=coffee", timeline(8, [1] * 8))
        assert cached.status_code == 200
        blocked, provider = live(client, "/api/signals/search-interest?q=tea",
                                 timeline(8, [1] * 8))
    assert blocked.status_code == 429 and provider.calls == []
    assert "budget" in blocked.json()["detail"]


def test_usage_breakdown_groups_by_engine_and_prices(db, client):
    live(client, "/api/signals/search-interest?q=coffee", timeline(8, [1] * 8))
    with patch("app.routes.serpapi.fetch_account_usage",
               return_value={"plan_name": "Developer"}):
        body = client.get("/api/serpapi/usage/breakdown").json()
    row = next(r for r in body["by_endpoint"] if r["endpoint"] == "google_trends")
    assert row["credits_used"] == 1 and row["feature"] == "Search Interest"
    assert body["cost_per_search_usd"] == 0.015
    assert body["pricing_source"].startswith("https://serpapi.com")
    assert body["credits_used_this_month"] == 1
    assert body["monthly_budget"] is None
