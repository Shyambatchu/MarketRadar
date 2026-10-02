"""AI Analyst: evidence-grounded analysis over a Market Pulse snapshot.

The property that matters most is that the analyst cannot invent facts, and
these tests hold it to that structurally rather than by inspection:

* every factual statement is produced by Python from the snapshot, so a
  provider that returns nothing still yields the full factual analysis;
* the only model-produced text is the summary, and a summary asserting a
  banned conclusion or citing an unknown figure is withheld, not shown.

No test reaches a real provider. The provider is injected.
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
from app.routes.analyst import get_analyst_service
from app.schemas.analyst import AnalystResponse
from app.services.ai_provider import (
    AIProviderError, NotConfiguredProvider, get_ai_provider,
)
from app.services.analyst_service import AnalystService, validate_summary

BASE = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
AUSTIN = "Austin,Texas,United States"
HYDERABAD = "Hyderabad,Telangana,India"


def at(hours: float) -> datetime:
    return BASE + timedelta(hours=hours)


# ---------------------------------------------------------------- providers
class StubProvider:
    """A provider that returns whatever the test tells it to."""

    name = "stub"

    def __init__(self, response="Three verified businesses were observed.",
                 error=None):
        self.response = response
        self.error = error
        self.calls = []

    def is_configured(self) -> bool:
        return True

    def generate(self, system_prompt, user_prompt, max_tokens=600):
        self.calls.append((system_prompt, user_prompt))
        if self.error:
            raise self.error
        return self.response


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
    """Default: no provider configured."""
    return AnalystService(db=db, provider=NotConfiguredProvider())


def merchant(db, name, domain=None, status="verified", address="1 Main St"):
    row = Merchant(name=name, normalized_name=name.lower().replace(" ", ""),
                   normalized_domain=domain, status=status,
                   entity_type="business", address=address)
    db.add(row)
    db.flush()
    db.commit()
    return row


def competitor_obs(db, m, market="Coffee Shops", location=AUSTIN, position=None,
                   rating=None, reviews=None, observed_at=None):
    db.add(CompetitorObservation(
        merchant_id=m.id, market=market, query=market.lower(),
        location_resolved=location, source_type="local",
        discovery_method="google_maps_local", entity_type="business",
        status="verified", position=position, rating=rating, reviews=reviews,
        observed_at=observed_at or at(0)))
    db.commit()


def product_obs(db, m, query="Widget 2000", market="Coffee Shops", location=AUSTIN,
                price=None, price_status="verified", product_status="found",
                observed_at=None, reason=None):
    db.add(ProductObservation(
        merchant_id=m.id, product_query=query, normalized_query=query.lower(),
        market=market, location_resolved=location, product_name=query,
        product_status=product_status, price_status=price_status,
        verification_reason=reason, price=price,
        currency="USD" if price else None,
        source_type="merchant_website_indexed", discovery_method="indexed_search",
        source_url="https://example.test/product/x", source_domain="example.test",
        page_type="product", evidence_scope="catalog", inventory_confirmed=False,
        observed_at=observed_at or at(0)))
    db.commit()


def statements(result, section=None):
    items = getattr(result, section) if section else result.observations
    return " ".join(o.statement for o in items)


# ============================================================ 1: no data
def test_analysis_with_no_market_pulse_data(service, db):
    result = service.analyse()
    assert result.has_data is False
    assert result.summary is None
    assert result.detail
    assert result.persisted is False
    # The factual sections still explain the absence rather than being empty.
    assert any(o.kind == "insufficient_evidence" for o in result.observations)


# ============================================================ 2: valid data
def test_analysis_with_valid_data(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1, rating=4.5, reviews=120)
    product_obs(db, m, price=19.99)

    result = service.analyse(market="Coffee Shops", location=AUSTIN)
    assert result.has_data is True
    assert result.context.market == "Coffee Shops"
    assert result.market_overview and result.competitor_observations
    assert result.product_observations and result.price_analysis
    assert result.visibility_observations and result.data_quality
    # Every observation carries an evidence reference.
    assert all(o.evidence.section for o in result.observations)
    assert len(result.evidence) == len(result.observations)


def test_every_statement_is_computed_not_generated(service, db):
    """With no provider at all, the full factual analysis is still produced."""
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1)
    product_obs(db, m, price=19.99)

    result = service.analyse(market="Coffee Shops", location=AUSTIN)
    assert result.provider_configured is False
    assert result.analysis_mode == "deterministic"
    assert result.summary is None
    assert len(result.observations) > 5, "facts do not depend on a provider"


# ============================================================ 3: insufficient
def test_insufficient_history_is_stated_not_smoothed_over(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    for hours in (0, 1, 2):
        competitor_obs(db, m, position=3, observed_at=at(hours))

    result = service.analyse(market="Coffee Shops", location=AUSTIN)
    trend_text = statements(result, "trend_analysis")
    assert "insufficient" in trend_text.lower()
    assert "single distinct measurement" in trend_text
    assert any(o.kind == "insufficient_evidence" for o in result.trend_analysis)


def test_two_distinct_measurements_are_described_factually(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=5, observed_at=at(0))
    competitor_obs(db, m, position=5, observed_at=at(1))
    competitor_obs(db, m, position=2, observed_at=at(200))

    text_out = statements(service.analyse(market="Coffee Shops", location=AUSTIN),
                          "trend_analysis")
    assert "2 distinct measurements" in text_out
    assert "decreased" in text_out
    for banned in ("improving", "winning", "better than"):
        assert banned not in text_out.lower()


def test_trend_facts_are_not_recalculated():
    """Trend verdicts must come from TrendsService, not be re-derived."""
    import inspect
    from app.services import analyst_service

    source = inspect.getsource(analyst_service.AnalystService._trends)
    assert "collapse(" not in source
    assert "distinct_points" in source, "it reads the series' own verdict"


# ============================================================ 4,5,6: prices
def test_verified_price_is_reported(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    product_obs(db, m, price=19.99, price_status="verified")

    text_out = statements(service.analyse(market="Coffee Shops", location=AUSTIN),
                          "price_analysis")
    assert "1 verified price observation is recorded (1 distinct measurement)" in text_out
    assert "19.99" in text_out


def test_unknown_price_is_not_reported_as_absent(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    product_obs(db, m, price=None, price_status="unknown", product_status="unknown")

    result = service.analyse(market="Coffee Shops", location=AUSTIN)
    product_text = statements(result, "product_observations")
    assert "not a finding that the product is unavailable" in product_text
    assert "No verified price measurements" in statements(result, "price_analysis")


def test_unverified_price_is_excluded_and_said_so(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    product_obs(db, m, price=99.0, price_status="unavailable",
                reason="price_not_product_specific")

    text_out = statements(service.analyse(market="Coffee Shops", location=AUSTIN),
                          "price_analysis")
    assert "could not be verified" in text_out
    assert "excluded from price analysis" in text_out
    assert "99.0" not in text_out, "an unverified figure must never be quoted"


def test_a_single_price_is_called_insufficient_not_averaged(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    for hours in (0, 1, 2):
        product_obs(db, m, price=19.99, observed_at=at(hours))

    text_out = statements(service.analyse(market="Coffee Shops", location=AUSTIN),
                          "price_analysis")
    assert "insufficient to summarise" in text_out
    assert "averaging" not in text_out


def test_sufficient_distinct_prices_are_summarised_with_a_caveat(service, db):
    a = merchant(db, "Shop A", "a.example")
    b = merchant(db, "Shop B", "b.example")
    product_obs(db, a, price=10.0)
    product_obs(db, b, price=20.0)

    text_out = statements(service.analyse(market="Coffee Shops", location=AUSTIN),
                          "price_analysis")
    assert "range from 10.00 to 20.00" in text_out
    assert "not a market rate" in text_out


# ============================================================ 7,8: quality
def test_geographic_uncertainty_is_reported(service, db):
    m = merchant(db, "Remote Shop", "remote.example", address=None)
    competitor_obs(db, m, position=3)

    text_out = statements(service.analyse(market="Coffee Shops", location=AUSTIN),
                          "data_quality")
    assert "geographic relevance" in text_out
    assert "could not be verified" in text_out
    assert "Nothing is inferred from the domain name" in text_out


def test_missing_domain_is_reported(service, db):
    m = merchant(db, "No Site Shop", domain=None)
    competitor_obs(db, m, position=2)

    text_out = statements(service.analyse(market="Coffee Shops", location=AUSTIN),
                          "data_quality")
    assert "no website domain reported" in text_out
    assert "No Site Shop" in text_out


# ============================================================ 9,10,11
def test_multiple_merchants_are_all_reported(service, db):
    for name in ("Shop A", "Shop B", "Shop C"):
        m = merchant(db, name, name.lower().replace(" ", "") + ".example")
        competitor_obs(db, m, position=1)

    text_out = statements(service.analyse(market="Coffee Shops", location=AUSTIN),
                          "competitor_observations")
    assert "3 verified businesses" in text_out
    for name in ("Shop A", "Shop B", "Shop C"):
        assert name in text_out


def test_multiple_products_are_all_reported(service, db):
    m = merchant(db, "Shop A", "a.example")
    product_obs(db, m, query="Widget 2000", price=10.0)
    product_obs(db, m, query="Gadget 3000", price=30.0, observed_at=at(1))

    text_out = statements(service.analyse(market="Coffee Shops", location=AUSTIN),
                          "price_analysis")
    assert "Widget 2000" in text_out and "Gadget 3000" in text_out


def test_contexts_remain_separated(service, db):
    a = merchant(db, "Austin Shop", "austin.example")
    h = merchant(db, "Hyderabad Shop", "hyd.example")
    competitor_obs(db, a, market="Coffee Shops", location=AUSTIN)
    competitor_obs(db, h, market="Automotive Repair", location=HYDERABAD)

    austin = statements(service.analyse(market="Coffee Shops", location=AUSTIN))
    assert "Austin Shop" in austin and "Hyderabad Shop" not in austin

    hyd = statements(service.analyse(market="Automotive Repair", location=HYDERABAD))
    assert "Hyderabad Shop" in hyd and "Austin Shop" not in hyd


# ============================================================ 12: no provider
def test_provider_not_configured_is_a_clear_state(service, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1)

    result = service.analyse(market="Coffee Shops", location=AUSTIN)
    assert result.provider_configured is False
    assert result.provider_name == "not_configured"
    assert result.summary is None
    assert result.analysis_mode == "deterministic"
    assert "No AI provider is configured" in result.detail


def test_default_provider_is_not_configured_without_settings():
    provider = get_ai_provider(provider_name="", api_key=None)
    assert provider.is_configured() is False
    with pytest.raises(Exception):
        provider.generate("s", "u")


def test_an_unregistered_provider_name_degrades_safely():
    provider = get_ai_provider(provider_name="nonexistent-vendor", api_key="k")
    assert provider.is_configured() is False


# ============================================================ 13,14: mocked
def test_mocked_provider_success_produces_an_assisted_summary(db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1)

    provider = StubProvider("1 verified business was observed in the snapshot.")
    result = AnalystService(db=db, provider=provider).analyse(
        market="Coffee Shops", location=AUSTIN)

    assert result.provider_configured is True
    assert result.analysis_mode == "assisted"
    assert result.summary == "1 verified business was observed in the snapshot."
    assert result.summary_rejected is False
    # The provider is given the computed facts, never raw records.
    system, user = provider.calls[0]
    assert "Do not add facts" in system
    assert "Statements computed from recorded observations" in user


def test_mocked_provider_failure_leaves_the_facts_intact(db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1)

    provider = StubProvider(error=AIProviderError("upstream timeout"))
    result = AnalystService(db=db, provider=provider).analyse(
        market="Coffee Shops", location=AUSTIN)

    assert result.summary is None
    assert result.provider_error and "upstream timeout" in result.provider_error
    assert result.analysis_mode == "deterministic"
    assert len(result.observations) > 3, "a provider fault must not lose the facts"


def test_an_unexpected_provider_exception_is_contained(db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1)

    provider = StubProvider(error=RuntimeError("boom"))
    result = AnalystService(db=db, provider=provider).analyse(
        market="Coffee Shops", location=AUSTIN)

    assert result.summary is None
    assert "RuntimeError" in result.provider_error
    assert result.observations


def test_an_empty_provider_response_is_not_shown(db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1)

    result = AnalystService(db=db, provider=StubProvider("   ")).analyse(
        market="Coffee Shops", location=AUSTIN)
    assert result.summary is None
    assert "empty summary" in result.provider_error


def test_include_summary_false_skips_the_provider(db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1)

    provider = StubProvider()
    result = AnalystService(db=db, provider=provider).analyse(
        market="Coffee Shops", location=AUSTIN, include_summary=False)
    assert provider.calls == []
    assert result.summary is None
    assert result.observations


# ============================================================ 15: no invention
@pytest.mark.parametrize("summary, fragment", [
    ("Bean & Brew is the market leader here.", "market leader"),
    ("This competitor is clearly dominant.", "dominant"),
    ("The market is growing steadily.", "growing"),
    ("Prices will increase next quarter.", "will increase"),
    ("Demand is high in this area.", "demand is high"),
    ("Total Wine went out of business.", "went out of business"),
    ("We recommend targeting this segment.", "we recommend"),
    ("Shop A is outperforming Shop B.", "outperform"),
    ("Customers prefer the cheaper option.", "customers prefer"),
    ("Its market share is increasing.", "market share"),
])
def test_a_summary_asserting_a_conclusion_is_rejected(summary, fragment):
    ok, reason = validate_summary(summary, ["1 verified business was observed."])
    assert ok is False
    assert fragment in reason


def test_a_summary_citing_an_unknown_figure_is_rejected():
    ok, reason = validate_summary(
        "There were 47 verified businesses observed.",
        ["3 verified businesses were observed."])
    assert ok is False
    assert "47" in reason


def test_a_faithful_summary_is_accepted():
    ok, reason = validate_summary(
        "3 verified businesses were observed and 1 verified price of 19.99 is available.",
        ["3 verified businesses were observed.",
         "1 verified price measurement is available: Shop A at 19.99 USD."])
    assert ok is True and reason is None


def test_a_rejected_summary_is_withheld_with_its_reason(db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1)

    provider = StubProvider("Bean & Brew is the dominant market leader.")
    result = AnalystService(db=db, provider=provider).analyse(
        market="Coffee Shops", location=AUSTIN)

    assert result.summary is None, "an unfounded summary must never be shown"
    assert result.summary_rejected is True
    assert "conclusion the evidence does not support" in result.summary_rejection_reason
    assert result.analysis_mode == "deterministic"
    # The facts survive the rejection.
    assert result.observations


def test_computed_statements_contain_no_banned_conclusion(db):
    """The deterministic layer must itself never conclude."""
    a = merchant(db, "Shop A", "a.example")
    b = merchant(db, "Shop B", domain=None, address=None)
    competitor_obs(db, a, position=1, rating=4.8, reviews=500, observed_at=at(0))
    competitor_obs(db, b, position=9, rating=3.1, reviews=4, observed_at=at(0))
    competitor_obs(db, a, position=1, observed_at=at(200))
    product_obs(db, a, price=19.99)
    product_obs(db, b, price=None, price_status="unknown", product_status="unknown")

    result = AnalystService(db=db, provider=NotConfiguredProvider()).analyse(
        market="Coffee Shops", location=AUSTIN)
    ok, reason = validate_summary(statements(result),
                                  [o.statement for o in result.observations])
    assert ok is True, reason


def test_no_response_field_invites_a_conclusion():
    banned = ("winner", "leader", "score", "ranking", "growth", "prediction",
              "forecast", "recommendation", "confidence")
    for name in banned:
        assert name not in AnalystResponse.model_fields, name


# ============================================================ 16,17: safety
def test_analyst_performs_zero_serpapi_calls(db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1)
    product_obs(db, m, price=19.99)

    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        AnalystService(db=db, provider=StubProvider()).analyse(
            market="Coffee Shops", location=AUSTIN)
        assert MockSearch.call_count == 0


def test_analyst_performs_zero_db_mutations(db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1)
    product_obs(db, m, price=19.99)

    before = (db.query(Merchant).count(),
              db.query(CompetitorObservation).count(),
              db.query(ProductObservation).count())
    rows_before = [(r.id, r.price, r.price_status) for r in db.query(ProductObservation).all()]

    service = AnalystService(db=db, provider=StubProvider())
    service.analyse()
    service.analyse(market="Coffee Shops", location=AUSTIN)

    assert before == (db.query(Merchant).count(),
                      db.query(CompetitorObservation).count(),
                      db.query(ProductObservation).count())
    assert rows_before == [(r.id, r.price, r.price_status)
                           for r in db.query(ProductObservation).all()]


def test_analyst_performs_no_discovery_of_its_own():
    import inspect
    from app.services import analyst_service

    source = inspect.getsource(analyst_service)
    assert "locations.json" not in source
    assert "CompetitorService" not in source
    assert "ProductService" not in source
    assert "GoogleSearch" not in source
    assert "ApiBudgetManager" not in source
    assert "from app.services.pulse_service import" in source


def test_no_artificial_budget_field_in_the_analyst_contract():
    for name in ("daily_limit", "max_credits", "searches_remaining",
                 "budget_exhausted", "credits_remaining", "total_searches_left"):
        assert name not in AnalystResponse.model_fields, name


# ============================================================ API surface
@pytest.fixture
def client(db):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_analyst_service] = lambda: AnalystService(
        db=db, provider=NotConfiguredProvider())
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_endpoint_returns_the_documented_schema(client, db):
    m = merchant(db, "Bean & Brew", "beanandbrew.example")
    competitor_obs(db, m, position=1, rating=4.5)
    product_obs(db, m, price=19.99)

    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        response = client.get("/api/analyst/analysis", params={
            "market": "Coffee Shops", "location": AUSTIN})
        assert MockSearch.call_count == 0

    assert response.status_code == 200
    body = AnalystResponse(**response.json())
    assert body.has_data is True
    assert body.persisted is False
    assert body.provider_configured is False
    assert body.observations and body.evidence


def test_endpoint_with_no_data_is_200(client, db):
    response = client.get("/api/analyst/analysis", params={"market": "Nothing Here"})
    assert response.status_code == 200
    assert response.json()["has_data"] is False


def test_endpoint_requires_no_serpapi_key(client, db):
    from app.config import settings

    original = settings.SERPAPI_API_KEY
    try:
        settings.SERPAPI_API_KEY = None
        assert client.get("/api/analyst/analysis").status_code == 200
    finally:
        settings.SERPAPI_API_KEY = original
