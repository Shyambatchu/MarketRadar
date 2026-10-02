"""The /api/competitors contract.

Status codes carry meaning the body cannot, and the frontend depends on the
distinction: 422 is an unresolvable location, 502 is a provider failure, and a
200 with an empty list means the search genuinely found nothing.
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine, get_db
from app.main import app
from app.routes.competitors import get_competitor_service
from app.schemas.competitor import CompetitorSearchResponse
from app.services.competitor_service import CompetitorService
from app.services.serpapi_organic_service import SerpApiOrganicService

from tests.stubs import StubResolver, no_account


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    session.execute(text("DELETE FROM search_cache"))
    session.execute(text("DELETE FROM competitor_observations"))
    session.execute(text("DELETE FROM merchants"))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(db):
    """A client wired to the test session, with offline location and account."""
    def override_db():
        yield db

    def override_service():
        organic = SerpApiOrganicService(api_key="test_key", db=db,
                                       resolver=StubResolver(),
                                       account_fetcher=no_account)
        return CompetitorService(db=db, organic_service=organic)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_competitor_service] = override_service
    yield TestClient(app)
    app.dependency_overrides.clear()


def payload(local_results=(), organic_results=()):
    return {"local_results": list(local_results),
            "organic_results": list(organic_results)}


LOCAL_ONE = [{"title": "Bean & Brew", "website": "https://beanandbrew.com",
              "address": "1 Main St", "place_id": "p1", "rating": 4.5,
              "reviews": 88, "position": 1}]


def test_search_returns_the_documented_schema(client):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = payload(LOCAL_ONE)
        response = client.get("/api/competitors/search", params={
            "market": "Coffee Shops", "q": "coffee shops",
            "location": "Austin, Texas"})

    assert response.status_code == 200
    body = CompetitorSearchResponse(**response.json())
    assert body.location_resolved == "Austin,Texas,United States"
    assert body.provider_status == "success"
    assert body.competitors_verified == 1
    competitor = body.competitors[0]
    assert competitor.name == "Bean & Brew"
    assert competitor.domain == "beanandbrew.com"
    assert competitor.status == "verified"
    assert competitor.evidence[0].discovery_method == "google_maps_local"


def test_unresolvable_location_is_422_with_a_readable_message(client):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        response = client.get("/api/competitors/search", params={
            "market": "Coffee Shops", "location": "Zzzqqxinvalidplace"})
        assert MockSearch.call_count == 0

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "Zzzqqxinvalidplace" in detail
    assert "postal code" in detail


def test_provider_failure_is_502_not_an_empty_list(client):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.side_effect = RuntimeError("provider down")
        response = client.get("/api/competitors/search", params={
            "market": "Coffee Shops", "location": "Austin, Texas"})

    assert response.status_code == 502
    assert "provider down" in response.json()["detail"]


def test_genuinely_empty_search_is_200_with_no_results(client):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = payload()
        response = client.get("/api/competitors/search", params={
            "market": "Fitness Centres", "location": "Austin, Texas"})

    assert response.status_code == 200
    body = response.json()
    assert body["provider_status"] == "no_results"
    assert body["competitors"] == []


def test_missing_market_and_query_is_400(client):
    response = client.get("/api/competitors/search",
                          params={"location": "Austin, Texas"})
    assert response.status_code == 400


def test_saved_listing_and_detail_endpoints(client):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = payload(LOCAL_ONE)
        client.get("/api/competitors/search", params={
            "market": "Coffee Shops", "q": "coffee shops",
            "location": "Austin, Texas"})

    listing = client.get("/api/competitors")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    competitor_id = listing.json()["competitors"][0]["id"]

    detail = client.get("/api/competitors/" + str(competitor_id))
    assert detail.status_code == 200
    assert detail.json()["evidence_count"] >= 1
    assert detail.json()["evidence"][0]["source_type"] == "local"

    assert client.get("/api/competitors/999999").status_code == 404


def test_listing_filters_are_honoured(client):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        MockSearch.return_value.get_dict.return_value = payload(LOCAL_ONE)
        client.get("/api/competitors/search", params={
            "market": "Coffee Shops", "location": "Austin, Texas"})

    assert client.get("/api/competitors",
                      params={"market": "Coffee Shops"}).json()["total"] == 1
    assert client.get("/api/competitors",
                      params={"market": "Automotive Repair"}).json()["total"] == 0
    assert client.get("/api/competitors",
                      params={"status": "uncertain"}).json()["total"] == 0


def test_listing_makes_no_provider_request(client):
    """Reading saved competitors must never spend a credit."""
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        client.get("/api/competitors")
        client.get("/api/competitors/1")
        assert MockSearch.call_count == 0


def test_no_artificial_budget_field_in_the_competitor_contract():
    forbidden = ("daily_limit", "daily_used", "max_credits", "searches_remaining",
                 "budget_exhausted", "credits_remaining")
    for name in forbidden:
        assert name not in CompetitorSearchResponse.model_fields, name
