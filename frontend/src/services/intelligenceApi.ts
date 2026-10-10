import api from './api';
import type {
  DashboardSummary, InterestByRegion, InterestOverTime, NewsArticle,
  NewsSearchResponse, Opportunity, OpportunityListResponse, OpportunitySources, OpportunityStatus,
  PriceAlertResponse, RelatedQueries, ReportSummary, SavedSearch, ScoringMethod,
  UsageBreakdown,
} from '../types/intelligence';

const query = (params: Record<string, string | number | undefined | null>): string => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== '') {
      search.append(key, String(value));
    }
  });
  const text = search.toString();
  return text ? `?${text}` : '';
};

// ---------------------------------------------------------------- free reads
/** Executive summary of stored evidence. No provider request. */
export const getDashboard = async (
  filters: { market?: string; location?: string; days?: number } = {},
  signal?: AbortSignal,
): Promise<DashboardSummary> =>
  (await api.get<DashboardSummary>(`/dashboard${query(filters)}`, { signal })).data;

/** Detected price changes over stored verified prices. No provider request. */
export const getPriceAlerts = async (
  filters: { q?: string; market?: string; location?: string; min_change_percent?: number } = {},
  signal?: AbortSignal,
): Promise<PriceAlertResponse> =>
  (await api.get<PriceAlertResponse>(`/prices/alerts${query(filters)}`, { signal })).data;

export const getUsageBreakdown = async (signal?: AbortSignal): Promise<UsageBreakdown> =>
  (await api.get<UsageBreakdown>('/serpapi/usage/breakdown', { signal })).data;

// ---------------------------------------------------------------- opportunities
export const getScoringMethod = async (signal?: AbortSignal): Promise<ScoringMethod> =>
  (await api.get<ScoringMethod>('/opportunities/method', { signal })).data;

/** Evidence available to each opportunity source. Free. */
export const getOpportunitySources = async (
  filters: { market?: string; location?: string } = {}, signal?: AbortSignal,
): Promise<OpportunitySources> =>
  (await api.get<OpportunitySources>(`/opportunities/sources${query(filters)}`, { signal })).data;

export const listOpportunities = async (
  filters: { status?: OpportunityStatus; market?: string; location?: string; min_score?: number } = {},
  signal?: AbortSignal,
): Promise<OpportunityListResponse> =>
  (await api.get<OpportunityListResponse>(`/opportunities${query(filters)}`, { signal })).data;

/** Rebuild opportunities from current evidence. Review statuses are kept. */
export const refreshOpportunities = async (
  filters: { market?: string; location?: string } = {},
): Promise<OpportunityListResponse> =>
  (await api.post<OpportunityListResponse>(`/opportunities/refresh${query(filters)}`)).data;

export const updateOpportunity = async (
  id: number, update: { status?: OpportunityStatus; note?: string },
): Promise<Opportunity> =>
  (await api.patch<Opportunity>(`/opportunities/${id}`, update)).data;

// ---------------------------------------------------------------- reports
export const listReports = async (signal?: AbortSignal): Promise<{ total: number; reports: ReportSummary[] }> =>
  (await api.get<{ total: number; reports: ReportSummary[] }>('/reports', { signal })).data;

export const createReport = async (
  request: { market?: string | null; location?: string | null; title?: string },
): Promise<ReportSummary> => (await api.post<ReportSummary>('/reports', request)).data;

export const deleteReport = async (id: number): Promise<void> => {
  await api.delete(`/reports/${id}`);
};

/** Absolute URL of a print-ready report (opened in a new tab). */
export const reportUrl = (id: number): string => `${api.defaults.baseURL}/reports/${id}.html`;

// ---------------------------------------------------------------- saved searches
export const listSavedSearches = async (
  module?: SavedSearch['module'], signal?: AbortSignal,
): Promise<{ total: number; saved_searches: SavedSearch[] }> =>
  (await api.get<{ total: number; saved_searches: SavedSearch[] }>(
    `/saved-searches${query({ module })}`, { signal })).data;

export const saveSearch = async (
  request: { module: SavedSearch['module']; query: string; market?: string; location?: string; label?: string },
): Promise<{ id: number; created: boolean }> =>
  (await api.post<{ id: number; created: boolean }>('/saved-searches', request)).data;

export const deleteSavedSearch = async (id: number): Promise<void> => {
  await api.delete(`/saved-searches/${id}`);
};

// ---------------------------------------------------------------- market signals
// Live endpoints: one SerpApi credit per uncached request.
export const getSearchInterest = async (
  params: { q: string; geo?: string; date?: string }, signal?: AbortSignal,
): Promise<InterestOverTime> =>
  (await api.get<InterestOverTime>(`/signals/search-interest${query(params)}`, { signal })).data;

export const getInterestByRegion = async (
  params: { q: string; geo?: string; date?: string; region?: string }, signal?: AbortSignal,
): Promise<InterestByRegion> =>
  (await api.get<InterestByRegion>(`/signals/search-interest/regions${query(params)}`, { signal })).data;

export const getRelatedQueries = async (
  params: { q: string; geo?: string; date?: string }, signal?: AbortSignal,
): Promise<RelatedQueries> =>
  (await api.get<RelatedQueries>(`/signals/search-interest/related${query(params)}`, { signal })).data;

export const searchNews = async (
  params: { q: string; gl?: string; hl?: string; sort?: 'relevance' | 'date' }, signal?: AbortSignal,
): Promise<NewsSearchResponse> =>
  (await api.get<NewsSearchResponse>(`/signals/news${query(params)}`, { signal })).data;

/** Collected news. No provider request. */
export const listSavedNews = async (
  q?: string, signal?: AbortSignal,
): Promise<{ total: number; articles: NewsArticle[] }> =>
  (await api.get<{ total: number; articles: NewsArticle[] }>(
    `/signals/news/saved${query({ q })}`, { signal })).data;

// ---------------------------------------------------------------- exports
/** Absolute URL of a CSV export. Opening it downloads the file. */
export const exportUrl = (
  dataset: 'competitors' | 'products' | 'prices' | 'price-alerts' | 'trends' | 'opportunities',
  params: Record<string, string | number | undefined | null> = {},
): string => `${api.defaults.baseURL}/export/${dataset}.csv${query(params)}`;
