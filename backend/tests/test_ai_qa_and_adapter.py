"""Anthropic adapter request shape, and evidence-grounded Q&A validation.

No test reaches a real AI provider: the adapter is driven with a fake SDK
client and Q&A with fake providers.
"""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.main import app
from app.models.merchant import Merchant
from app.models.news_article import NewsArticle
from app.models.product_observation import ProductObservation
from app.services.ai_provider import AIProviderError, get_ai_provider
from app.services.analyst_qa_service import AnalystQAService, validate_answer
from app.services.anthropic_provider import AnthropicProvider
from app.schemas.analyst import EvidenceItem

BASE = datetime(2026, 5, 1, 12, tzinfo=timezone.utc)


# ------------------------------------------------------------ adapter
class FakeMessages:
    def __init__(self, reply="ok", stop_reason="end_turn"):
        self.reply, self.stop_reason, self.calls = reply, stop_reason, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason=self.stop_reason,
                               content=[SimpleNamespace(type="thinking", thinking=""),
                                        SimpleNamespace(type="text", text=self.reply)])


def adapter(**kw):
    messages = FakeMessages(**kw)
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    return AnthropicProvider(api_key="test", client=client), messages


def test_adapter_request_shape():
    provider, messages = adapter(reply="A summary.")
    assert provider.generate("sys", "user") == "A summary."
    call = messages.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["output_config"] == {"effort": "medium"}
    assert call["max_tokens"] >= 16000
    assert "thinking" not in call  # always on for this model; never disabled


def test_adapter_structured_output():
    provider, messages = adapter(reply=json.dumps({"answer": "x"}))
    assert provider.generate_json("s", "u", {"type": "object"}) == {"answer": "x"}
    assert messages.calls[0]["output_config"]["format"]["type"] == "json_schema"


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_adapter_refusal_and_truncation_are_errors(stop_reason):
    provider, _ = adapter(stop_reason=stop_reason)
    with pytest.raises(AIProviderError):
        provider.generate("s", "u")


def test_adapter_rejects_non_json():
    provider, _ = adapter(reply="not json")
    with pytest.raises(AIProviderError):
        provider.generate_json("s", "u", {})


def test_the_anthropic_adapter_is_registered():
    provider = get_ai_provider("anthropic", "test-key")
    assert provider.name == "anthropic" and provider.is_configured()
    assert get_ai_provider("", "test-key").is_configured() is False


# ------------------------------------------------------------ validation
EVIDENCE = [
    EvidenceItem(id="F1", kind="observation", section="prices",
                 statement="Widget is priced at 12.50 USD at Alpha."),
    EvidenceItem(id="F2", kind="price_alert", section="price_alerts",
                 statement="Price rose 20.0% at Alpha."),
]


def answer(**overrides):
    base = {"answer": "Widget costs 12.50 USD at Alpha [F1] after a 20.0% rise [F2].",
            "facts": [{"statement": "Widget is 12.50 USD at Alpha.", "citations": ["F1"]}],
            "interpretations": [], "hypotheses": [], "missing_data": [],
            "confidence": "medium"}
    base.update(overrides)
    return base


def test_a_grounded_answer_passes():
    assert validate_answer(answer(), EVIDENCE) == (True, None)


@pytest.mark.parametrize("bad,reason", [
    (dict(answer="Prices are 99 USD [F1]."), "figure"),
    (dict(answer="See [F9]."), "does not exist"),
    (dict(facts=[{"statement": "Uncited.", "citations": []}]), "without citing"),
    (dict(hypotheses=[{"statement": "Prices will increase.", "citations": ["F2"]}]), "claim"),
    (dict(interpretations=[{"statement": "Alpha has market share.", "citations": ["F1"]}]),
     "claim"),
])
def test_ungrounded_answers_are_withheld(bad, reason):
    ok, why = validate_answer(answer(**bad), EVIDENCE)
    assert not ok and reason in why


# ------------------------------------------------------------ service
@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for table in ("product_observations", "competitor_observations", "merchants",
                  "news_articles"):
        session.execute(text("DELETE FROM " + table))
    session.commit()
    m = Merchant(name="Alpha", normalized_name="alpha", status="verified",
                 entity_type="business", normalized_domain="alpha.example")
    session.add(m)
    session.commit()
    for day, price in ((0, 10.0), (1, 12.0)):
        session.add(ProductObservation(
            merchant_id=m.id, product_query="Widget", normalized_query="widget",
            market="Widgets", location_resolved="Austin,Texas,United States",
            product_name="Widget", product_status="found", price_status="verified",
            price=price, currency="USD", source_url="https://alpha.example/p",
            observed_at=BASE + timedelta(days=day)))
    session.add(NewsArticle(query="Widgets", normalized_query="widgets",
                            title="Widget demand news", link="https://n.example/a",
                            source_name="Example News", published_at=BASE))
    session.commit()
    yield session
    session.close()


class NoProvider:
    name = "not_configured"

    def is_configured(self):
        return False


class FakeProvider:
    name = "fake"

    def __init__(self, reply):
        self.reply = reply

    def is_configured(self):
        return True

    def generate_json(self, system, user, schema):
        self.prompt = user
        return self.reply(user) if callable(self.reply) else self.reply


def test_deterministic_answer_lists_relevant_evidence(db):
    result = AnalystQAService(db, provider=NoProvider()).ask(
        "Which products have unusual price changes?", market="Widgets",
        location="Austin,Texas,United States")
    assert result.mode == "deterministic" and result.answer is None
    kinds = {e.kind for e in result.evidence}
    assert {"price_alert", "news"} <= kinds
    assert result.relevant_evidence
    alert = next(e for e in result.evidence if e.kind == "price_alert")
    assert alert.source_urls == ["https://alpha.example/p"]


def test_assisted_answer_cites_real_evidence(db):
    def reply(prompt):
        alert_id = next(line.split(" ")[0] for line in prompt.splitlines()
                        if "[price_alert]" in line)
        return {"answer": "A price increase was detected [" + alert_id + "].",
                "facts": [{"statement": "A price increase was detected.",
                           "citations": [alert_id]}],
                "interpretations": [], "hypotheses": [
                    {"statement": "Check whether the size changed.", "citations": [alert_id]}],
                "missing_data": ["Sales volumes."], "confidence": "medium"}
    provider = FakeProvider(reply)
    result = AnalystQAService(db, provider=provider).ask(
        "What changed?", market="Widgets", location="Austin,Texas,United States")
    assert result.mode == "assisted" and result.answer.startswith("A price increase")
    assert "publisher's claim" in provider.prompt


def test_an_invented_figure_falls_back_to_evidence(db):
    provider = FakeProvider(answer(answer="Prices doubled to 999 USD."))
    result = AnalystQAService(db, provider=provider).ask(
        "What changed?", market="Widgets", location="Austin,Texas,United States")
    assert result.mode == "deterministic" and result.answer_rejected
    assert "999" in result.rejection_reason and result.relevant_evidence


def test_ask_endpoint_validation(db):
    client = TestClient(app)
    assert client.post("/api/analyst/ask", json={"question": "?"}).status_code == 400
    r = client.post("/api/analyst/ask", json={"question": "What changed in this market?",
                                              "market": "Widgets"})
    assert r.status_code == 200 and r.json()["evidence"]
