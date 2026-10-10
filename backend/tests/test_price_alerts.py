"""Price change detection: increases, decreases, new and missing offers,
outliers, dispersion and conflicts -- from stored verified evidence only."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.main import app
from app.models.merchant import Merchant
from app.models.product_observation import ProductObservation
from app.services.price_change_service import PriceChangeService

BASE = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
LOC = "Austin,Texas,United States"


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for table in ("product_observations", "competitor_observations", "merchants"):
        session.execute(text("DELETE FROM " + table))
    session.commit()
    yield session
    session.close()


def merchant(db, name):
    m = Merchant(name=name, normalized_name=name.lower(), status="verified",
                 entity_type="business", normalized_domain=name.lower() + ".example")
    db.add(m)
    db.commit()
    return m


def obs(db, m, price, run, currency="USD", price_status="verified", location=LOC,
        source_type="merchant_website_indexed"):
    db.add(ProductObservation(
        merchant_id=m.id, product_query="Widget", normalized_query="widget",
        market="Widgets", location_resolved=location, product_name="Widget",
        product_status="found", price_status=price_status,
        price=price, currency=currency, source_type=source_type,
        source_url="https://" + m.normalized_domain + "/p/widget",
        observed_at=BASE + timedelta(days=run)))
    db.commit()


def types(response):
    return sorted(a.type for a in response.alerts)


def test_one_reading_produces_no_change(db):
    a = merchant(db, "Alpha")
    obs(db, a, 10.0, 0)
    assert PriceChangeService(db).detect().alerts == []


def test_a_repeated_cached_reading_is_not_a_change(db):
    a = merchant(db, "Alpha")
    for run in range(3):
        obs(db, a, 10.0, run)
    assert [x for x in PriceChangeService(db).detect().alerts
            if x.type.startswith("price_")] == []


def test_increase_and_decrease_are_detected_with_evidence(db):
    a, b = merchant(db, "Alpha"), merchant(db, "Beta")
    obs(db, a, 10.0, 0); obs(db, b, 20.0, 0)
    obs(db, a, 12.0, 1); obs(db, b, 18.0, 1)
    alerts = {x.merchant: x for x in PriceChangeService(db).detect().alerts
              if x.type.startswith("price_")}
    assert alerts["Alpha"].type == "price_increase"
    assert alerts["Alpha"].change_percent == 20.0
    assert alerts["Beta"].type == "price_decrease"
    assert len(alerts["Alpha"].record_ids) == 2
    assert alerts["Alpha"].source_urls == ["https://alpha.example/p/widget"]


def test_a_change_below_the_threshold_is_ignored(db):
    a = merchant(db, "Alpha")
    obs(db, a, 100.0, 0); obs(db, a, 102.0, 1)
    assert PriceChangeService(db).detect().alerts == []
    assert types(PriceChangeService(db).detect(min_change_percent=1)) == ["price_increase"]


def test_unverified_prices_are_never_read(db):
    a = merchant(db, "Alpha")
    obs(db, a, 10.0, 0); obs(db, a, 50.0, 1, price_status="unavailable")
    assert PriceChangeService(db).detect().alerts == []


def test_series_never_cross_locations_or_currencies(db):
    a = merchant(db, "Alpha")
    obs(db, a, 10.0, 0); obs(db, a, 20.0, 1, location="Lyon,France")
    obs(db, a, 30.0, 2, currency="EUR")
    assert [x for x in PriceChangeService(db).detect().alerts
            if x.type.startswith("price_")] == []


def test_new_and_missing_offers_need_an_earlier_run(db):
    a, b, c = merchant(db, "Alpha"), merchant(db, "Beta"), merchant(db, "Gamma")
    obs(db, a, 10.0, 0); obs(db, b, 10.0, 0)
    obs(db, a, 10.0, 1); obs(db, c, 10.0, 1)
    alerts = {x.merchant: x.type for x in PriceChangeService(db).detect().alerts}
    assert alerts["Gamma"] == "new_offer"
    assert alerts["Beta"] == "not_observed_in_latest"
    missing = next(x for x in PriceChangeService(db).detect().alerts if x.merchant == "Beta")
    assert "not proof" in missing.explanation


def test_first_run_offers_are_not_new(db):
    a = merchant(db, "Alpha")
    obs(db, a, 10.0, 0)
    assert "new_offer" not in types(PriceChangeService(db).detect())


def test_outlier_and_dispersion(db):
    ms = [merchant(db, n) for n in ("A1", "A2", "A3", "A4", "A5")]
    for m, p in zip(ms, (10.0, 10.5, 11.0, 10.2, 40.0)):
        obs(db, m, p, 0)
    result = PriceChangeService(db).detect()
    outliers = [x for x in result.alerts if x.type == "outlier"]
    assert [x.merchant for x in outliers] == ["A5"]
    assert "price_dispersion" in types(result)


def test_conflicting_prices_in_one_run(db):
    a = merchant(db, "Alpha")
    obs(db, a, 10.0, 0)
    obs(db, a, 14.0, 0, source_type="google_shopping")
    assert "conflicting_prices" in types(PriceChangeService(db).detect())


def test_the_endpoint_validates_and_filters(db):
    a = merchant(db, "Alpha")
    obs(db, a, 10.0, 0); obs(db, a, 12.0, 1)
    client = TestClient(app)
    r = client.get("/api/prices/alerts?q=Widget&location=" + LOC)
    assert r.status_code == 200 and r.json()["total"] == 1
    assert client.get("/api/prices/alerts?location=Nowhere").json()["total"] == 0
    assert client.get("/api/prices/alerts?min_change_percent=-1").status_code == 400
