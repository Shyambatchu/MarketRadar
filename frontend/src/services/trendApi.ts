import api from './api';
import type {
  MerchantPresenceResponse, TrendListResponse, TrendSummaryResponse,
} from '../types/trend';

/**
 * Trends read the observation history that Competitors and Products already
 * recorded. No endpoint here makes a provider request, so none costs a SerpApi
 * credit, and none writes anything back.
 */

export const getTrendSummary = async (
  signal?: AbortSignal,
): Promise<TrendSummaryResponse> => {
  const response = await api.get<TrendSummaryResponse>('/trends/summary', { signal });
  return response.data;
};

export const getPriceTrends = async (
  filters: { q?: string; market?: string } = {},
  signal?: AbortSignal,
): Promise<TrendListResponse> => {
  const params = new URLSearchParams();
  if (filters.q) params.append('q', filters.q);
  if (filters.market) params.append('market', filters.market);
  const suffix = params.toString() ? `?${params.toString()}` : '';

  const response = await api.get<TrendListResponse>(`/trends/prices${suffix}`, { signal });
  return response.data;
};

export const getAvailabilityTrends = async (
  filters: { q?: string } = {},
  signal?: AbortSignal,
): Promise<TrendListResponse> => {
  const params = new URLSearchParams();
  if (filters.q) params.append('q', filters.q);
  const suffix = params.toString() ? `?${params.toString()}` : '';

  const response = await api.get<TrendListResponse>(`/trends/availability${suffix}`, { signal });
  return response.data;
};

export const getVisibilityTrends = async (
  filters: { market?: string; metric?: string } = {},
  signal?: AbortSignal,
): Promise<TrendListResponse> => {
  const params = new URLSearchParams();
  if (filters.market) params.append('market', filters.market);
  if (filters.metric) params.append('metric', filters.metric);
  const suffix = params.toString() ? `?${params.toString()}` : '';

  const response = await api.get<TrendListResponse>(`/trends/visibility${suffix}`, { signal });
  return response.data;
};

export const getMerchantPresence = async (
  filters: { market?: string; location?: string } = {},
  signal?: AbortSignal,
): Promise<MerchantPresenceResponse> => {
  const params = new URLSearchParams();
  if (filters.market) params.append('market', filters.market);
  if (filters.location) params.append('location', filters.location);
  const suffix = params.toString() ? `?${params.toString()}` : '';

  const response = await api.get<MerchantPresenceResponse>(`/trends/merchants${suffix}`, { signal });
  return response.data;
};
