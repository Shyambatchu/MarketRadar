import api from './api';
import type { SerpSearchResponse, UsageStatsResponse } from '../types/serpapi';

export const searchOrganic = async (query: string, location?: string, signal?: AbortSignal): Promise<SerpSearchResponse> => {
  const params = new URLSearchParams();
  params.append('q', query);
  if (location) {
    params.append('location', location);
  }
  
  const response = await api.get<SerpSearchResponse>(`/serpapi/search?${params.toString()}`, { signal });
  return response.data;
};

export const getUsageStats = async (signal?: AbortSignal): Promise<UsageStatsResponse> => {
  const response = await api.get<UsageStatsResponse>(`/serpapi/usage`, { signal });
  return response.data;
};

export interface RecentSearch {
  id: number;
  query: string;
  location: string | null;
  searched_at: string;
  organic_count: number;
  local_count: number;
}

export const getRecentSearches = async (signal?: AbortSignal): Promise<RecentSearch[]> => {
  const response = await api.get<RecentSearch[]>('/serpapi/recent', { signal });
  return response.data;
};
