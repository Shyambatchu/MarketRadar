import api from './api';
import type { AnalystResponse } from '../types/analyst';

/**
 * The AI Analyst reads a Market Pulse snapshot. It makes no provider search,
 * so it costs no SerpApi credit, and it writes nothing back.
 *
 * `include_summary: false` skips the AI provider entirely and returns the
 * deterministic factual analysis alone.
 */
export const getAnalysis = async (
  filters: { market?: string; location?: string; includeSummary?: boolean } = {},
  signal?: AbortSignal,
): Promise<AnalystResponse> => {
  const params = new URLSearchParams();
  if (filters.market) params.append('market', filters.market);
  if (filters.location) params.append('location', filters.location);
  if (filters.includeSummary === false) params.append('include_summary', 'false');
  const suffix = params.toString() ? `?${params.toString()}` : '';

  const response = await api.get<AnalystResponse>(`/analyst/analysis${suffix}`, { signal });
  return response.data;
};
