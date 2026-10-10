"""CSV exports match the stored evidence and are safe to open in a spreadsheet."""
import csv
import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.main import app
from app.models.merchant import Merchant
from app.models.product_observation import ProductObservation

BASE = datetime(2026, 5, 1, 12, tzinfo=timezone.utc)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for table in ("product_observations", "competitor_observations", "merchants",
                  "audit_events"):
        session.execute(text("DELETE FROM " + table))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


def read(response):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    return list(csv.DictReader(io.StringIO(response.text.lstrip("﻿"))))


def seed(db):
    m = Merchant(name="=HYPERLINK(\"x\")", normalized_name="x", status="verified",
                 entity_type="business", normalized_domain="alpha.example")
    db.add(m)
    db.commit()
    for day, price in ((0, 10.0), (1, 12.0)):
        db.add(ProductObservation(
            merchant_id=m.id, product_query="Widget", normalized_query="widget",
            market="Widgets", location_resolved="Austin,Texas,United States",
            product_name="Widget", product_status="found", price_status="verified",
            price=price, currency="EUR", source_type="merchant_website_indexed",
            source_url="https://alpha.example/p", observed_at=BASE + timedelta(days=day)))
    db.add(ProductObservation(
        merchant_id=m.id, product_query="Widget", normalized_query="widget",
        market="Widgets", product_status="found", price_status="unavailable",
        observed_at=BASE))
    db.commit()


def test_competitor_export_neutralises_formulas(db, client):
    seed(db)
    rows = read(client.get("/api/export/competitors.csv"))
    assert len(rows) == 1
    assert rows[0]["name"].startswith("'=")


def test_product_and_price_exports(db, client):
    seed(db)
    assert len(read(client.get("/api/export/products.csv?q=Widget"))) == 3
    prices = read(client.get("/api/export/prices.csv?q=Widget"))
    assert len(prices) == 2
    assert {p["currency"] for p in prices} == {"EUR"}


def test_alert_and_trend_exports(db, client):
    seed(db)
    alerts = read(client.get("/api/export/price-alerts.csv"))
    assert [a["type"] for a in alerts] == ["price_increase"]
    points = read(client.get("/api/export/trends.csv?signal=prices"))
    assert [p["value"] for p in points] == ["10.0", "12.0"]


def test_export_validation(client):
    assert client.get("/api/export/trends.csv?signal=nope").status_code == 400
    assert client.get("/api/export/products.csv?limit=0").status_code == 400
