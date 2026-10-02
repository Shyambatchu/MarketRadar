"""Market Pulse: read-only analysis over the observation history.

Two properties matter most and are tested hardest:

1. It never writes and never calls a provider. It is the top of the stack,
   consuming what Competitors and Products produced, so a mutation or a credit
   spent here would be a layering violation as much as a bug.
2. It states nothing the evidence does not support. No market "grows", no
   competitor "wins", no business "disappears", and one measurement read
   repeatedly never becomes a trend or an average.
"""
from datetime import datetime, timedelta, timezone

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine, get_db
from app.main import app
from app.models.competitor import CompetitorObservation
from app.models.merchant import Merchant
from app.models.product_observation import ProductObservation
from app.services.pulse_service import MarketPulseService

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
def service(db):
    return MarketPulseService(db=db)


@pytest.fixture
def client(db):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    yield TestClient(app)
    app.dependency_overrides.clear()


AUSTIN = "Austin,Texas,United States"
HYDERABAD = "Hyderabad,Telangana,India"


def merchant(db, name, domain=None, status="verified", address="1 Main St"):
    row = Merchant(name=name, normalized_name=name.lower().replace(" ", ""),
                   normalized_domain=domain, status=status,
                   entity_type="business", address=address)
    db.add(row)
    db.flush()
    db.commit()
    return row


def competitor_obs(db, m, market="Coffee Shops", location=AUSTIN, position=None,
                   rating=None, reviews=None, observed_at=None,
                   source_type="local", method="google_maps_local"):
    db.add(CompetitorObservation(
        merchant_id=m.id, market=market, query=market.lower(),
        location_resolved=location, source_type=source_type,
        discovery_method=method, entity_type="business", status="verified",
        position=position, rating=rating, reviews=reviews,
        observed_at=observed_at or at(0)))
    db.commit()


def product_obs(db, m, query="Widget 2000", market="Coffee Shops", location=AUSTIN,
                price=None, price_status="verified", product_status="found",
                observed_at=None, reason=None, scope="catalog"):
    db.add(ProductObservation(
        merchant_id=m.id, product_query=query, normalized_query=query.lower(),
        market=market, location_resolved=location, product_name=query,
        product_status=product_status, price_status=price_status,
        verification_reason=reason, price=price,
        currency="USD" if price else None,
        source_type="merchant_website_indexed", discovery_method="indexed_search",
        source_url="https://example.test/product/x", source_domain="example.test",
        page_type="product", evidence_scope=scope, inventory_confirmed=False,
        observed_at=observed_at or at(0)))
    db.commit()


# ============================================================ 1: no data
def test_snapshot_with_no_data(service, db):
    result = service.snapshot()
    assert result.has_data is False
    assert result.competitors == []
    assert result.products == []
    assert result.prices == []
    assert result.detail
    assert result.persisted is False


def test_options_with_no_data(service, db):
    result = service.options()
    assert result.total == 0
    assert "No observations" in result.detail


# ============================================================ 2,3: sections
def test_snapshot_with_competitor_data(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1, rating=4.5, reviews=120)

    result = service.snapshot(market="Coffee Shops", location=AUSTIN)
    assert result.has_data is True
    assert result.context.merchants == 1
    assert result.context.competitor_observations == 1
    entry = result.competitors[0]
    assert entry.name == "Bean & Brew"
    assert entry.status == "verified"
    assert entry.discovery_methods == ["google_maps_local"]
    assert entry.present_in_latest is True


