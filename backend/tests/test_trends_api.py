"""The /api/trends contract.

Every endpoint reads the observation history only: no provider request, no
SerpApi key required, no credit spent, and nothing written back.
"""
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

BASE = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def at(hours: float) -> datetime:
    return BASE + timedelta(hours=hours)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for table in ("product_observations", "competitor_observations", "merchants"):
        session.execute(text("DELETE FROM " + table))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(db):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def seed(db, prices=(), positions=()):
    merchant = Merchant(name="Shop A", normalized_name="shopa",
                        normalized_domain="shopa.example", status="verified",
                        entity_type="business")
    db.add(merchant)
    db.flush()
    for hours, price in prices:
        db.add(ProductObservation(
            merchant_id=merchant.id, product_query="Widget 2000",
            normalized_query="widget 2000", market="Hardware",
            location_resolved="Austin,Texas,United States",
            product_name="Widget 2000", product_status="found",
            price_status="verified", price=price, currency="USD",
            evidence_scope="catalog", inventory_confirmed=False,
            observed_at=at(hours)))
    for hours, position in positions:
        db.add(CompetitorObservation(
            merchant_id=merchant.id, market="Hardware", query="hardware",
            location_resolved="Austin,Texas,United States", source_type="local",
            discovery_method="google_maps_local", entity_type="business",
            status="verified", position=position, observed_at=at(hours)))
    db.commit()
    return merchant


def test_summary_endpoint(client, db):
    seed(db, prices=[(0, 20.0)], positions=[(0, 3)])
    response = client.get("/api/trends/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["persisted"] is False
    assert body["product_observations"] == 1
    assert body["verified_price_observations"] == 1
    assert body["insufficient_history"] is True
    assert body["detail"]


def test_summary_on_empty_history(client, db):
    body = client.get("/api/trends/summary").json()
    assert body["competitor_observations"] == 0
    assert body["insufficient_history"] is True
    assert "No observations" in body["detail"]


def test_price_endpoint_reports_a_real_movement(client, db):
    seed(db, prices=[(0, 20.0), (1, 20.0), (200, 18.0)])
    body = client.get("/api/trends/prices").json()

    assert body["total"] == 1
    assert body["analyzable"] == 1
    series = body["series"][0]
    assert series["raw_observations"] == 3
    assert series["distinct_points"] == 2, "the cache duplicate must collapse"
    assert series["direction"] == "down"
    assert series["change_absolute"] == -2.0


def test_price_endpoint_refuses_to_call_a_single_reading_stable(client, db):
    seed(db, prices=[(0, 20.0), (1, 20.0), (2, 20.0)])
    body = client.get("/api/trends/prices").json()

    series = body["series"][0]
    assert series["status"] == "insufficient_history"
    assert series["direction"] is None
    assert body["analyzable"] == 0
    assert "measured twice" in body["detail"]


def test_price_endpoint_filters_by_query_and_market(client, db):
    seed(db, prices=[(0, 20.0)])
    assert client.get("/api/trends/prices",
                      params={"q": "Widget 2000"}).json()["total"] == 1
    assert client.get("/api/trends/prices",
                      params={"q": "Gadget 3000"}).json()["total"] == 0
    assert client.get("/api/trends/prices",
                      params={"market": "Hardware"}).json()["total"] == 1
    assert client.get("/api/trends/prices",
                      params={"market": "Coffee"}).json()["total"] == 0


def test_availability_endpoint(client, db):
    seed(db, prices=[(0, 20.0)])
    body = client.get("/api/trends/availability").json()
    assert body["total"] == 1
    assert body["series"][0]["metric"] == "availability"


def test_visibility_endpoint(client, db):
    seed(db, positions=[(0, 5), (200, 2)])
    body = client.get("/api/trends/visibility", params={"metric": "position"}).json()
    assert body["total"] == 1
    assert body["series"][0]["direction"] == "down"


def test_visibility_rejects_an_unsupported_metric(client, db):
    response = client.get("/api/trends/visibility", params={"metric": "popularity"})
    assert response.status_code == 400


def test_merchants_endpoint(client, db):
    seed(db, positions=[(0, 3), (200, 3)])
    body = client.get("/api/trends/merchants").json()
    assert body["total"] == 1
    presence = body["merchants"][0]
    assert presence["merchant"] == "Shop A"
    assert presence["present_in_latest"] is True
    assert presence["distinct_searches"] == 2


def test_no_endpoint_makes_a_provider_request(client, db):
    """Trends must never spend a credit."""
    seed(db, prices=[(0, 20.0)], positions=[(0, 3)])
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        for path in ("/api/trends/summary", "/api/trends/prices",
                     "/api/trends/availability", "/api/trends/visibility",
                     "/api/trends/merchants"):
            assert client.get(path).status_code == 200
        assert MockSearch.call_count == 0


def test_endpoints_do_not_require_a_serpapi_key(client, db):
    """No 503 path exists: trends reads the database only."""
    from app.config import settings

    original = settings.SERPAPI_API_KEY
    try:
        settings.SERPAPI_API_KEY = None
        assert client.get("/api/trends/summary").status_code == 200
        assert client.get("/api/trends/prices").status_code == 200
    finally:
        settings.SERPAPI_API_KEY = original


def test_endpoints_write_nothing(client, db):
    seed(db, prices=[(0, 20.0)], positions=[(0, 3)])
    before = (db.query(Merchant).count(),
              db.query(CompetitorObservation).count(),
              db.query(ProductObservation).count())

    for path in ("/api/trends/summary", "/api/trends/prices",
                 "/api/trends/availability", "/api/trends/visibility",
                 "/api/trends/merchants"):
        client.get(path)

    assert before == (db.query(Merchant).count(),
                      db.query(CompetitorObservation).count(),
                      db.query(ProductObservation).count())


def test_no_artificial_budget_field_in_the_trend_contract():
    from app.schemas.trend import TrendListResponse, TrendSummaryResponse

    for model in (TrendSummaryResponse, TrendListResponse):
        for name in ("daily_limit", "max_credits", "searches_remaining",
                     "budget_exhausted"):
            assert name not in model.model_fields, name
