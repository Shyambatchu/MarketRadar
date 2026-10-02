export interface SerpSearchResult {
  position: number | null;
  title: string | null;
  link: string | null;
  displayed_link: string | null;
  snippet: string | null;
  domain: string | null;
  result_type: string;
}

export interface LocationResolution {
  requested: string;
  canonical_name: string;
  country_code: string | null;
  target_type: string | null;
  matched_candidate: string | null;
  ambiguous: boolean;
  alternatives: string[];
}

export interface SerpSearchResponse {
  query: string;
  /** What the user typed. */
  location: string | null;
  /** The canonical location the provider was actually given. */
  resolved_location: string | null;
  location_resolution: LocationResolution | null;
  engine: string;
  searched_at: string;
  cache_hit: boolean;
  /** 'success' | 'no_results'. A provider failure is a non-200 response. */
  provider_status: string;
  results: SerpSearchResult[];
  local_results?: any | null;
}

/**
 * Local request history and SerpApi's own account quota, kept apart.
 *
 * `local_*` is what this application recorded itself doing and is NOT a quota.
 * Everything else comes verbatim from SerpApi's account endpoint, the only
 * authority on what remains, and is null when it could not be read -- render
 * "Unavailable", never a blank and never a computed figure. There is no daily
 * limit or daily allowance in this contract.
 */
export interface UsageStatsResponse {
  local_requests_recorded: number;
  local_credits_used: number;
  local_failed_requests: number;
  local_cache_hits: number;

  account_quota_available: boolean;
  account_quota_detail: string | null;

  plan_name: string | null;
  account_status: string | null;
  plan_renewal_date: string | null;
  searches_per_month: number | null;
  plan_searches_left: number | null;
  extra_credits: number | null;
  total_searches_left: number | null;
  this_month_usage: number | null;
  this_hour_searches: number | null;
  account_rate_limit_per_hour: number | null;
}
