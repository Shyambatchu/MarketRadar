"""Currency-correct prices, and Price Intelligence results that are kept.

Found in the 2026-10-10 enhancement audit:

* every price was read from ``$NN.NN`` text and labelled USD -- a euro or rupee
  price was never found, and a Canadian "$" was called US dollars;
* the Shopping price was parsed by stripping "$" instead of using the
  provider's own ``extracted_price``;
* Price Intelligence results were never stored, so they fed no Trends, Market
  Pulse or AI Analyst reading.
"""
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.models.merchant import Merchant
from app.models.product_observation import ProductObservation
from app.providers.merchant_website_provider import MerchantWebsitePriceProvider
from app.services.live_price_service import LivePriceService
from app.services.money import find_prices, parse_amount, parse_price
from app.services.trends_service import TrendsService

from tests.stubs import StubResolver

SECAUCUS = (40.798337, -74.064938)


# ------------------------------------------------------------ parsing
@pytest.mark.parametrize("text,country,amount,currency", [
    ("$39.99", "us", 39.99, "USD"),
    ("$39.99", "ca", 39.99, "CAD"),
    ("$1,299.99", "us", 1299.99, "USD"),
    ("12,99 €", None, 12.99, "EUR"),
    ("1.234,56 EUR", None, 1234.56, "EUR"),
    ("₹1,200", "in", 1200.0, "INR"),
    ("Rs. 499", "in", 499.0, "INR"),
    ("£5", "gb", 5.0, "GBP"),
    ("C$45.00", "us", 45.0, "CAD"),
    ("USD 12.50", None, 12.5, "USD"),
])
def test_prices_are_read_with_their_currency(text, country, amount, currency):
    match = parse_price(text, country)
    assert match.amount == amount
    assert match.currency == currency


def test_a_bare_dollar_sign_outside_a_dollar_country_has_no_currency():
    assert parse_price("$39.99", "de").currency is None
    assert parse_price("$39.99", None).currency is None


def test_bare_numbers_in_prose_are_never_prices():
    assert find_prices("Widget 2000 750ml") == []
    assert parse_price("Widget 2000 750ml") is None


def test_a_size_after_a_price_is_not_grouped_into_it():
    assert parse_price("$29 100ml", "us").amount == 29.0


def test_conflicting_currencies_are_ambiguous():
    assert parse_price("$19.99 and €20", "us") is None


@pytest.mark.parametrize("raw,value", [("1,234", 1234.0), ("1.5", 1.5), ("39", 39.0),
                                       ("1.234,56", 1234.56), ("", None)])
def test_amount_conventions(raw, value):
    assert parse_amount(raw) == value


def test_website_extraction_reports_currency_from_the_market():
    provider = MerchantWebsitePriceProvider()
    info = provider.extract_price_info("Widget 2000", "Widget 2000 €24,90 in den Warenkorb",
                                       "Widget 2000", country="de")
    assert info["price"] == 24.9 and info["currency"] == "EUR"
    info = provider.extract_price_info("Widget 2000", "Widget 2000 $39.99 Add to Cart",
                                       "Widget 2000", country="au")
    assert info["currency"] == "AUD"


def test_a_euro_range_is_still_a_range():
    info = MerchantWebsitePriceProvider().extract_price_info(
        "Widget", "Widget 12 € - 20 €", "Widget", country="de")
    assert info["is_range"] and info["price"] is None


# ------------------------------------------------------------ pipeline
@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for table in ("search_cache", "product_observations", "competitor_observations",
                  "merchants", "api_usage"):
        session.execute(text("DELETE FROM " + table))
    session.commit()
    yield session
    session.close()


MAPS = {
    "place_results": {"title": "Secaucus",
                      "gps_coordinates": {"latitude": SECAUCUS[0], "longitude": SECAUCUS[1]}},
    "local_results": [{
        "title": "Example Wine", "gps_coordinates": {"latitude": 40.80, "longitude": -74.06},
        "website": "https://example.com", "address": "1 Main St", "place_id": "p1",
    }],
}


