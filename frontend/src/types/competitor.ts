import type { LocationResolution } from './serpapi';

export interface StageStatus {
  stage: string;
  status: 'ok' | 'degraded' | 'error' | 'skipped';
  detail: string | null;
  results_count: number | null;
}

/** One recorded reason to believe a business competes here. Never inferred. */
export interface CompetitorEvidence {
  source_type: string;
  source_url: string | null;
  source_domain: string | null;
  discovery_method: string;
  entity_type: string;
  observed_at: string;

  match_method: string;
  match_confidence: string;
  status: string;
  reason: string | null;

  position: number | null;
  rating: number | null;
  reviews: number | null;
  title: string | null;
  snippet: string | null;
}

export interface Competitor {
  id: number | null;
  name: string;
  normalized_name: string | null;
  domain: string | null;
  website: string | null;

  address: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  latitude: number | null;
  longitude: number | null;
  place_id: string | null;

  /** discovered | verified | uncertain | rejected */
  status: string;
  /** business | directory | social | article | marketplace | unknown */
  entity_type: string;
  match_method: string;
  match_confidence: string;
  status_reason: string | null;

  rating: number | null;
  reviews: number | null;
  best_position: number | null;

  /**
   * Which searches found this business. A saved list spans many markets and
   * places, so a row is meaningless without the context that produced it.
   */
  market: string | null;
  location_requested: string | null;
  location_resolved: string | null;
  markets: string[];
  locations: string[];

  /** 'local' | 'organic', from the observations actually recorded. */
  discovery_sources: string[];
  discovery_methods: string[];

  /**
   * True when a provider gave a real position (address or coordinates).
   * Organic evidence carries none, which is why such a business stays
   * 'discovered' and its location reads as unverified.
   */
  has_location_evidence: boolean;

  first_seen_at: string | null;
  last_seen_at: string | null;
  evidence_count: number;
  evidence: CompetitorEvidence[];
}

/** A result that was not a business, kept so nothing disappears silently. */
export interface RejectedResult {
  title: string | null;
  url: string | null;
  domain: string | null;
  entity_type: string;
  reason: string;
  source_type: string;
}

export interface CompetitorSearchResponse {
  market: string;
  query: string;
  effective_query: string;
  location_requested: string | null;
  location_resolved: string | null;
  location_resolution: LocationResolution | null;

  /** 'success' | 'no_results'. A provider failure is a non-200 response. */
  provider_status: string;
  cache_hit: boolean;
  stages: StageStatus[];

  local_results_found: number;
  organic_results_found: number;
  business_candidates: number;
  rejected_non_business: number;
  competitors_discovered: number;
  competitors_verified: number;
  competitors_uncertain: number;
  duplicates_merged: number;
  new_competitors: number;

  competitors: Competitor[];
  rejected_results: RejectedResult[];
}

export interface CompetitorListResponse {
  total: number;
  competitors: Competitor[];
}
