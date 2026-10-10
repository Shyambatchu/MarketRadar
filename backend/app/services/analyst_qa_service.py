"""AI Analyst Q&A: answer a question from numbered, stored evidence only.

The same split as the narrative summary, applied to free-form questions:

1. **Code gathers the evidence.** The deterministic analyst observations for
   the market and location, the detected price alerts, and collected news
   headlines -- each numbered ``F1``, ``F2`` ... with its sources, dates and
   record ids. Nothing a model writes can add to this list.
2. **The model answers only from that list**, as structured JSON that cites
   evidence ids and separates facts, interpretations, hypotheses and missing
   data.
3. **The answer is validated** before it is shown: every citation must name a
   real evidence item, every statement in ``facts`` must cite one, every
   number anywhere must already appear in the evidence, and no forecast,
   market-share or closure claim may be made. A failing answer is withheld
   with the reason, and the deterministic result is returned instead.

With no provider configured the deterministic result is the answer: the
evidence items most relevant to the question, ranked by word overlap, with no
prose added. It never spends a SerpApi credit and writes nothing.
"""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.news_article import NewsArticle
from app.schemas.analyst import AnalystAnswer, CitedStatement, EvidenceItem
from app.services.ai_provider import (
    AIProvider, AIProviderError, get_ai_provider,
)
from app.services.analyst_service import (
    AnalystService, _NUMBER_RE, _canonical_number,
)
from app.services.news_service import normalize_query
from app.services.price_change_service import PriceChangeService

MAX_QUESTION_LENGTH = 500
MAX_NEWS_ITEMS = 10
DETERMINISTIC_TOP_K = 8

# Claims no answer may make, whatever the evidence: a forecast, a share of the
# market, or a business's fate. Recommendations are allowed -- but only as
# hypotheses, which the schema keeps separate from facts.
_FORBIDDEN = [re.compile(r"\b" + p, re.IGNORECASE) for p in (
    r"market share", r"will (increase|decrease|grow|fall|rise|drop)", r"forecast",
    r"we predict", r"went out of business", r"closed down", r"no longer operates",
    r"has disappeared", r"probability of success",
)]

SYSTEM_PROMPT = (
    "You are a market analyst answering a question for a business user. You are "
    "given numbered evidence items (F1, F2, ...) computed from recorded market "
    "observations, detected price changes and collected news headlines. Rules:\n"
    "1. Use only the evidence items. Do not add facts, figures, names or context "
    "from anywhere else, including your own knowledge.\n"
    "2. Cite evidence ids in square brackets, e.g. [F3], in the answer, and list "
    "them in each statement's citations.\n"
    "3. 'facts' restate evidence. 'interpretations' are cautious readings of it. "
    "'hypotheses' are things worth investigating next and must be phrased as "
    "unproven. 'missing_data' names what the evidence does not cover.\n"
    "4. Use only numbers that appear in the evidence, written exactly as they "
    "appear there.\n"
    "5. Never forecast, never estimate market share, and never say a business "
    "closed. A news headline is the publisher's claim, not a verified fact.\n"
    "6. If the evidence does not answer the question, say so plainly in the "
    "answer and use missing_data.\n"
    "7. Keep the answer under 150 words."
)

_STATEMENTS = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {"statement": {"type": "string"},
                       "citations": {"type": "array", "items": {"type": "string"}}},
        "required": ["statement", "citations"],
        "additionalProperties": False,
    },
}
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "facts": _STATEMENTS,
        "interpretations": _STATEMENTS,
        "hypotheses": _STATEMENTS,
        "missing_data": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["answer", "facts", "interpretations", "hypotheses",
                 "missing_data", "confidence"],
    "additionalProperties": False,
}

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is", "are",
         "which", "what", "who", "how", "this", "that", "with", "have", "has", "most",
         "during", "selected", "should", "next", "be", "do", "does", "any"}


def _tokens(text: str) -> set:
    return {w for w in _WORD_RE.findall((text or "").lower()) if w not in _STOP}


