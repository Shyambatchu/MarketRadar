/**
 * Types for the intelligence endpoints added on top of the observation
 * modules: price alerts, opportunities, reports, saved searches, market
 * signals (Google Trends / Google News), usage and the dashboard summary.
 * Field names mirror the backend responses exactly.
 */

export interface PriceAlert {
  type: 'price_increase' | 'price_decrease' | 'new_offer' | 'not_observed_in_latest'
    | 'outlier' | 'price_dispersion' | 'conflicting_prices' | string;
  severity: 'info' | 'warning' | string;
  confidence: 'high' | 'medium' | 'low' | string;
  product: string;
  merchant: string | null;
  merchant_id: number | null;
  market: string | null;
  location: string | null;
  currency: string | null;
  previous_price: number | null;
  current_price: number | null;
  change_absolute: number | null;
  change_percent: number | null;
  previous_observed_at: string | null;
  observed_at: string | null;
  explanation: string;
  record_ids: number[];
  source_urls: string[];
}

export interface PriceAlertResponse {
  generated_at: string;
  thresholds: {
    min_change_percent: number;
    outlier_mad_k: number;
    dispersion_min_percent: number;
    min_merchants_for_outliers: number;
  };
  contexts_examined: number;
  verified_observations: number;
  total: number;
  alerts: PriceAlert[];
  detail: string | null;
}

export interface ScoreBreakdown {
  score: number;
  inputs: Record<'impact' | 'confidence' | 'freshness' | 'relevance', number | null>;
  weights: Record<'impact' | 'confidence' | 'freshness' | 'relevance', number>;
  contributions: Record<'impact' | 'confidence' | 'freshness' | 'relevance', number>;
  missing: string[];
  formula: string;
}

export type OpportunityStatus = 'new' | 'saved' | 'reviewed' | 'dismissed';

export interface Opportunity {
  id: number;
  title: string;
  category: string;
  market: string | null;
  location: string | null;
  product: string | null;
  merchant_id: number | null;
  score: number;
  breakdown: ScoreBreakdown;
  evidence: { record_ids: number[]; source_urls: string[]; explanation?: string; source?: string };
  confidence: string;
  relevance_note: string | null;
  suggested_action: string | null;
  status: OpportunityStatus;
  note: string | null;
  created_at: string | null;
  updated_at: string | null;
  evidence_observed_at: string | null;
}

export interface OpportunityListResponse {
  total: number;
  disclaimer: string;
  refreshed?: number;
  opportunities: Opportunity[];
}

export interface ScoringMethod {
  formula: string;
  weights: Record<string, number>;
  statuses: string[];
  disclaimer: string;
}

export interface ReportSummary {
  id: number;
  title: string;
  market: string | null;
  location: string | null;
  created_at: string | null;
  has_data: boolean;
  competitors: number;
  verified_prices: number;
  price_alerts: number;
  opportunities: number;
}

export interface SavedSearch {
  id: number;
  module: 'research' | 'competitors' | 'products' | 'prices' | 'interest' | 'news';
  label: string | null;
  query: string;
  market: string | null;
  location: string | null;
  created_at: string | null;
}

export interface InterestPoint {
  date: string;
  label: string | null;
  value: number;
  partial: boolean;
}

export interface InterestSeries {
  term: string;
  points: InterestPoint[];
  point_count: number;
  average: number | null;
  latest: number | null;
  peak_date: string | null;
  relative_change_percent: number | null;
  change_detail: string | null;
}

export interface InterestOverTime {
  terms: string[];
  geo: string | null;
  date: string;
  request_key: string;
  cache_hit: boolean;
  collected_at: string;
  disclaimer: string;
  series: InterestSeries[];
  has_data: boolean;
}

export interface InterestByRegion {
  term: string;
  geo: string | null;
  date: string;
  region: string | null;
  cache_hit: boolean;
  disclaimer: string;
  regions: { location: string | null; geo: string | null; value: number }[];
}

export interface RelatedQueries {
  term: string;
  geo: string | null;
  date: string;
  cache_hit: boolean;
  rising: { query: string; value_label: string | null; value: number | null }[];
  top: { query: string; value_label: string | null; value: number | null }[];
  detail: string;
}

export interface NewsArticle {
  id?: number;
  query?: string;
  title: string;
  link: string;
  source_name: string | null;
  published_at: string | null;
  published_label?: string | null;
  position?: number | null;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
}

export interface NewsSearchResponse {
  query: string;
  gl: string;
  hl: string;
  sort: string;
  cache_hit: boolean;
  collected_at: string;
  total: number;
  articles: NewsArticle[];
  provider_status: string;
  detail: string;
}

export interface UsageEndpointRow {
  endpoint: string;
  engine: string;
  feature: string;
  requests: number;
  credits_used: number;
  failed_requests: number;
  avg_response_seconds: number | null;
  last_request_at: string | null;
  estimated_cost_usd: number | null;
}

export interface UsageBreakdown {
  generated_at: string;
  credits_used_this_month: number;
  monthly_budget: number | null;
  budget_remaining: number | null;
  budget_exhausted: boolean;
  estimated_cost_this_month_usd: number | null;
  pricing_source: string;
  pricing_retrieved: string;
  cost_per_search_usd: number | null;
  cost_basis: string;
  plan_monthly_price_usd?: number;
  plan_searches_per_month?: number;
  by_endpoint: UsageEndpointRow[];
  daily: { day: string; credits_used: number; requests: number }[];
}

export interface DashboardSummary {
  generated_at: string;
  filters: { market: string | null; location: string | null; days: number | null };
  counts: {
    competitors: number;
    businesses: number;
    confirmed_competitors: number;
    products_found: number;
    verified_prices: number;
    competitor_observations: number;
    product_observations: number;
    markets: number;
  };
  freshness: {
    first_observed_at: string | null;
    last_observed_at: string | null;
    last_news_collected_at: string | null;
    last_search_interest_collected_at: string | null;
  };
  recent_changes: PriceAlert[];
  recent_changes_total: number;
  top_opportunities: Opportunity[];
  recent_reports: { id: number; title: string; created_at: string | null }[];
  recent_searches: { query: string; location: string | null; searched_at: string; cache_hit: boolean }[];
  health: {
    serpapi_configured: boolean;
    ai_provider_configured: boolean;
    requests_last_7_days: number;
    failed_requests_last_7_days: number;
    credits_used_this_month: number;
    monthly_budget: number | null;
    budget_remaining: number | null;
  };
}

/** How much evidence each opportunity source has, and what it yields. */
export interface OpportunitySources {
  price_evidence: {
    verified_prices: number;
    products_tracked: number;
    products_with_history: number;
    signals: { price_moves: number; price_gaps: number; new_offers: number };
  };
  search_interest: { comparisons_collected: number; rising_terms: number };
  active_by_category: Record<string, number>;
  last_refreshed_at: string | null;
}
