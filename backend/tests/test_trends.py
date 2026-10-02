"""Trends: derived from observation history, never authoritative.

The defining risk in this module is manufactured history. Re-running a search
inside the 7-day response cache returns byte-identical data and stores another
observation row, so three rows can describe one measurement. Reporting that as
a stable trend would be false confidence of exactly the kind the rest of the
system refuses to produce.

Observed in the real database before this module existed: every merchant with
repeat observations had ``COUNT(DISTINCT position) = 1`` and
``COUNT(DISTINCT rating) = 1``.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.models.competitor import CompetitorObservation
from app.models.merchant import Merchant
from app.models.product_observation import ProductObservation
from app.services.trends_service import (
    TrendsService, build_series, collapse,
)

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
    return TrendsService(db=db)


def merchant(db, name, domain=None, status="verified"):
    row = Merchant(name=name, normalized_name=name.lower().replace(" ", ""),
                   normalized_domain=domain, status=status,
                   entity_type="business")
    db.add(row)
    db.flush()
    return row


def competitor_obs(db, merchant_row, market="Coffee", location="Austin,Texas,United States",
                   position=None, rating=None, reviews=None, observed_at=None):
    db.add(CompetitorObservation(
        merchant_id=merchant_row.id, market=market, query=market.lower(),
        location_resolved=location, source_type="local",
        discovery_method="google_maps_local", entity_type="business",
        status="verified", position=position, rating=rating, reviews=reviews,
        observed_at=observed_at or at(0)))
    db.commit()


def product_obs(db, merchant_row, query="Widget 2000", price=None,
                price_status="verified", product_status="found",
                market="Hardware", observed_at=None, size=None):
    db.add(ProductObservation(
        merchant_id=merchant_row.id, product_query=query,
        normalized_query=query.lower(), market=market,
        location_resolved="Austin,Texas,United States",
        product_name=query, observed_size=size,
        product_status=product_status, price_status=price_status,
        price=price, currency="USD" if price else None,
        source_type="merchant_website_indexed", discovery_method="indexed_search",
        evidence_scope="catalog", inventory_confirmed=False,
        observed_at=observed_at or at(0)))
    db.commit()


# ============================================================ collapse
def test_identical_consecutive_readings_collapse_to_one_point():
    """The core defence: one measurement read three times is one point."""
    points = collapse([(at(0), 19.99, None), (at(1), 19.99, None),
                       (at(2), 19.99, None)])
    assert len(points) == 1
    assert points[0].observation_count == 3
    assert points[0].value == 19.99


def test_a_changed_reading_starts_a_new_point():
    points = collapse([(at(0), 19.99, None), (at(1), 19.99, None),
                       (at(2), 17.49, None)])
    assert [p.value for p in points] == [19.99, 17.49]
    assert [p.observation_count for p in points] == [2, 1]


def test_a_value_that_returns_is_a_separate_point():
    """Up then back down is two movements, not a cancellation."""
    points = collapse([(at(0), 10.0, None), (at(1), 12.0, None),
                       (at(2), 10.0, None)])
    assert [p.value for p in points] == [10.0, 12.0, 10.0]


def test_collapse_orders_oldest_first_regardless_of_input_order():
    points = collapse([(at(2), 3.0, None), (at(0), 1.0, None), (at(1), 2.0, None)])
    assert [p.value for p in points] == [1.0, 2.0, 3.0]


def test_labels_participate_in_identity():
    """Same price, different observed size, is a different reading."""
    points = collapse([(at(0), 19.99, "750ml"), (at(1), 19.99, "1l")])
    assert len(points) == 2


# ============================================================ series status
def test_one_measurement_repeatedly_observed_is_never_a_trend():
    """The exact shape of the real data: three rows, one reading."""
    series = build_series("Widget", "price", "Merchant",
                          [(at(0), 19.99, None), (at(1), 19.99, None),
                           (at(2), 19.99, None)])
    assert series.status == "insufficient_history"
    assert series.direction is None, "no direction may be claimed"
    assert series.change_absolute is None
    assert series.raw_observations == 3
    assert series.distinct_points == 1
    assert "not a trend" in series.detail


def test_two_distinct_measurements_that_agree_are_genuinely_flat():
    """Flat requires having watched it hold, not having read it twice."""
    series = build_series("Widget", "price", "Merchant",
                          [(at(0), 19.99, None), (at(1), 21.00, None),
                           (at(2), 19.99, None)])
    assert series.status == "trend"
    assert series.distinct_points == 3
    assert series.direction == "flat"
    assert series.change_absolute == 0


def test_a_rise_is_reported_with_its_magnitude():
    series = build_series("Widget", "price", "Merchant",
                          [(at(0), 20.0, None), (at(24), 25.0, None)])
    assert series.status == "trend"
    assert series.direction == "up"
    assert series.change_absolute == 5.0
    assert series.change_percent == 25.0
    assert series.observation_span_hours == 24.0


def test_a_fall_is_reported_with_its_magnitude():
    series = build_series("Widget", "price", "Merchant",
                          [(at(0), 20.0, None), (at(12), 15.0, None)])
    assert series.direction == "down"
    assert series.change_absolute == -5.0
    assert series.change_percent == -25.0


def test_no_observations_is_no_data_not_a_flat_trend():
    series = build_series("Widget", "price", "Merchant", [])
    assert series.status == "no_data"
    assert series.direction is None


# ============================================================ read-only
def test_trends_writes_nothing(service, db):
    """Trends derives from history; it must never become the source of truth."""
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1, rating=4.5)
    product_obs(db, m, price=19.99)

    before = {
        "merchants": db.query(Merchant).count(),
        "competitor": db.query(CompetitorObservation).count(),
        "product": db.query(ProductObservation).count(),
    }
    rows_before = [(r.id, r.price, r.price_status)
                   for r in db.query(ProductObservation).all()]

    service.summary()
    service.price_trends()
    service.availability_trends()
    service.visibility_trends()
    service.merchant_presence()

    assert before == {
        "merchants": db.query(Merchant).count(),
        "competitor": db.query(CompetitorObservation).count(),
        "product": db.query(ProductObservation).count(),
    }
    assert rows_before == [(r.id, r.price, r.price_status)
                           for r in db.query(ProductObservation).all()], \
        "existing observations must not be rewritten or normalised"


def test_no_trend_table_is_written(service, db):
    """The module persists nothing, so every response says so."""
    assert service.summary().persisted is False
    assert service.price_trends().persisted is False
    assert service.merchant_presence().persisted is False


def test_service_makes_no_provider_request(service, db):
    from unittest.mock import patch

    m = merchant(db, "Bean & Brew")
    competitor_obs(db, m, position=1)
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        service.summary()
        service.price_trends()
        service.visibility_trends()
        assert MockSearch.call_count == 0, "trends must spend no credit"


# ============================================================ comparability
def test_series_are_not_merged_across_merchants(service, db):
    a = merchant(db, "Shop A", "a.example")
    b = merchant(db, "Shop B", "b.example")
    product_obs(db, a, price=10.0, observed_at=at(0))
    product_obs(db, b, price=99.0, observed_at=at(1))

    result = service.price_trends()
    assert result.total == 2, "one series per merchant"
    assert all(s.distinct_points == 1 for s in result.series)
    assert all(s.status == "insufficient_history" for s in result.series)


def test_series_are_not_merged_across_markets_or_locations(service, db):
    m = merchant(db, "Bean & Brew")
    competitor_obs(db, m, market="Coffee", location="Austin,Texas,United States",
                   position=1, observed_at=at(0))
    competitor_obs(db, m, market="Coffee", location="Hyderabad,Telangana,India",
                   position=8, observed_at=at(1))

    result = service.visibility_trends(metric="position")
    assert result.total == 2, "a different location is a different context"
    assert result.analyzable == 0, "neither context has two measurements"


def test_a_real_movement_within_one_context_is_detected(service, db):
    m = merchant(db, "Bean & Brew")
    competitor_obs(db, m, position=5, observed_at=at(0))
    competitor_obs(db, m, position=5, observed_at=at(1))   # cache duplicate
    competitor_obs(db, m, position=2, observed_at=at(200))  # after cache expiry

    result = service.visibility_trends(metric="position")
    assert result.total == 1
    series = result.series[0]
    assert series.raw_observations == 3
    assert series.distinct_points == 2
    assert series.status == "trend"
    assert series.direction == "down"       # position improved
    assert series.change_absolute == -3.0


# ============================================================ price rules
def test_only_verified_prices_form_a_price_trend(service, db):
    """An unverified price was never established as this product's price."""
    m = merchant(db, "Shop A")
    product_obs(db, m, price=10.0, price_status="verified", observed_at=at(0))
    product_obs(db, m, price=99.0, price_status="unavailable", observed_at=at(1))
    product_obs(db, m, price=None, price_status="unknown", observed_at=at(2))

    result = service.price_trends()
    assert result.total == 1
    assert result.series[0].raw_observations == 1
    assert result.series[0].status == "insufficient_history"


