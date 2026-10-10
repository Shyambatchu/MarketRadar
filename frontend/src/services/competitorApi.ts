import api from './api';
import type {
  Competitor, CompetitorListResponse, CompetitorSearchResponse,
} from '../types/competitor';

export interface CompetitorSearchParams {
  market: string;
  query?: string;
  location?: string;
}

/**
 * Discover competitors for a market and place.
 *
 * Errors are meaningful and must not be flattened: 422 is a location with no
 * provider-supported equivalent, 502 is a provider failure, and a 200 with an
 * empty list means the search genuinely found nothing.
 */
export const searchCompetitors = async (
  { market, query, location }: CompetitorSearchParams,
  signal?: AbortSignal,
): Promise<CompetitorSearchResponse> => {
  const params = new URLSearchParams();
  if (market) params.append('market', market);
  if (query) params.append('q', query);
  if (location) params.append('location', location);

  const response = await api.get<CompetitorSearchResponse>(
    `/competitors/search?${params.toString()}`, { signal });
  return response.data;
};

/** Saved competitors. Reads the database only -- spends no credit. */
export const listCompetitors = async (
  filters: { market?: string; location?: string; status?: string; reviewStatus?: string } = {},
  signal?: AbortSignal,
): Promise<CompetitorListResponse> => {
  const params = new URLSearchParams();
  if (filters.market) params.append('market', filters.market);
  if (filters.location) params.append('location', filters.location);
  if (filters.status) params.append('status', filters.status);
  if (filters.reviewStatus) params.append('review_status', filters.reviewStatus);

  const suffix = params.toString() ? `?${params.toString()}` : '';
  const response = await api.get<CompetitorListResponse>(
    `/competitors${suffix}`, { signal });
  return response.data;
};

/** One competitor with its full discovery evidence. */
export const getCompetitor = async (
  id: number,
  signal?: AbortSignal,
): Promise<Competitor> => {
  const response = await api.get<Competitor>(`/competitors/${id}`, { signal });
  return response.data;
};

/**
 * Confirm, reject or rename a discovered business. A search result is never
 * proof of competition; this records the user's decision (audited). Pass
 * `review_status: 'unreviewed'` to clear it and an empty string to clear text.
 */
export const reviewCompetitor = async (
  id: number,
  update: { review_status?: 'confirmed' | 'rejected' | 'unreviewed'; display_name?: string; review_note?: string },
): Promise<Competitor> => {
  const response = await api.patch<Competitor>(`/competitors/${id}`, update);
  return response.data;
};
