"""Reports freeze an evidence snapshot and render it; saved searches persist."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.main import app
from app.models.competitor import CompetitorObservation
from app.models.merchant import Merchant
from app.models.product_observation import ProductObservation

BASE = datetime(2026, 5, 1, 12, tzinfo=timezone.utc)
LOC = "Austin,Texas,United States"


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for table in ("reports", "saved_searches", "opportunities", "product_observations",
                  "competitor_observations", "merchants", "news_articles"):
        session.execute(text("DELETE FROM " + table))
    session.commit()
    for name, price in (("Alpha", 10.0), ("Beta", 14.0)):
        m = Merchant(name=name, normalized_name=name.lower(), status="verified",
                     entity_type="business", normalized_domain=name.lower() + ".example",
                     website="https://" + name.lower() + ".example", review_status="confirmed")
        session.add(m)
        session.commit()
        session.add(CompetitorObservation(merchant_id=m.id, market="Widgets", query="Widgets",
                                          location_resolved=LOC, source_type="local",
                                          discovery_method="google_maps_local",
                                          entity_type="business", observed_at=BASE))
        session.add(ProductObservation(
            merchant_id=m.id, product_query="Widgets", normalized_query="widgets",
            market="Widgets", location_resolved=LOC, product_name="Widget <b>X</b>",
            product_status="found", price_status="verified", price=price, currency="USD",
            source_url="https://" + name.lower() + ".example/p", observed_at=BASE))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


def test_report_snapshot_and_render(db, client):
    created = client.post("/api/reports", json={"market": "Widgets", "location": LOC}).json()
    assert created["has_data"] and created["competitors"] == 2
    assert created["verified_prices"] == 2
    page = client.get("/api/reports/" + str(created["id"]) + ".html")
    assert page.status_code == 200 and page.headers["content-type"].startswith("text/html")
    body = page.text
    assert "Methodology" in body and "Limitations" in body
    assert "Widget &lt;b&gt;X&lt;/b&gt;" in body          # provider text is escaped
    assert "<svg" in body                                 # chart drawn from the data
    assert "confirmed" in body
    assert "Print / Save as PDF" in body


def test_a_report_is_frozen(db, client):
    rid = client.post("/api/reports", json={"market": "Widgets", "location": LOC}).json()["id"]
    db.execute(text("DELETE FROM product_observations"))
    db.commit()
    assert "14.00 USD" in client.get("/api/reports/" + str(rid) + ".html").text


def test_report_list_and_delete(db, client):
    rid = client.post("/api/reports", json={"market": "Widgets"}).json()["id"]
    assert client.get("/api/reports").json()["total"] == 1
    assert client.delete("/api/reports/" + str(rid)).status_code == 204
    assert client.get("/api/reports/" + str(rid) + ".html").status_code == 404


def test_an_empty_selection_still_renders_honestly(db, client):
    rid = client.post("/api/reports", json={"market": "Nothing here"}).json()["id"]
    body = client.get("/api/reports/" + str(rid) + ".html").text
    assert "No verified prices were observed" in body


def test_saved_searches(db, client):
    first = client.post("/api/saved-searches",
                        json={"module": "research", "query": "coffee", "location": "Austin"})
    assert first.json()["created"] is True
    again = client.post("/api/saved-searches",
                        json={"module": "research", "query": "coffee", "location": "Austin"})
    assert again.json() == {"id": first.json()["id"], "created": False}
    assert client.post("/api/saved-searches",
                       json={"module": "nope", "query": "x"}).status_code == 400
    listed = client.get("/api/saved-searches?module=research").json()
    assert listed["total"] == 1
    assert client.delete("/api/saved-searches/" + str(first.json()["id"])).status_code == 204


def test_a_report_includes_opportunities(db, client):
    """Observed in the browser: a report failed (500) once opportunities
    existed, because their timestamps were not JSON serialisable."""
    m = db.query(Merchant).filter(Merchant.name == "Alpha").one()
    db.add(ProductObservation(
        merchant_id=m.id, product_query="Widgets", normalized_query="widgets",
        market="Widgets", location_resolved=LOC, product_name="Widget",
        product_status="found", price_status="verified", price=7.0, currency="USD",
        observed_at=BASE + timedelta(days=1)))
    db.commit()
    assert client.post("/api/opportunities/refresh").json()["total"] >= 1
    created = client.post("/api/reports", json={"market": "Widgets", "location": LOC})
    assert created.status_code == 200 and created.json()["opportunities"] >= 1
    body = client.get("/api/reports/" + str(created.json()["id"]) + ".html").text
    assert "Opportunities" in body and "cut the price" in body
