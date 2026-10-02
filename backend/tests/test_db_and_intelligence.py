import pytest
from datetime import datetime, timezone, timedelta
from app.services.intelligence_service import IntelligenceService
from app.schemas.price import PriceObservation
from app.models.market_observation import MarketObservation
from app.database.connection import engine, SessionLocal
from app.database.base import Base

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()

def test_intelligence_service_compare_decrease():
    service = IntelligenceService()
    res = service.compare_prices(2599, 2499)
    assert res["change_type"] == "price_decrease"
    assert res["absolute_change"] == -100
    assert res["percentage_change"] == -3.85

def test_intelligence_service_compare_increase():
    service = IntelligenceService()
    res = service.compare_prices(100, 150)
    assert res["change_type"] == "price_increase"
    assert res["absolute_change"] == 50
    assert res["percentage_change"] == 50.0

def test_intelligence_service_compare_no_change():
    service = IntelligenceService()
    res = service.compare_prices(99.99, 99.99)
    assert res["change_type"] == "no_change"
    assert res["absolute_change"] == 0

def test_intelligence_service_compare_none_safety():
    service = IntelligenceService()
    res = service.compare_prices(None, 100)
    assert res["change_type"] == "unknown"

def test_observation_creation_and_retrieval(setup_db):
    service = IntelligenceService()
    db = setup_db
    
    # Create test observations at different times
    now = datetime.now(timezone.utc)
    obs1 = PriceObservation(
        product_name="Test Headphones",
        merchant="Store A",
        price=100.0,
        source="test",
        query="headphones",
        observed_at=now - timedelta(days=1)
    )
    obs2 = PriceObservation(
        product_name="Test Headphones",
        merchant="Store A",
        price=90.0,
        source="test",
        query="headphones",
        observed_at=now
    )
    
    service.save_observations(db, [obs1, obs2])
    
    # Retrieve history
    history = service.get_history(db, "Test Headphones")
    assert len(history) == 2
    # Ensure ordered by observed_at descending
    assert history[0].price == 90.0
    assert history[1].price == 100.0

    # Retrieve changes
    changes = service.get_changes(db, "Test Headphones")
    assert changes["comparison"]["change_type"] == "price_decrease"
    assert changes["comparison"]["absolute_change"] == -10.0
