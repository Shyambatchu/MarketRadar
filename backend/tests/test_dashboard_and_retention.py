"""Dashboard aggregates stored rows only; expired cache rows are pruned."""
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
from app.models.serpapi_models import SearchCache
from app.services.api_budget import prune_expired_cache

NOW = datetime.now(timezone.utc)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for table in ("product_observations", "competitor_observations", "merchants",
                  "opportunities", "reports", "search_cache", "api_usage"):
        session.execute(text("DELETE FROM " + table))
    session.commit()
    yield session
    session.close()


def seed(db):
    m = Merchant(name="Alpha", normalized_name="alpha", status="verified",
                 entity_type="business", review_status="confirmed")
    db.add(m)
    db.commit()
    db.add(CompetitorObservation(merchant_id=m.id, market="Widgets", location_resolved="X",
                                 source_type="local", observed_at=NOW - timedelta(days=40)))
    for days, price in ((2, 10.0), (1, 13.0)):
        db.add(ProductObservation(merchant_id=m.id, product_query="W", normalized_query="w",
                                  market="Widgets", location_resolved="X",
                                  product_status="found", price_status="verified",
                                  price=price, currency="USD",
                                  observed_at=NOW - timedelta(days=days)))
    db.commit()


def test_dashboard_counts_and_changes(db):
    seed(db)
    body = TestClient(app).get("/api/dashboard").json()
    assert body["counts"]["businesses"] == 1
    assert body["counts"]["confirmed_competitors"] == 1
    assert body["counts"]["verified_prices"] == 2
    assert body["recent_changes_total"] == 1
    assert body["recent_changes"][0]["type"] == "price_increase"
    assert body["health"]["monthly_budget"] is None


def test_dashboard_filters(db):
    seed(db)
    client = TestClient(app)
    assert client.get("/api/dashboard?days=7").json()["counts"]["competitor_observations"] == 0
    assert client.get("/api/dashboard?market=Other").json()["counts"]["businesses"] == 0
    assert client.get("/api/dashboard?days=0").status_code == 400


def test_old_expired_cache_rows_are_pruned(db):
    db.add(SearchCache(cache_key="old", response_data="{}",
                       expires_at=NOW - timedelta(days=60)))
    db.add(SearchCache(cache_key="recent", response_data="{}",
                       expires_at=NOW - timedelta(days=1)))
    db.add(SearchCache(cache_key="live", response_data="{}",
                       expires_at=NOW + timedelta(days=1)))
    db.commit()
    assert prune_expired_cache(engine) == 1
    db.expire_all()
    assert {r.cache_key for r in db.query(SearchCache).all()} == {"recent", "live"}
