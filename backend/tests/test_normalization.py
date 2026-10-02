import pytest
from app.services.normalization_service import NormalizationService

@pytest.fixture
def test_google_shopping_fixture():
    # LOCAL TEST FIXTURE ONLY - Not real market data
    return {
        "shopping_results": [
            {
                "position": 1,
                "title": "Test Wireless Headphones",
                "product_id": "12345",
                "link": "https://example.com/product",
                "source": "TechStore",
                "price": "$99.99",
                "extracted_price": 99.99,
                "extracted_old_price": 129.99,
                "currency": "$",
                "rating": 4.5,
                "reviews": 120,
                "delivery": "Free delivery",
                "snippet": "Great sound quality."
            },
            {
                "position": 2,
                "title": "Missing Price Product",
                "source": "OtherStore"
                # missing price, rating, reviews, old_price, delivery
            },
            {
                "title": "", # Empty title should be skipped
                "source": "Store"
            }
        ]
    }

def test_normalization_valid(test_google_shopping_fixture):
    service = NormalizationService()
    observations = service.normalize_market_observation(test_google_shopping_fixture, query="headphones")
    
    assert len(observations) == 2
    
    obs1 = observations[0]
    assert obs1.product_name == "Test Wireless Headphones"
    assert obs1.price == 99.99
    assert obs1.old_price == 129.99
    assert obs1.rating == 4.5
    assert obs1.review_count == 120
    assert obs1.merchant == "TechStore"
    assert obs1.delivery == "Free delivery"
    assert obs1.query == "headphones"
    
    obs2 = observations[1]
    assert obs2.product_name == "Missing Price Product"
    assert obs2.price is None
    assert obs2.old_price is None
    assert obs2.rating is None
    assert obs2.review_count is None
    assert obs2.merchant == "OtherStore"

def test_normalization_empty():
    service = NormalizationService()
    observations = service.normalize_market_observation({}, query="test")
    assert len(observations) == 0
