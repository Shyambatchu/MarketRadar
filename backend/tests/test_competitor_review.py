"""Competitor review: the user decides whether a business is a competitor.

An organic search result is never proof of competition (spec §6). Review is
recorded apart from the identity status, audited, never overwritten by a later
search, and a rejected business is skipped by Products.
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.merchant import Merchant


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for table in ("audit_events", "competitor_observations", "product_observations",
                  "merchants"):
        session.execute(text("DELETE FROM " + table))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


def make(db, name="Alpha Bikes"):
    m = Merchant(name=name, normalized_name=name.lower().replace(" ", ""),
                 status="discovered", entity_type="business",
                 normalized_domain=name.lower().replace(" ", "") + ".example")
    db.add(m)
    db.commit()
    return m.id


def test_reject_records_the_decision_and_an_audit_row(db, client):
    mid = make(db)
    r = client.patch("/api/competitors/" + str(mid),
                     json={"review_status": "rejected", "review_note": "a directory"})
    assert r.status_code == 200
    body = r.json()
    assert body["review_status"] == "rejected"
    assert body["review_note"] == "a directory"
    assert body["reviewed_at"]
    # Identity evidence is untouched.
    assert body["status"] == "discovered"
    event = db.query(AuditEvent).one()
    assert event.entity_id == mid and event.action == "review_updated"
    assert json.loads(event.detail)["review_status"] == [None, "rejected"]


def test_rename_and_clear(db, client):
    mid = make(db)
    client.patch("/api/competitors/" + str(mid), json={"display_name": "Alpha"})
    r = client.patch("/api/competitors/" + str(mid),
                     json={"display_name": "", "review_status": "unreviewed"})
    assert r.json()["display_name"] is None
    assert r.json()["review_status"] is None


def test_a_no_op_update_writes_no_audit_row(db, client):
    mid = make(db)
    client.patch("/api/competitors/" + str(mid), json={})
    assert db.query(AuditEvent).count() == 0


def test_invalid_status_and_missing_competitor(db, client):
    mid = make(db)
    assert client.patch("/api/competitors/" + str(mid),
                        json={"review_status": "winner"}).status_code == 400
    assert client.patch("/api/competitors/999999",
                        json={"review_status": "confirmed"}).status_code == 404


def test_saved_list_filters_by_review(db, client):
    a, b = make(db, "Alpha Bikes"), make(db, "Beta Bikes")
    client.patch("/api/competitors/" + str(a), json={"review_status": "confirmed"})
    confirmed = client.get("/api/competitors?review_status=confirmed").json()
    assert [c["id"] for c in confirmed["competitors"]] == [a]
    unreviewed = client.get("/api/competitors?review_status=unreviewed").json()
    assert [c["id"] for c in unreviewed["competitors"]] == [b]


def test_rejected_competitors_are_not_searched_by_products(db, monkeypatch):
    from app.schemas.competitor import Competitor, CompetitorSearchResponse
    from app.services.product_service import ProductService

    searched = []

    class Organic:
        api_key = "test-key"

    class Competitors:
        organic = Organic()

        def discover(self, **kwargs):
            def comp(i, name, review):
                return Competitor(id=i, name=name, domain=name + ".example",
                                  status="verified", match_confidence="high",
                                  review_status=review)
            return CompetitorSearchResponse(
                market="m", query="m", effective_query="m", location_requested="x",
                provider_status="success",
                competitors=[comp(1, "kept", None), comp(2, "dropped", "rejected")])

    class Provider:
        def discover_prices(self, merchant, *args, **kwargs):
            searched.append(merchant["domain"])
            return {"status": "ok", "observations": [], "off_domain_rejected": 0}

    service = ProductService(db=db, competitor_service=Competitors(),
                             website_provider=Provider())
    service.discover(product="widget", location="x", persist=False)
    assert searched == ["kept.example"]


def test_discovery_never_overwrites_a_review(db):
    """A later search updates identity status but leaves the review alone."""
    from app.services.competitor_service import CompetitorService
    mid = make(db)
    service = CompetitorService(db=db, organic_service=None)
    service.review(mid, review_status="rejected")
    candidate = {"name": "Alpha Bikes", "normalized_name": "alphabikes",
                 "domain": "alphabikes.example", "website": None, "address": None,
                 "place_id": None, "latitude": None, "longitude": None,
                 "rating": None, "reviews": None, "source_type": "organic",
                 "discovery_method": "google_organic", "entity_type": "business",
                 "match_method": "new", "match_confidence": "unmatched",
                 "evidence": [{"source_type": "organic", "source_url": None,
                               "source_domain": "alphabikes.example",
                               "discovery_method": "google_organic",
                               "entity_type": "business", "position": 1,
                               "rating": None, "reviews": None, "title": "Alpha",
                               "snippet": None, "match_method": "new",
                               "match_confidence": "unmatched",
                               "classification_reason": None,
                               "classification_confidence": "medium"}]}
    competitor, _ = service._persist(candidate, "verified", None, "m", "q", "q", "x", "X")
    db.commit()
    assert competitor.review_status == "rejected"
    assert db.query(Merchant).filter(Merchant.id == mid).one().status == "verified"