def test_snapshot_with_product_data(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    product_obs(db, m, price=19.99)

    result = service.snapshot(market="Coffee Shops", location=AUSTIN)
    assert result.context.product_observations == 1
    product = result.products[0]
    assert product.product_status == "found"
    assert product.evidence_scope == "catalog"
    assert product.inventory_confirmed is False


# ============================================================ 4,5: prices
def test_verified_price_appears_in_price_signals(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    product_obs(db, m, price=19.99, price_status="verified")

    result = service.snapshot(market="Coffee Shops", location=AUSTIN)
    assert len(result.prices) == 1
    assert result.prices[0].price == 19.99
    assert result.data_quality.prices_verified == 1


def test_unverified_price_never_enters_price_analysis(service, db):
    """An unverified price was never established as this product's price."""
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    product_obs(db, m, price=99.0, price_status="unavailable",
                reason="price_not_product_specific")
    product_obs(db, m, price=None, price_status="unknown",
                product_status="unknown", observed_at=at(1))

    result = service.snapshot(market="Coffee Shops", location=AUSTIN)
    assert result.prices == [], "no unverified price may appear"
    assert result.price_statistics.distinct_measurements == 0
    assert result.price_statistics.sufficient is False
    # The product itself is still reported, with its state intact.
    assert len(result.products) == 2
    assert result.data_quality.prices_unavailable == 1
    assert result.data_quality.prices_unknown == 1


def test_unknown_product_is_not_reported_as_absent(service, db):
    """Unknown must never be silently turned into a negative finding."""
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    product_obs(db, m, product_status="unknown", price_status="unknown")

    result = service.snapshot(market="Coffee Shops", location=AUSTIN)
    assert result.data_quality.products_unknown == 1
    assert result.data_quality.products_not_found == 0
    assert any("not a finding" in note for note in result.data_quality.notes)


# ============================================================ statistics
def test_a_single_price_is_not_averaged(service, db):
    """One measurement read repeatedly is a sample of one."""
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    for hours in (0, 1, 2):
        product_obs(db, m, price=19.99, observed_at=at(hours))

    stats = service.snapshot(market="Coffee Shops", location=AUSTIN).price_statistics
    assert stats.distinct_measurements == 1
    assert stats.sufficient is False
    assert stats.average is None
    assert stats.lowest is None and stats.highest is None
    assert "Too few to summarise" in stats.detail


def test_statistics_appear_once_enough_distinct_measurements_exist(service, db):
    a = merchant(db, "Shop A", "a.example")
    b = merchant(db, "Shop B", "b.example")
    product_obs(db, a, price=10.0)
    product_obs(db, b, price=20.0)

    stats = service.snapshot(market="Coffee Shops", location=AUSTIN).price_statistics
    assert stats.distinct_measurements == 2
    assert stats.sufficient is True
    assert stats.lowest == 10.0 and stats.highest == 20.0
    assert stats.average == 15.0
    assert "not a market rate" in stats.detail


# ============================================================ 6-9: separation
def test_markets_remain_separated(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, market="Coffee Shops")
    competitor_obs(db, m, market="Bakeries", observed_at=at(1))

    coffee = service.snapshot(market="Coffee Shops", location=AUSTIN)
    assert coffee.context.competitor_observations == 1
    bakeries = service.snapshot(market="Bakeries", location=AUSTIN)
    assert bakeries.context.competitor_observations == 1


def test_locations_remain_separated(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, location=AUSTIN)
    competitor_obs(db, m, location=HYDERABAD, observed_at=at(1))

    austin = service.snapshot(market="Coffee Shops", location=AUSTIN)
    hyd = service.snapshot(market="Coffee Shops", location=HYDERABAD)
    assert austin.context.competitor_observations == 1
    assert hyd.context.competitor_observations == 1
    assert austin.context.location == AUSTIN
    assert hyd.context.location == HYDERABAD


def test_products_remain_separated(service, db):
    m = merchant(db, "Shop A", "a.example")
    product_obs(db, m, query="Widget 2000", price=10.0)
    product_obs(db, m, query="Gadget 3000", price=30.0, observed_at=at(1))

    result = service.snapshot(market="Coffee Shops", location=AUSTIN)
    assert {p.product_query for p in result.products} == {"Widget 2000", "Gadget 3000"}
    assert {p.price for p in result.prices} == {10.0, 30.0}


def test_merchants_remain_separated(service, db):
    a = merchant(db, "Shop A", "a.example")
    b = merchant(db, "Shop B", "b.example")
    competitor_obs(db, a, position=1)
    competitor_obs(db, b, position=2)

    result = service.snapshot(market="Coffee Shops", location=AUSTIN)
    assert len(result.competitors) == 2
    assert {c.name for c in result.competitors} == {"Shop A", "Shop B"}
    assert {v.merchant for v in result.visibility} == {"Shop A", "Shop B"}


def test_options_lists_only_observed_markets(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, market="Coffee Shops", location=AUSTIN)
    competitor_obs(db, m, market="Automotive Repair", location=HYDERABAD,
                   observed_at=at(1))

    options = service.options()
    assert options.total == 2
    pairs = {(o.market, o.location) for o in options.options}
    assert pairs == {("Coffee Shops", AUSTIN), ("Automotive Repair", HYDERABAD)}


# ============================================================ 10-12: trends
def test_one_measurement_is_insufficient_history(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=3)

    result = service.snapshot(market="Coffee Shops", location=AUSTIN)
    position_series = [t for t in result.trends if t.metric == "position"]
    assert position_series
    assert all(t.status == "insufficient_history" for t in position_series)
    assert all(t.direction is None for t in position_series)


def test_repeated_identical_cached_measurement_is_insufficient_history(service, db):
    """The failure mode this whole stack is built to avoid."""
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    for hours in (0, 1, 2):
        competitor_obs(db, m, position=3, observed_at=at(hours))

    result = service.snapshot(market="Coffee Shops", location=AUSTIN)
    series = next(t for t in result.trends if t.metric == "position")
    assert series.raw_observations == 3
    assert series.distinct_points == 1
    assert series.status == "insufficient_history"
    assert series.direction is None
    assert result.data_quality.trend_series_with_direction == 0
    assert any("single distinct measurement" in n for n in result.data_quality.notes)


def test_two_distinct_measurements_produce_a_direction(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=5, observed_at=at(0))
    competitor_obs(db, m, position=5, observed_at=at(1))    # cache duplicate
    competitor_obs(db, m, position=2, observed_at=at(200))

    result = service.snapshot(market="Coffee Shops", location=AUSTIN)
    series = next(t for t in result.trends if t.metric == "position")
    assert series.distinct_points == 2
    assert series.status == "trend"
    assert series.direction == "down"
    assert result.data_quality.trend_series_with_direction >= 1


# ============================================================ 14: presence
def test_absent_from_latest_is_not_labelled_disappeared(service, db):
    a = merchant(db, "Still Here", "a.example")
    b = merchant(db, "Not In Latest", "b.example")
    competitor_obs(db, a, observed_at=at(0))
    competitor_obs(db, b, observed_at=at(0))
    competitor_obs(db, a, observed_at=at(200))

    result = service.snapshot(market="Coffee Shops", location=AUSTIN)
    by_name = {c.name: c for c in result.competitors}
    absent = by_name["Not In Latest"]
    assert absent.present_in_latest is False
    assert "not proof" in absent.presence_note
    for word in ("disappeared", "closed down", "left the market."):
        assert word not in absent.presence_note.lower().replace(
            "closed or left the market", "")
    # The record survives in full.
    assert absent.first_seen_at is not None
    assert db.query(Merchant).count() == 2


def test_no_response_field_asserts_a_conclusion(service, db):
    """The schema must not offer a place to put an unsupported judgement."""
    from app.schemas.pulse import MarketPulseResponse

    banned = ("growth", "growing", "winner", "winning", "losing", "dominant",
              "demand", "best_competitor", "score", "ranking_score",
              "disappeared", "health_score", "momentum")
    fields = set(MarketPulseResponse.model_fields)
    for name in banned:
        assert name not in fields, name + " invites an unsupported conclusion"


# ============================================================ 15-17: read-only
def test_snapshot_writes_nothing(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1, rating=4.5)
    product_obs(db, m, price=19.99)

    before = (db.query(Merchant).count(),
              db.query(CompetitorObservation).count(),
              db.query(ProductObservation).count())
    rows_before = [(r.id, r.price, r.price_status, r.product_status)
                   for r in db.query(ProductObservation).all()]

    service.options()
    service.snapshot()
    service.snapshot(market="Coffee Shops", location=AUSTIN)

    assert before == (db.query(Merchant).count(),
                      db.query(CompetitorObservation).count(),
                      db.query(ProductObservation).count())
    assert rows_before == [(r.id, r.price, r.price_status, r.product_status)
                           for r in db.query(ProductObservation).all()]


def test_market_pulse_performs_zero_serpapi_calls(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1)
    product_obs(db, m, price=19.99)

    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        service.options()
        service.snapshot(market="Coffee Shops", location=AUSTIN)
        assert MockSearch.call_count == 0


def test_service_performs_no_discovery_of_its_own():
    """Layering: Pulse consumes, it does not discover."""
    import inspect
    from app.services import pulse_service

    source = inspect.getsource(pulse_service)
    assert "locations.json" not in source
    assert "class LocationResolver" not in source
    assert "def match_merchant" not in source
    assert "def match_product" not in source
    assert "CompetitorService" not in source
    assert "ProductService" not in source
    assert "GoogleSearch" not in source
    # Trend semantics are reused, not reimplemented.
    assert "from app.services.trends_service import" in source


def test_no_artificial_budget_field_in_the_pulse_contract():
    from app.schemas.pulse import MarketPulseResponse

    for name in ("daily_limit", "daily_used", "max_credits",
                 "searches_remaining", "budget_exhausted", "credits_remaining",
                 "account_quota_available", "total_searches_left"):
        assert name not in MarketPulseResponse.model_fields, name


# ============================================================ API surface
def test_endpoints_respond_and_do_not_mutate(client, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1, rating=4.5)
    product_obs(db, m, price=19.99)

    before = (db.query(Merchant).count(),
              db.query(CompetitorObservation).count(),
              db.query(ProductObservation).count())

    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        options = client.get("/api/market-pulse/options")
        snapshot = client.get("/api/market-pulse", params={
            "market": "Coffee Shops", "location": AUSTIN})
        assert MockSearch.call_count == 0

    assert options.status_code == 200
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert body["persisted"] is False
    assert body["context"]["market"] == "Coffee Shops"
    assert body["context"]["location"] == AUSTIN
    assert body["has_data"] is True

    assert before == (db.query(Merchant).count(),
                      db.query(CompetitorObservation).count(),
                      db.query(ProductObservation).count())


def test_endpoint_requires_no_serpapi_key(client, db):
    from app.config import settings

    original = settings.SERPAPI_API_KEY
    try:
        settings.SERPAPI_API_KEY = None
        assert client.get("/api/market-pulse").status_code == 200
        assert client.get("/api/market-pulse/options").status_code == 200
    finally:
        settings.SERPAPI_API_KEY = original


def test_snapshot_for_an_unobserved_market_is_empty_not_an_error(client, db):
    merchant(db, "Bean & Brew", "beanandbrew.example")
    response = client.get("/api/market-pulse", params={"market": "Nothing Here"})
    assert response.status_code == 200
    body = response.json()
    assert body["has_data"] is False
    assert body["detail"]
