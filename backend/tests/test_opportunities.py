"""Opportunity scoring: explicit formula, missing-data handling, review."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.main import app
from app.models.merchant import Merchant
from app.models.product_observation import ProductObservation
from app.models.trend_observation import TrendObservation
from app.services import opportunity_service
from app.services.opportunity_service import OpportunityService, freshness, score

NOW = datetime.now(timezone.utc).replace(microsecond=0)
LOC = "Austin,Texas,United States"


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for table in ("opportunities", "audit_events", "product_observations",
                  "competitor_observations", "merchants", "trend_observations"):
        session.execute(text("DELETE FROM " + table))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


def merchant(db, name, review=None):
    m = Merchant(name=name, normalized_name=name.lower(), status="verified",
                 entity_type="business", normalized_domain=name.lower() + ".example",
                 review_status=review)
    db.add(m)
    db.commit()
    return m


def price(db, m, value, days_ago):
    db.add(ProductObservation(
        merchant_id=m.id, product_query="Widget", normalized_query="widget",
        market="Widgets", location_resolved=LOC, product_name="Widget",
        product_status="found", price_status="verified", price=value, currency="USD",
        source_type="merchant_website_indexed", source_url="https://x.example/" + m.name,
        observed_at=NOW - timedelta(days=days_ago)))
    db.commit()


# ------------------------------------------------------------ formula
def test_score_is_the_weighted_sum_of_normalised_inputs():
    result = score({"impact": 1.0, "confidence": 1.0, "freshness": 1.0, "relevance": 1.0})
    assert result["score"] == 100.0
    result = score({"impact": 0.5, "confidence": 0.0, "freshness": 0.0, "relevance": 0.0})
    assert result["score"] == round(100 * result["weights"]["impact"] * 0.5, 1)
    assert abs(sum(result["weights"].values()) - 1.0) < 1e-3


def test_a_missing_input_contributes_zero_and_is_reported():
    result = score({"impact": 1.0, "confidence": 1.0, "freshness": None, "relevance": 1.0})
    assert result["missing"] == ["freshness"]
    assert result["contributions"]["freshness"] == 0
    assert result["inputs"]["freshness"] is None


def test_inputs_are_clamped():
    assert score({"impact": 7, "confidence": -1, "freshness": 1, "relevance": 1})[
        "inputs"]["impact"] == 1.0


def test_freshness_halves_each_half_life():
    half = opportunity_service.settings.OPPORTUNITY_FRESHNESS_HALF_LIFE_DAYS
    assert freshness(NOW, NOW) == 1.0
    assert abs(freshness(NOW - timedelta(days=half), NOW) - 0.5) < 1e-3
    assert freshness(None, NOW) is None


# ------------------------------------------------------------ generation
def test_refresh_builds_leads_from_price_evidence(db, client):
    a, b = merchant(db, "Alpha", review="confirmed"), merchant(db, "Beta")
    price(db, a, 10.0, 3); price(db, a, 8.0, 1)
    price(db, b, 10.0, 3); price(db, b, 16.0, 1)
    body = client.post("/api/opportunities/refresh").json()
    cats = {o["category"] for o in body["opportunities"]}
    assert {"competitor_price_move", "pricing_headroom", "price_gap"} <= cats
    move = next(o for o in body["opportunities"] if o["category"] == "competitor_price_move")
    assert move["breakdown"]["inputs"]["relevance"] == 1.0
    assert move["evidence"]["source_urls"]
    assert "not a probability" in body["disclaimer"]
    scores = [o["score"] for o in body["opportunities"]]
    assert scores == sorted(scores, reverse=True)


def test_rejected_competitors_produce_no_leads(db):
    a = merchant(db, "Alpha", review="rejected")
    price(db, a, 10.0, 3); price(db, a, 5.0, 1)
    assert [o for o in OpportunityService(db).refresh()
            if o.category == "competitor_price_move"] == []


def test_refresh_is_idempotent_and_keeps_review_status(db, client):
    a = merchant(db, "Alpha")
    price(db, a, 10.0, 3); price(db, a, 5.0, 1)
    first = client.post("/api/opportunities/refresh").json()["opportunities"][0]
    client.patch("/api/opportunities/" + str(first["id"]), json={"status": "saved"})
    again = client.post("/api/opportunities/refresh").json()["opportunities"]
    same = next(o for o in again if o["id"] == first["id"])
    assert same["status"] == "saved"
    assert len([o for o in again if o["category"] == first["category"]]) == 1


def test_dismissed_leads_are_hidden_unless_asked_for(db, client):
    a = merchant(db, "Alpha")
    price(db, a, 10.0, 3); price(db, a, 5.0, 1)
    opp = client.post("/api/opportunities/refresh").json()["opportunities"][0]
    client.patch("/api/opportunities/" + str(opp["id"]), json={"status": "dismissed"})
    assert opp["id"] not in [o["id"] for o in client.get("/api/opportunities").json()["opportunities"]]
    assert client.get("/api/opportunities?status=dismissed").json()["total"] == 1


def test_rising_search_interest_becomes_a_lead(db):
    for i, value in enumerate([10, 10, 10, 10, 20, 20, 30, 30]):
        db.add(TrendObservation(keyword="cold brew", region="US", interest_value=value,
                                request_key="TIMESERIES|cold brew|US|today 12-m",
                                data_type="TIMESERIES", timeframe="today 12-m",
                                partial=False, point_at=NOW - timedelta(weeks=8 - i),
                                observed_at=NOW))
    db.commit()
    leads = [o for o in OpportunityService(db).refresh()
             if o.category == "rising_search_interest"]
    assert len(leads) == 1 and "200.0%" in leads[0].title


def test_update_validation(db, client):
    assert client.patch("/api/opportunities/999", json={"status": "saved"}).status_code == 404
    a = merchant(db, "Alpha")
    price(db, a, 10.0, 3); price(db, a, 5.0, 1)
    opp = client.post("/api/opportunities/refresh").json()["opportunities"][0]
    assert client.patch("/api/opportunities/" + str(opp["id"]),
                        json={"status": "won"}).status_code == 400


def test_method_and_export(db, client):
    method = client.get("/api/opportunities/method").json()
    assert "score = 100" in method["formula"]
    a = merchant(db, "Alpha")
    price(db, a, 10.0, 3); price(db, a, 5.0, 1)
    client.post("/api/opportunities/refresh")
    r = client.get("/api/export/opportunities.csv")
    assert r.status_code == 200 and "suggested_action" in r.text


def test_sources_explain_what_evidence_exists(db, client):
    body = client.get("/api/opportunities/sources").json()
    assert body["price_evidence"]["verified_prices"] == 0
    assert body["price_evidence"]["products_with_history"] == 0
    a, b = merchant(db, "Alpha"), merchant(db, "Beta")
    price(db, a, 10.0, 3); price(db, a, 8.0, 1); price(db, b, 14.0, 1)
    client.post("/api/opportunities/refresh")
    body = client.get("/api/opportunities/sources").json()
    assert body["price_evidence"]["verified_prices"] == 3
    assert body["price_evidence"]["products_tracked"] == 1
    assert body["price_evidence"]["products_with_history"] == 1
    assert body["price_evidence"]["signals"]["price_moves"] == 1
    assert body["active_by_category"]["competitor_price_move"] == 1
    assert body["last_refreshed_at"]
