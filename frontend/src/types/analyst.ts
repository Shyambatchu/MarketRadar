import type { MarketContext } from './marketPulse';

/** Where a statement came from, back into the Market Pulse snapshot. */
export interface EvidenceRef {
  section: string;
  detail: string | null;
  record_ids: number[];
  merchant_ids: number[];
  count: number | null;
}

/**
 * One factual statement, computed from the snapshot — never generated.
 * A language model is never asked to produce one.
 */
export interface Observation {
  section: string;
  statement: string;
  /** observation | limitation | insufficient_evidence */
  kind: string;
  evidence: EvidenceRef;
}

export interface AnalystResponse {
  generated_at: string;
  /** Always false: the analyst derives, it does not persist. */
  persisted: boolean;

  /** deterministic — facts only; assisted — facts plus a validated summary. */
  analysis_mode: string;
  provider_configured: boolean;
  provider_name: string | null;
  provider_error: string | null;

  context: MarketContext;
  has_data: boolean;

  /** The only model-produced text. Withheld entirely if it fails validation. */
  summary: string | null;
  summary_rejected: boolean;
  summary_rejection_reason: string | null;

  market_overview: Observation[];
  competitor_observations: Observation[];
  product_observations: Observation[];
  price_analysis: Observation[];
  visibility_observations: Observation[];
  trend_analysis: Observation[];
  data_quality: Observation[];

  observations: Observation[];
  evidence: EvidenceRef[];

  detail: string | null;
}

/** One numbered evidence item an answer may cite as [F#]. */
export interface EvidenceItem {
  id: string;
  /** observation | limitation | insufficient_evidence | price_alert | news */
  kind: string;
  section: string;
  statement: string;
  source_urls: string[];
  observed_at: string | null;
  record_ids: number[];
}

export interface CitedStatement {
  statement: string;
  citations: string[];
}

/**
 * An answer built only from numbered evidence. `mode` is "assisted" when an AI
 * provider wrote it and it passed validation, otherwise "deterministic": the
 * evidence most relevant to the question, with no prose added.
 */
export interface AnalystAnswer {
  generated_at: string;
  question: string;
  context: MarketContext;
  mode: 'assisted' | 'deterministic';
  provider_configured: boolean;
  provider_name: string | null;
  answer: string | null;
  facts: CitedStatement[];
  interpretations: CitedStatement[];
  hypotheses: CitedStatement[];
  missing_data: string[];
  confidence: 'high' | 'medium' | 'low' | null;
  relevant_evidence: string[];
  evidence: EvidenceItem[];
  answer_rejected: boolean;
  rejection_reason: string | null;
  provider_error: string | null;
  detail: string | null;
}
