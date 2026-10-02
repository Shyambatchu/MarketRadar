/**
 * One distinct measurement.
 *
 * `observation_count` is how many stored observations collapsed into this
 * point. Re-running a search inside the response cache window returns
 * byte-identical data, so several observations can describe one measurement.
 */
export interface TrendPoint {
  value: number | null;
  label: string | null;
  observed_at: string;
  observation_count: number;
}

/**
 * Movement of one metric for one subject, within one comparable context.
 *
 * `status` is `trend` (two or more distinct measurements),
 * `insufficient_history` (fewer than two — no direction is claimed), or
 * `no_data`. A single measurement observed repeatedly is never "flat".
 */
export interface TrendSeries {
  subject: string;
  subject_id: number | null;
  metric: string;
  context: string | null;

  status: string;
  direction: string | null;
  change_absolute: number | null;
  change_percent: number | null;

  first_value: number | null;
  last_value: number | null;
  first_observed_at: string | null;
  last_observed_at: string | null;
  observation_span_hours: number | null;

  raw_observations: number;
  distinct_points: number;
  points: TrendPoint[];

  detail: string | null;
}

export interface MerchantPresence {
  merchant: string;
  merchant_id: number | null;
  domain: string | null;
  market: string | null;
  location: string | null;
  status: string;
  first_seen_at: string;
  last_seen_at: string;
  observation_count: number;
  distinct_searches: number;
  /** False is not proof a business has gone — a search may return a different slice. */
  present_in_latest: boolean;
}

export interface ContextSummary {
  market: string | null;
  location: string | null;
  source: string;
  merchants: number;
  observations: number;
  distinct_searches: number;
  first_observed_at: string | null;
  last_observed_at: string | null;
  span_hours: number | null;
  analyzable: boolean;
  detail: string | null;
}

export interface TrendSummaryResponse {
  generated_at: string;
  /** Always false: trends are derived, never the source of truth. */
  persisted: boolean;

  competitor_observations: number;
  product_observations: number;
  merchants_tracked: number;
  verified_price_observations: number;

  contexts: ContextSummary[];
  analyzable_contexts: number;
  insufficient_history: boolean;
  detail: string | null;
}

export interface TrendListResponse {
  generated_at: string;
  persisted: boolean;
  total: number;
  analyzable: number;
  insufficient_history: number;
  series: TrendSeries[];
  detail: string | null;
}

export interface MerchantPresenceResponse {
  generated_at: string;
  persisted: boolean;
  total: number;
  contexts: ContextSummary[];
  merchants: MerchantPresence[];
  detail: string | null;
}