def test_price_trend_reports_a_genuine_change(service, db):
    m = merchant(db, "Shop A")
    product_obs(db, m, price=20.0, observed_at=at(0))
    product_obs(db, m, price=20.0, observed_at=at(1))
    product_obs(db, m, price=18.0, observed_at=at(200))

    result = service.price_trends()
    series = result.series[0]
    assert series.status == "trend"
    assert series.direction == "down"
    assert series.change_absolute == -2.0
    assert series.change_percent == -10.0


def test_no_verified_prices_is_an_honest_empty_response(service, db):
    m = merchant(db, "Shop A")
    product_obs(db, m, price=None, price_status="unknown")
    result = service.price_trends()
    assert result.total == 0
    assert "No verified price observations" in result.detail


# ============================================================ availability
def test_availability_transition_is_detected(service, db):
    m = merchant(db, "Shop A")
    product_obs(db, m, product_status="unknown", price_status="unknown",
                observed_at=at(0))
    product_obs(db, m, product_status="found", observed_at=at(200))

    result = service.availability_trends()
    series = result.series[0]
    assert series.status == "trend"
    assert [p.label for p in series.points] == ["unknown", "found"]
    assert series.direction == "up"


def test_repeated_unknown_is_not_a_decline(service, db):
    m = merchant(db, "Shop A")
    for hours in (0, 1, 2):
        product_obs(db, m, product_status="unknown", price_status="unknown",
                    observed_at=at(hours))

    series = service.availability_trends().series[0]
    assert series.status == "insufficient_history"
    assert series.direction is None


