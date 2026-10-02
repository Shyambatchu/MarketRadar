import type { TrendSeries } from './trend';

/** A market and location actually present in the observation history. */
export interface MarketOption {
  market: string | null;
  location: string | null;
  competitor_observations: number;
  product_observations: number;
  merchants: number;
  first_observed_at: string | null;
  last_observed_at: string | null;
}

/** What the snapshot covers. Shared by every section so they cannot be mixed. */
export interface MarketContext {
  market: string | null;
  location: string | null;
  first_observed_at: string | null;
  last_observed_at: string | null;
  observation_span_hours: number | null;
  distinct_searches: number;
  merchants: number;
  competitor_observations: number;
  product_observations: number;
}

export interface CompetitorEntry {
  merchant_id: number | null;
  name: string;
  domain: string | null;
  website: string | null;
  address: string | null;
  /** verified | discovered | uncertain | rejected — evidence strength only. */
  status: string;
  entity_type: string;
  discovery_sources: string[];
  discovery_methods: string[];
  first_seen_at: string | null;
  last_seen_at: string | null;
  observation_count: number;
  distinct_searches: number;
  present_in_latest: boolean;
  /** Stated in full so absence is never read as closure. */
  presence_note: string | null;
  has_location_evidence: boolean;
}

export interface ProductEntry {
  observation_id: number;
  merchant_id: number | null;
  merchant: string | null;
  merchant_domain: string | null;
  product_query: string;
  product_name: string | null;
  observed_size: string | null;
  size_confirmed: boolean;
  /** found | not_found | unknown */
  product_status: string;
  /** verified | unavailable | unknown */
  price_status: string;
  verification_reason: string | null;
  evidence_scope: string;
  inventory_confirmed: boolean;
  source_url: string | null;
  source_domain: string | null;
  page_type: string | null;
  observed_at: string;
}

/** A verified price observation. Unverified prices never appear here. */
export interface PriceEntry {
  observation_id: number;
  merchant: string | null;
  merchant_id: number | null;
  product_name: string | null;
  product_query: string;
  observed_size: string | null;
  price: number;
  currency: string | null;
  source_url: string | null;
  source_domain: string | null;
  evidence_scope: string;
  inventory_confirmed: boolean;
  observed_at: string;
}

/** Only populated when enough *distinct* measurements exist. */
export interface PriceStatistics {
  distinct_measurements: number;
  sufficient: boolean;
  lowest: number | null;
  highest: number | null;
  average: number | null;
  currency: string | null;
  detail: string | null;
}

export interface VisibilityEntry {
  merchant_id: number | null;
  merchant: string;
  domain: string | null;
  best_position: number | null;
  latest_position: number | null;
  rating: number | null;
  reviews: number | null;
  observed_at: string | null;
  observation_count: number;
}

export interface DataQuality {
  competitors_verified: number;
  competitors_discovered: number;
  competitors_uncertain: number;
  products_found: number;
  products_not_found: number;
  products_unknown: number;
  prices_verified: number;
  prices_unavailable: number;
  prices_unknown: number;
  trend_series: number;
  trend_series_with_direction: number;
  trend_series_insufficient_history: number;
  notes: string[];
}

export interface MarketPulseResponse {
  generated_at: string;
  /** Always false: Market Pulse is derived, never the source of truth. */
  persisted: boolean;
  context: MarketContext;
  competitors: CompetitorEntry[];
  products: ProductEntry[];
  prices: PriceEntry[];
  price_statistics: PriceStatistics;
  visibility: VisibilityEntry[];
  trends: TrendSeries[];
  data_quality: DataQuality;
  has_data: boolean;
  detail: string | null;
}

export interface MarketPulseOptionsResponse {
  generated_at: string;
  total: number;
  options: MarketOption[];
  detail: string | null;
}
