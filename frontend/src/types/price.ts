export interface PriceObservation {
  product_name: string;
  product_id: string | null;
  merchant: string | null;
  price: number | null;
  old_price: number | null;
  currency: string | null;
  rating: number | null;
  review_count: number | null;
  delivery: string | null;
  product_link: string | null;
  snippet: string | null;
  position: number | null;
  source: string;
  query: string;
  location: string | null;
  observed_at: string;
}

export interface PriceSearchResponse {
  query: string;
  location: string | null;
  total_results: number;
  observations: PriceObservation[];
  source: string;
  observed_at: string;
}

export interface PriceComparison {
  change_type: 'price_increase' | 'price_decrease' | 'no_change' | 'unknown';
  previous_price: number | null;
  current_price: number | null;
  absolute_change: number | null;
  percentage_change: number | null;
}

export interface PriceChangesResponse {
  product_name: string;
  merchant: string | null;
  comparison: PriceComparison;
  current_observation_date: string;
  previous_observation_date: string;
}

export interface PriceHistoryResponse {
  product_name: string;
  history: any[]; // Using any to avoid duplicating the entire DB model schema in frontend for now
}
