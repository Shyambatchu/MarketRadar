import type { LocationResolution } from './serpapi';

export interface StageStatus {
  stage: string;
  status: 'ok' | 'degraded' | 'error' | 'skipped';
  detail: string | null;
  results_count: number | null;
}

/**
 * One recorded observation of a product at a merchant.
 *
 * `product_status` and `price_status` are independent: a product can be found
 * with no usable price, and that says nothing about whether it exists.
 */
export interface ProductEvidence {
  merchant: string;
  merchant_id: number | null;
  merchant_domain: string | null;
  merchant_match_status: string;

  product_name: string | null;
  normalized_product_name: string | null;
  observed_size: string | null;
  size_confirmed: boolean;

  /** found | not_found | unknown */
  product_status: string;
  /** verified | unavailable | unknown */
  price_status: string;
  verification_reason: string | null;

  price: number | null;
  currency: string | null;

  source_type: string | null;
  source_url: string | null;
  source_domain: string | null;
  discovery_method: string | null;
  page_type: string | null;

  /** catalog | store_inventory | marketplace_listing */
  evidence_scope: string;
  /** A catalogue listing never proves a physical store holds stock. */
  inventory_confirmed: boolean;

  match_method: string;
  match_reason: string | null;
  snippet: string | null;
  observed_at: string;
}

/** Evidence that could not establish product identity, kept visible. */
export interface RejectedProductResult {
  merchant: string;
  title: string | null;
  url: string | null;
  page_type: string | null;
  reason: string;
  detail: string | null;
}

export interface ProductSearchResponse {
  product_query: string;
  market: string | null;
  location_requested: string | null;
  location_resolved: string | null;
  location_resolution: LocationResolution | null;

  /** 'success' | 'no_results'. A provider failure is a non-200 response. */
  provider_status: string;
  cache_hit: boolean;
  stages: StageStatus[];

  merchants_considered: number;
  merchants_searched: number;
  merchants_without_domain: number;
  merchant_provider_errors: number;

  website_rows_examined: number;
  off_domain_rejected: number;
  listing_pages_rejected: number;
  candidate_matches: number;

  products_found: number;
  products_not_found: number;
  products_unknown: number;
  prices_verified: number;
  prices_unavailable: number;

  evidence: ProductEvidence[];
  rejected_results: RejectedProductResult[];
}

export interface ProductObservationRecord {
  id: number;
  merchant_id: number | null;
  merchant_name: string | null;
  merchant_domain: string | null;

  product_query: string;
  market: string | null;
  location_resolved: string | null;

  product_name: string | null;
  observed_size: string | null;
  size_confirmed: boolean;
  product_status: string;
  price_status: string;
  verification_reason: string | null;
  price: number | null;
  currency: string | null;

  source_type: string | null;
  source_url: string | null;
  source_domain: string | null;
  discovery_method: string | null;
  page_type: string | null;
  evidence_scope: string;
  inventory_confirmed: boolean;
  match_method: string;
  match_reason: string | null;
  merchant_match_status: string;
  snippet: string | null;
  observed_at: string;
}

export interface ProductObservationListResponse {
  total: number;
  observations: ProductObservationRecord[];
}
