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