class AnalystQAService:
    def __init__(self, db: Session, provider: Optional[AIProvider] = None):
        self.db = db
        self.provider = provider or get_ai_provider()

    # ------------------------------------------------------------------
    def gather_evidence(self, market: Optional[str], location: Optional[str]
                        ) -> Tuple[Any, List[EvidenceItem]]:
        analysis = AnalystService(db=self.db, provider=self.provider).analyse(
            market=market, location=location, include_summary=False)
        items: List[EvidenceItem] = []

        def add(**kwargs):
            items.append(EvidenceItem(id="F" + str(len(items) + 1), **kwargs))

        for obs in analysis.observations:
            add(kind=obs.kind, section=obs.section, statement=obs.statement,
                record_ids=obs.evidence.record_ids,
                observed_at=analysis.context.last_observed_at)

        alerts = PriceChangeService(self.db).detect(market=market, location=location)
        for alert in alerts.alerts[:20]:
            add(kind="price_alert", section="price_alerts",
                statement="Price alert (" + alert.type.replace("_", " ") + ", "
                + alert.confidence + " confidence) for " + alert.product
                + (" at " + alert.merchant if alert.merchant else "") + ": "
                + alert.explanation,
                source_urls=alert.source_urls, observed_at=alert.observed_at,
                record_ids=alert.record_ids)

        if market:
            news = self.db.query(NewsArticle).filter(
                NewsArticle.normalized_query == normalize_query(market)).order_by(
                NewsArticle.published_at.desc().nullslast()).limit(MAX_NEWS_ITEMS).all()
            for article in news:
                add(kind="news", section="news",
                    statement="News headline (publisher's claim, not verified): \""
                    + (article.title or "") + "\" -- " + (article.source_name or "unknown source")
                    + (", published " + article.published_at.date().isoformat()
                       if article.published_at else ""),
                    source_urls=[article.link] if article.link else [],
                    observed_at=article.published_at, record_ids=[article.id])
        return analysis, items

    # ------------------------------------------------------------------
    def ask(self, question: str, market: Optional[str] = None,
            location: Optional[str] = None) -> AnalystAnswer:
        question = (question or "").strip()
        if len(question) < 3:
            raise ValueError("Ask a question of at least 3 characters.")
        if len(question) > MAX_QUESTION_LENGTH:
            raise ValueError("Questions are limited to " + str(MAX_QUESTION_LENGTH)
                             + " characters.")
        market = (market or "").strip() or None
        location = (location or "").strip() or None

        analysis, evidence = self.gather_evidence(market, location)
        response = AnalystAnswer(
            generated_at=datetime.now(timezone.utc), question=question,
            context=analysis.context, provider_configured=self.provider.is_configured(),
            provider_name=getattr(self.provider, "name", None), evidence=evidence)

        if not analysis.has_data and not evidence:
            response.detail = ("No observations match this market and location, so there "
                               "is no evidence to answer from.")
            response.missing_data = ["Any recorded observations for this selection."]
            return response

        response.relevant_evidence = self._rank(question, evidence)
        if not self.provider.is_configured():
            response.detail = ("No AI provider is configured, so the evidence items most "
                               "relevant to the question are listed without a written "
                               "answer. Set AI_PROVIDER and AI_API_KEY to enable answers.")
            return response

        try:
            raw = self._call(question, evidence)
        except AIProviderError as exc:
            response.provider_error = str(exc)
            response.detail = "The AI provider failed; the most relevant evidence is listed."
            return response
        except Exception as exc:
            response.provider_error = "The AI provider failed: " + type(exc).__name__ + "."
            return response

        ok, reason = validate_answer(raw, evidence)
        if not ok:
            response.answer_rejected = True
            response.rejection_reason = reason
            response.detail = ("The written answer was withheld because it did not pass "
                               "validation; the most relevant evidence is listed instead.")
            return response

        response.mode = "assisted"
        response.answer = raw["answer"].strip()
        response.facts = [CitedStatement(**s) for s in raw["facts"]]
        response.interpretations = [CitedStatement(**s) for s in raw["interpretations"]]
        response.hypotheses = [CitedStatement(**s) for s in raw["hypotheses"]]
        response.missing_data = list(raw["missing_data"])
        response.confidence = raw["confidence"]
        return response

    def _call(self, question: str, evidence: List[EvidenceItem]) -> Dict[str, Any]:
        lines = []
        for item in evidence:
            when = (" (observed " + item.observed_at.date().isoformat() + ")"
                    if item.observed_at else "")
            src = (" Sources: " + ", ".join(item.source_urls[:3])) if item.source_urls else ""
            lines.append(item.id + " [" + item.kind + "]" + when + ": " + item.statement + src)
        user_prompt = ("Evidence:\n" + "\n".join(lines) + "\n\nQuestion: " + question)
        if hasattr(self.provider, "generate_json"):
            return self.provider.generate_json(SYSTEM_PROMPT, user_prompt, ANSWER_SCHEMA)
        import json
        text = self.provider.generate(SYSTEM_PROMPT, user_prompt
                                      + "\n\nRespond with JSON only, matching: "
                                      + json.dumps(ANSWER_SCHEMA))
        try:
            data = json.loads(text)
        except ValueError:
            raise AIProviderError("The AI provider returned an answer that was not valid JSON.")
        return data

    @staticmethod
    def _rank(question: str, evidence: List[EvidenceItem]) -> List[str]:
        wanted = _tokens(question)
        scored = []
        for index, item in enumerate(evidence):
            overlap = len(wanted & _tokens(item.statement + " " + item.section))
            # Limitations always matter to "how sure are we" questions.
            if item.kind in ("limitation", "insufficient_evidence") and \
                    wanted & {"weak", "conflicting", "confidence", "missing", "evidence"}:
                overlap += 2
            if overlap:
                scored.append((-overlap, index, item.id))
        scored.sort()
        ranked = [i for _, _, i in scored[:DETERMINISTIC_TOP_K]]
        return ranked or [e.id for e in evidence[:DETERMINISTIC_TOP_K]]


