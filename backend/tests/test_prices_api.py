import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

def test_prices_search_no_api_key():
    # Ensure key is not set
    settings.SERPAPI_API_KEY = None
    
    response = client.get("/api/prices/search?q=wireless+headphones")
    assert response.status_code == 503
    
    data = response.json()
    assert "Live market data is not configured yet" in data["detail"]

def test_prices_search_no_query():
    response = client.get("/api/prices/search?q=")
    assert response.status_code == 400
