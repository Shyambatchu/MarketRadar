"""The /api/products contract.

Status codes carry meaning the body cannot: 422 is an unresolvable location,
502 a provider failure, and a 200 whose evidence says ``unknown`` is a real
answer rather than an error.
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine, get_db
from app.main import app
from app.routes.products import get_product_service
from app.schemas.product import ProductSearchResponse
from app.services.competitor_service import CompetitorService
from app.services.product_service import ProductService
from app.services.serpapi_organic_service import SerpApiOrganicService

from tests.stubs import StubResolver, no_account


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for table in ("search_cache", "product_observations",
                  "competitor_observations", "merchants"):
        session.execute(text("DELETE FROM " + table))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(db):
    def override_db():
        yield db

    def override_service():
        organic = SerpApiOrganicService(api_key="test_key", db=db,
                                       resolver=StubResolver(),
                                       account_fetcher=no_account)
        competitors = CompetitorService(db=db, organic_service=organic)
        return ProductService(db=db, competitor_service=competitors)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_product_service] = override_service
    yield TestClient(app)
    app.dependency_overrides.clear()


MERCHANT = {"title": "Rivertown Supply", "website": "https://rivertown.example",
            "place_id": "p1", "address": "1 Main St", "position": 1}


class Router:
    def __init__(self, per_site, fail_all=False):
        self.per_site = per_site
        self.fail_all = fail_all

    def __call__(self, params):
        q = params.get("q", "")
        outer = self

        class Search:
            @staticmethod
            def get_dict():
                if outer.fail_all:
                    raise RuntimeError("provider down")
                if q.startswith("site:"):
                    domain = q.split()[0][len("site:"):]
                    return {"organic_results": outer.per_site.get(domain, [])}
                return {"local_results": [MERCHANT], "organic_results": []}

        return Search()


PRODUCT_ROW = [{"title": "Widget 2000",
                "link": "https://rivertown.example/product/widget-2000",
                "snippet": "Widget 2000 $10.00 add to cart", "position": 1}]


def test_search_returns_the_documented_schema(client):
    router = Router({"rivertown.example": PRODUCT_ROW})
    with patch("app.services.api_budget.GoogleSearch", side_effect=router):
        response = client.get("/api/products/search", params={
            "q": "Widget 2000", "market": "Hardware",
            "location": "Austin, Texas"})

    assert response.status_code == 200
    body = ProductSearchResponse(**response.json())
    assert body.location_resolved == "Austin,Texas,United States"
    assert body.provider_status == "success"
    assert body.products_found == 1
    e = body.evidence[0]
    assert e.merchant == "Rivertown Supply"
    assert e.merchant_domain == "rivertown.example"
    assert e.product_status == "found"
    assert e.price_status == "verified"
    assert e.price == 10.0
    assert e.evidence_scope == "catalog"
    assert e.inventory_confirmed is False


def test_unresolvable_location_is_422(client):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        response = client.get("/api/products/search", params={
            "q": "Widget 2000", "location": "Zzzqqxinvalidplace"})
        assert MockSearch.call_count == 0

    assert response.status_code == 422
    assert "Zzzqqxinvalidplace" in response.json()["detail"]


def test_provider_failure_is_502_not_product_not_found(client):
    router = Router({}, fail_all=True)
    with patch("app.services.api_budget.GoogleSearch", side_effect=router):
        response = client.get("/api/products/search", params={
            "q": "Widget 2000", "location": "Austin, Texas"})

    assert response.status_code == 502
    assert "provider down" in response.json()["detail"]


def test_missing_query_is_400(client):
    assert client.get("/api/products/search",
                      params={"location": "Austin, Texas"}).status_code == 400


def test_no_evidence_is_200_with_unknown_not_an_error(client):
    """A merchant we searched and found nothing at is a real answer."""
    router = Router({"rivertown.example": []})
    with patch("app.services.api_budget.GoogleSearch", side_effect=router):
        response = client.get("/api/products/search", params={
            "q": "Widget 2000", "location": "Austin, Texas"})

    assert response.status_code == 200
    body = response.json()
    assert body["products_found"] == 0
    assert body["products_not_found"] == 0
    assert body["evidence"][0]["product_status"] == "unknown"


def test_saved_listing_and_detail_endpoints(client):
    router = Router({"rivertown.example": PRODUCT_ROW})
    with patch("app.services.api_budget.GoogleSearch", side_effect=router):
        client.get("/api/products/search", params={
            "q": "Widget 2000", "market": "Hardware",
            "location": "Austin, Texas"})

    listing = client.get("/api/products")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    record = listing.json()["observations"][0]
    assert record["merchant_name"] == "Rivertown Supply"
    assert record["evidence_scope"] == "catalog"

    detail = client.get("/api/products/" + str(record["id"]))
    assert detail.status_code == 200
    assert detail.json()["product_status"] == "found"

    assert client.get("/api/products/999999").status_code == 404


def test_listing_filters_are_honoured(client):
    router = Router({"rivertown.example": PRODUCT_ROW})
    with patch("app.services.api_budget.GoogleSearch", side_effect=router):
        client.get("/api/products/search", params={
            "q": "Widget 2000", "market": "Hardware",
            "location": "Austin, Texas"})

    assert client.get("/api/products", params={"market": "Hardware"}).json()["total"] == 1
    assert client.get("/api/products", params={"market": "Electronics"}).json()["total"] == 0
    assert client.get("/api/products", params={"q": "Widget 2000"}).json()["total"] == 1
    assert client.get("/api/products", params={"q": "Gadget 3000"}).json()["total"] == 0
    assert client.get("/api/products",
                      params={"product_status": "found"}).json()["total"] == 1


def test_listing_makes_no_provider_request(client):
    with patch("app.services.api_budget.GoogleSearch") as MockSearch:
        client.get("/api/products")
        client.get("/api/products/1")
        assert MockSearch.call_count == 0


def test_no_artificial_budget_field_in_the_product_contract():
    for name in ("daily_limit", "daily_used", "max_credits", "searches_remaining",
                 "budget_exhausted", "credits_remaining"):
        assert name not in ProductSearchResponse.model_fields, name