# ============================================================ summary
def test_summary_reports_insufficient_history_honestly(service, db):
    m = merchant(db, "Bean & Brew")
    competitor_obs(db, m, position=1, observed_at=at(0))

    summary = service.summary()
    assert summary.competitor_observations == 1
    assert summary.analyzable_contexts == 0
    assert summary.insufficient_history is True
    # The wording differs by branch; what matters is that it explains why
    # rather than reporting an absence of movement.
    assert "measured twice" in summary.detail
    assert "cache" in summary.detail


def test_summary_on_an_empty_database_says_so(service, db):
    summary = service.summary()
    assert summary.competitor_observations == 0
    assert summary.contexts == []
    assert summary.insufficient_history is True
    assert "No observations" in summary.detail


def test_summary_marks_a_context_analyzable_once_searched_twice(service, db):
    m = merchant(db, "Bean & Brew")
    competitor_obs(db, m, position=1, observed_at=at(0))
    competitor_obs(db, m, position=2, observed_at=at(200))

    summary = service.summary()
    assert summary.analyzable_contexts == 1
    assert summary.insufficient_history is False
    assert summary.contexts[0].distinct_searches == 2


# ============================================================ presence
def test_merchant_presence_reports_first_and_last_seen(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1, observed_at=at(0))
    competitor_obs(db, m, position=1, observed_at=at(200))

    result = service.merchant_presence()
    assert result.total == 1
    presence = result.merchants[0]
    assert presence.merchant == "Bean & Brew"
    assert presence.observation_count == 2
    assert presence.distinct_searches == 2
    assert presence.present_in_latest is True


def test_a_merchant_absent_from_the_latest_search_is_flagged_not_deleted(service, db):
    """Absence from one search is not proof a business has gone."""
    a = merchant(db, "Still Here")
    b = merchant(db, "Not In Latest")
    competitor_obs(db, a, observed_at=at(0))
    competitor_obs(db, b, observed_at=at(0))
    competitor_obs(db, a, observed_at=at(200))

    result = service.merchant_presence()
    by_name = {m.merchant: m for m in result.merchants}
    assert by_name["Still Here"].present_in_latest is True
    assert by_name["Not In Latest"].present_in_latest is False
    # The record survives; nothing is removed from history.
    assert db.query(Merchant).count() == 2


def test_visibility_rejects_an_unsupported_metric(service, db):
    with pytest.raises(ValueError):
        service.visibility_trends(metric="popularity")


# ============================================================ generic design
def test_module_names_no_industry_product_or_place():
    import ast
    import inspect
    from app.services import trends_service

    tree = ast.parse(inspect.getsource(trends_service))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    literals = " ".join(n.value.lower() for n in ast.walk(tree)
                        if isinstance(n, ast.Constant)
                        and isinstance(n.value, str) and id(n) not in docstrings)

    for forbidden in ("wine", "liquor", "coffee", "new jersey", "holmdel",
                      "austin", "total wine"):
        assert forbidden not in literals, forbidden + " is hardcoded"


def test_summary_does_not_promise_trends_the_signals_cannot_show(service, db):
    """A context searched twice is a precondition, not a trend.

    Observed live: two contexts had 2-3 distinct searches, so the summary
    reported insufficient_history=False, while every one of the 15 series was
    insufficient_history because the repeat searches were cache hits returning
    identical readings.
    """
    m = merchant(db, "Bean & Brew")
    # Two searches of one context, but the same reading both times.
    competitor_obs(db, m, position=3, observed_at=at(0))
    competitor_obs(db, m, position=3, observed_at=at(200))

    summary = service.summary()
    assert summary.analyzable_contexts == 1, "the context was searched twice"
    assert summary.insufficient_history is True, \
        "but nothing was measured twice, so no trend may be promised"
    assert "measured twice" in summary.detail
    assert service.visibility_trends(metric="position").analyzable == 0


def test_summary_reports_measurable_once_a_reading_actually_changes(service, db):
    m = merchant(db, "Bean & Brew")
    competitor_obs(db, m, position=5, observed_at=at(0))
    competitor_obs(db, m, position=5, observed_at=at(1))
    competitor_obs(db, m, position=2, observed_at=at(200))

    summary = service.summary()
    assert summary.insufficient_history is False
    assert service.visibility_trends(metric="position").analyzable == 1
