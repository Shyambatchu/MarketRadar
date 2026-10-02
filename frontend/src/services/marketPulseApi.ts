import api from './api';
import type {
  MarketPulseOptionsResponse, MarketPulseResponse,
} from '../types/marketPulse';

/**
 * Market Pulse reads the observation history that Competitors and Products
 * already recorded. Neither endpoint makes a provider request, so neither
 * costs a SerpApi credit, and neither writes anything back.
 */

/** Markets and locations this installation has actually observed. */
export const getMarketPulseOptions = async (
  signal?: AbortSignal,
): Promise<MarketPulseOptionsResponse> => {
  const response = await api.get<MarketPulseOptionsResponse>(
    '/market-pulse/options', { signal });
  return response.data;
};

/** A factual snapshot of one market and location. */
export const getMarketPulse = async (
  filters: { market?: string; location?: string } = {},
  signal?: AbortSignal,
): Promise<MarketPulseResponse> => {
  const params = new URLSearchParams();
  if (filters.market) params.append('market', filters.market);
  if (filters.location) params.append('location', filters.location);
  const suffix = params.toString() ? `?${params.toString()}` : '';

  const response = await api.get<MarketPulseResponse>(
    `/market-pulse${suffix}`, { signal });
  return response.data;
};