def validate_answer(raw: Any, evidence: List[EvidenceItem]) -> Tuple[bool, Optional[str]]:
    """Reject an answer that cites nothing real, invents a figure or forecasts."""
    if not isinstance(raw, dict):
        return False, "The answer was not a JSON object."
    for key in ("answer", "facts", "interpretations", "hypotheses", "missing_data"):
        if key not in raw:
            return False, "The answer was missing '" + key + "'."
    ids = {e.id for e in evidence}
    known = set()
    for e in evidence:
        known.update(_canonical_number(n) for n in _NUMBER_RE.findall(e.statement))
    # Evidence ids themselves ("F12") contain digits that are not figures.
    known.update(_canonical_number(i[1:]) for i in ids)

    texts = [str(raw.get("answer") or "")]
    for section in ("facts", "interpretations", "hypotheses"):
        statements = raw.get(section) or []
        if not isinstance(statements, list):
            return False, "'" + section + "' was not a list."
        for s in statements:
            if not isinstance(s, dict) or not isinstance(s.get("statement"), str):
                return False, "A statement in '" + section + "' was malformed."
            cites = s.get("citations") or []
            if section == "facts" and not cites:
                return False, "A fact was stated without citing evidence."
            bad = [c for c in cites if c not in ids]
            if bad:
                return False, "The answer cited evidence that does not exist: " + bad[0] + "."
            texts.append(s["statement"])
    for cited in re.findall(r"\[(F\d+)\]", texts[0]):
        if cited not in ids:
            return False, "The answer cited evidence that does not exist: " + cited + "."
    texts.extend(str(m) for m in raw.get("missing_data") or [])

    for text in texts:
        for pattern in _FORBIDDEN:
            if pattern.search(text):
                return False, "The answer made a claim the evidence cannot support: '" \
                    + pattern.pattern.replace("\\b", "") + "'."
        stripped = re.sub(r"\[F\d+\]", "", text)
        for number in _NUMBER_RE.findall(stripped):
            if _canonical_number(number) not in known:
                return False, ("The answer cited a figure that does not appear in the "
                               "evidence: '" + number + "'.")
    return True, None
