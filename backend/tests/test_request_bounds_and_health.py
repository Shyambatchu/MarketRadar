"""Request bounds on credit-spending parameters, and an honest health check.

Found in the 2026-10-10 enhancement audit: ``num``, ``max_merchants`` and the
saved-list ``limit`` were unbounded (``limit=-1`` returned every row), so a
single request could fan out across an arbitrary number of paid searches. The
health endpoint returned a constant "ok" without checking anything.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import api_budget


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.parametrize("path", [
    "/api/serpapi/search?q=coffee&num=0",
    "/api/serpapi/search?q=coffee&num=101",
    "/api/competitors/search?market=coffee&location=Austin&num=500",
    "/api/products/search?q=beans&location=Austin&max_merchants=0",
    "/api/products/search?q=beans&location=Austin&max_merchants=50",
])
def test_out_of_range_spend_parameters_are_rejected_before_any_search(client, path):
    with patch("app.routes.serpapi.settings") as s1, \
            patch("app.routes.competitors.settings") as s2, \
            patch("app.routes.products.settings") as s3, \
            patch.object(api_budget, "GoogleSearch") as search:
        for s in (s1, s2, s3):
            s.SERPAPI_API_KEY = "test-key"
        r = client.get(path)
    assert r.status_code == 400
    assert "must be between" in r.json()["detail"]
    search.assert_not_called()


@pytest.mark.parametrize("path", ["/api/competitors?limit=-1", "/api/competitors?limit=0",
                                  "/api/products?limit=-1", "/api/products?limit=100000"])
def test_saved_list_limits_are_bounded(client, path):
    r = client.get(path)
    assert r.status_code == 400


def test_health_reports_dependencies_without_secrets(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert isinstance(body["serpapi_configured"], bool)
    assert isinstance(body["ai_provider_configured"], bool)
    assert "key" not in " ".join(str(v) for v in body.values()).lower()


def test_a_shopping_provider_failure_is_502_not_500(client):
    with patch("app.routes.prices.settings") as settings, \
            patch.object(api_budget, "GoogleSearch", side_effect=RuntimeError("down")):
        settings.SERPAPI_API_KEY = "test-key"
        r = client.get("/api/prices/search?q=widget")
    assert r.status_code == 502
