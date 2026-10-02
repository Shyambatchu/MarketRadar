import api from './api';

export interface LocalPriceObservation {
  merchant: string;
  merchant_id: string | null;
  merchant_name: string | null;
  merchant_domain: string | null;
  product_name: string;
  normalized_product_name: string | null;
  brand: string | null;
  variant: string | null;
  size: string | null;
  price: number | null;
  currency: string;
  availability: string | null;
  source_type: string;
  source_domain: string | null;
  source_url: string | null;
  discovery_method: string | null;
  observed_at: string;
  snippet_text: string | null;
  verification_reason: string | null;
  verification_status: string;

  // What the evidence actually covers: a catalogue listing is not proof that
  // a specific physical store holds stock.
  evidence_scope: string;
  inventory_confirmed: boolean;
  page_type: string | null;
  merchant_match_status: string;

  // Legacy fields
  distance: number | null;
  difference: number | null;
  is_reference_store: boolean;
  match_type: string;
  match_method: string;
  match_confidence: string;
  source: string;
}

export interface NearbyMerchantStatus {
  merchant: string;
  address: string | null;
  distance: number;
  website: string | null;
  place_id: string | null;
  
  product_status: string;
  price_status: string;
  
  product_name: string | null;
  product_size: string | null;
  product_variant: string | null;
  
  verification_reason: string | null;
  price: number | null;
  price_source: string | null;
  source_domain: string | null;
  source_url: string | null;

  evidence_scope: string | null;
  inventory_confirmed: boolean;
  merchant_match_status: string;
}

export interface StageStatus {
  stage: string;
  status: 'ok' | 'degraded' | 'error' | 'skipped';
  detail: string | null;
  results_count: number | null;
}

export interface SearchCenter {
  name: string;
  latitude: number;
  longitude: number;
  resolution_method: string | null;
}

export interface LocalPriceSearchResponse {
  searched_product: string;
  searched_area: string;
  searched_radius: number;
  search_center: SearchCenter | null;
  product_name: string;
  area: string;
  radius: number;
  lowest_price: number | null;
  average_price: number | null;
  highest_price: number | null;
  
  nearby_merchants_discovered: number;
  product_evidence_found: number;
  product_evidence_not_found: number;
  product_evidence_unknown: number;
  price_unavailable_count: number;
  
  website_results_found: number;
  website_off_domain_rejected: number;
  website_listing_pages: number;
  shopping_results_found: number;
  candidate_product_matches: number;
  exact_product_matches: number;
  merchant_matches: number;
  website_candidates: number;
  website_exact_matches: number;
  website_merchant_matches: number;
  shopping_candidates: number;
  shopping_exact_matches: number;
  shopping_merchant_matches: number;
  merchant_uncertain_count: number;
  verified_local_prices: number;

  verified_sizes: string[];
  mixed_size_statistics: boolean;
  stages: StageStatus[];
  
  reference_price: number | null;
  reference_store: NearbyMerchantStatus | null;
  
  nearby_merchants: NearbyMerchantStatus[];
  verified_price_observations: LocalPriceObservation[];
}

export const searchLocalPrices = async (product: string, area: string, radius: number, referenceStore?: string, signal?: AbortSignal): Promise<LocalPriceSearchResponse> => {
  const params = new URLSearchParams();
  params.append('product', product);
  params.append('area', area);
  params.append('radius', radius.toString());
  if (referenceStore) {
    params.append('reference_store', referenceStore);
  }
  
  const response = await api.get<LocalPriceSearchResponse>(`/prices/local?${params.toString()}`, { signal });
  return response.data;
};