def run(db, website_rows, shopping_rows=(), persist=True):
    def search(params):
        engine_name = params.get("engine")
        payload = {
            "google_maps": MAPS,
            "google": {"organic_results": list(website_rows)},
            "google_shopping": {"shopping_results": list(shopping_rows)},
        }[engine_name]

        class S:
            timeout = None

            @staticmethod
            def get_dict():
                return payload
        return S()

    service = LivePriceService("test-key", resolver=StubResolver())
    with patch("app.services.api_budget.GoogleSearch", side_effect=search):
        return service.fetch_real_data("Widget 2000", "Secaucus, NJ", 25, db=db,
                                       persist=persist)


PRODUCT_PAGE = {"link": "https://example.com/products/widget-2000",
                "title": "Widget 2000", "snippet": "Widget 2000 $39.99 Add to Cart"}


def test_a_verified_local_price_carries_the_markets_currency(db):
    result = run(db, [PRODUCT_PAGE])
    assert result.verified_price_observations[0].currency == "USD"
    assert result.currency == "USD"


def test_a_run_is_persisted_as_product_observations(db):
    result = run(db, [PRODUCT_PAGE])
    assert result.persisted_observations == 1
    row = db.query(ProductObservation).one()
    assert row.discovery_method == "price_intelligence"
    assert row.price == 39.99 and row.currency == "USD"
    assert row.price_status == "verified"
    assert row.location_resolved == "Secaucus,New Jersey,United States"
    merchant = db.query(Merchant).one()
    assert merchant.normalized_domain == "example.com" and merchant.place_id == "p1"


def test_repeated_runs_append_history_and_reuse_the_merchant(db):
    run(db, [PRODUCT_PAGE])
    db.execute(text("DELETE FROM search_cache"))
    db.commit()
    run(db, [dict(PRODUCT_PAGE, snippet="Widget 2000 $35.99 Add to Cart")])
    assert db.query(Merchant).count() == 1
    assert db.query(ProductObservation).count() == 2
    series = TrendsService(db).price_trends(product_query="Widget 2000").series
    assert len(series) == 1 and series[0].direction == "down"


def test_merchants_without_evidence_are_not_recorded(db):
    result = run(db, [])
    assert result.persisted_observations == 0
    assert db.query(ProductObservation).count() == 0


def test_persistence_can_be_skipped(db):
    run(db, [PRODUCT_PAGE], persist=False)
    assert db.query(ProductObservation).count() == 0


def test_shopping_uses_the_providers_extracted_price(db):
    result = run(db, [], shopping_rows=[{
        "title": "Widget 2000", "source": "example.com",
        "link": "https://example.com/products/widget-2000",
        "price": "$1,049.00", "extracted_price": 1049.0}])
    obs = result.verified_price_observations
    assert obs and obs[0].price == 1049.0 and obs[0].currency == "USD"


def test_price_series_never_mix_currencies(db):
    from datetime import datetime, timedelta, timezone
    m = Merchant(name="Alpha", normalized_name="alpha", status="verified",
                 entity_type="business", normalized_domain="alpha.example")
    db.add(m)
    db.commit()
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    for day, price, currency in ((0, 10.0, "USD"), (1, 9.0, "EUR"), (2, 11.0, "USD")):
        db.add(ProductObservation(
            merchant_id=m.id, product_query="Widget", normalized_query="widget",
            market="W", location_resolved="X", product_status="found",
            price_status="verified", price=price, currency=currency,
            observed_at=base + timedelta(days=day)))
    db.commit()
    series = TrendsService(db).price_trends(product_query="Widget").series
    by_currency = {s.currency: s for s in series}
    assert set(by_currency) == {"USD", "EUR"}
    assert by_currency["USD"].direction == "up"
    assert by_currency["EUR"].status == "insufficient_history"
