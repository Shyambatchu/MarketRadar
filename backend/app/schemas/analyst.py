from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.pulse import MarketContext


class EvidenceRef(BaseModel):
    """Where a statement came from.

    Every factual statement the analyst makes carries one of these, so a reader
    can go back to the Market Pulse section and the specific records behind it.
    """
    section: str                      # context | competitors | products | prices | visibility | trends | data_quality
    detail: Optional[str] = None
    record_ids: List[int] = []
    merchant_ids: List[int] = []
    count: Optional[int] = None


class Observation(BaseModel):
    """One factual statement, computed from the snapshot -- never generated.

    ``statement`` is produced deterministically in Python from the Market Pulse
    data. A language model is never asked to produce one, which is what makes
    "the analyst cannot invent facts" a property of the architecture rather
    than a request in a prompt.
    """
    section: str
    statement: str
    # observation | limitation | insufficient_evidence
    kind: str = "observation"
    evidence: EvidenceRef


class AnalystResponse(BaseModel):
    """Evidence-grounded analysis of one Market Pulse snapshot.

    Two distinct layers:

    * ``observations`` and the per-section lists are computed from the snapshot
      by code. They are facts, and they are present whether or not an AI
      provider is configured.
    * ``summary`` is the only text a language model produces. It is given the
      computed facts and nothing else, and its output is validated before it is
      returned. A summary that fails validation is withheld, never shown.

    The analyst states no conclusions: no winner, no market leader, no growth,
    no prediction, and no score.
    """
    generated_at: datetime
    persisted: bool = False

    # deterministic -- facts only, no provider involved
    # assisted      -- facts plus a validated narrative summary
    analysis_mode: str = "deterministic"
    provider_configured: bool = False
    provider_name: Optional[str] = None
    provider_error: Optional[str] = None

    context: MarketContext
    has_data: bool = False

    summary: Optional[str] = None
    summary_rejected: bool = False
    summary_rejection_reason: Optional[str] = None

    market_overview: List[Observation] = []
    competitor_observations: List[Observation] = []
    product_observations: List[Observation] = []
    price_analysis: List[Observation] = []
    visibility_observations: List[Observation] = []
    trend_analysis: List[Observation] = []
    data_quality: List[Observation] = []

    # Every observation above, flattened, for callers that want one list.
    observations: List[Observation] = []
    evidence: List[EvidenceRef] = []

    detail: Optional[str] = None


class AskRequest(BaseModel):
    question: str
    market: Optional[str] = None
    location: Optional[str] = None


class EvidenceItem(BaseModel):
    """One numbered piece of evidence the answer may cite as [F#]."""
    id: str
    kind: str          # observation | limitation | price_alert | news
    section: str
    statement: str
    source_urls: List[str] = []
    observed_at: Optional[datetime] = None
    record_ids: List[int] = []


class CitedStatement(BaseModel):
    statement: str
    citations: List[str] = []


class AnalystAnswer(BaseModel):
    """An answer to a question, built only from numbered evidence.

    ``facts`` restate evidence; ``interpretations`` read it; ``hypotheses`` are
    things worth checking next, explicitly unproven. ``mode`` is "assisted"
    when a model wrote the answer and it passed validation, "deterministic"
    when the evidence most relevant to the question is returned without prose.
    """
    generated_at: datetime
    question: str
    context: MarketContext
    mode: str = "deterministic"
    provider_configured: bool = False
    provider_name: Optional[str] = None
    answer: Optional[str] = None
    facts: List[CitedStatement] = []
    interpretations: List[CitedStatement] = []
    hypotheses: List[CitedStatement] = []
    missing_data: List[str] = []
    confidence: Optional[str] = None
    relevant_evidence: List[str] = []
    evidence: List[EvidenceItem] = []
    answer_rejected: bool = False
    rejection_reason: Optional[str] = None
    provider_error: Optional[str] = None
    detail: Optional[str] = None
