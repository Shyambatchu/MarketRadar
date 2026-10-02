import api from './api';
import type {
  ProductObservationListResponse, ProductObservationRecord,
  ProductSearchResponse,
} from '../types/product';

export interface ProductSearchParams {
  query: string;
  market?: string;
  location?: string;
  maxMerchants?: number;
}

/**
 * Find product evidence across the merchants in a market.
 *
 * Errors are meaningful and must not be flattened: 422 is a location with no
 * provider-supported equivalent, 502 is a provider failure, and a 200 whose
 * evidence reads `unknown` is a real answer, not an error.
 */
export const searchProducts = async (
  { query, market, location, maxMerchants }: ProductSearchParams,
  signal?: AbortSignal,
): Promise<ProductSearchResponse> => {
  const params = new URLSearchParams();
  params.append('q', query);
  if (market) params.append('market', market);
  if (location) params.append('location', location);
  if (maxMerchants) params.append('max_merchants', String(maxMerchants));

  const response = await api.get<ProductSearchResponse>(
    `/products/search?${params.toString()}`, { signal });
  return response.data;
};

/** Saved observations. Reads the database only -- spends no credit. */
export const listProductObservations = async (
  filters: { q?: string; market?: string; merchantId?: number; productStatus?: string } = {},
  signal?: AbortSignal,
): Promise<ProductObservationListResponse> => {
  const params = new URLSearchParams();
  if (filters.q) params.append('q', filters.q);
  if (filters.market) params.append('market', filters.market);
  if (filters.merchantId !== undefined) params.append('merchant_id', String(filters.merchantId));
  if (filters.productStatus) params.append('product_status', filters.productStatus);

  const suffix = params.toString() ? `?${params.toString()}` : '';
  const response = await api.get<ProductObservationListResponse>(
    `/products${suffix}`, { signal });
  return response.data;
};

/** One saved observation with its full evidence. */
export const getProductObservation = async (
  id: number,
  signal?: AbortSignal,
): Promise<ProductObservationRecord> => {
  const response = await api.get<ProductObservationRecord>(`/products/${id}`, { signal });
  return response.data;
};
