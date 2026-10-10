import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Dashboard from './Dashboard';
import type { DashboardSummary } from '../../types/intelligence';

const getDashboard = vi.fn();
let failWith: Error | null = null;
vi.mock('../../services/intelligenceApi', () => ({
  // A failure is returned by a plain function, not the spy: vitest's spy
  // tracks returned promises and reports a rejection it tracked even when
  // the component handled it.
  getDashboard: (...args: unknown[]) => (failWith ? Promise.reject(failWith) : getDashboard(...args)),
}));
vi.mock('../../services/trendApi', () => ({
  getTrendSummary: () => Promise.resolve({
    generated_at: '', competitor_observations: 0, product_observations: 0,
    merchants_tracked: 0, verified_price_observations: 0, contexts: [],
    analyzable_contexts: 0, insufficient_history: true, detail: null,
  }),
}));
vi.mock('../../services/marketPulseApi', () => ({
  getMarketPulseOptions: () => Promise.resolve({ generated_at: '', total: 0, options: [], detail: null }),
}));

const summary: DashboardSummary = {
  generated_at: '2026-10-10T00:00:00Z',
  filters: { market: null, location: null, days: null },
  counts: {
    competitors: 3, businesses: 4, confirmed_competitors: 1, products_found: 5,
    verified_prices: 6, competitor_observations: 7, product_observations: 8, markets: 2,
  },
  freshness: {
    first_observed_at: '2026-09-01T00:00:00Z', last_observed_at: '2026-10-01T00:00:00Z',
    last_news_collected_at: null, last_search_interest_collected_at: null,
  },
  recent_changes: [{
    type: 'price_increase', severity: 'warning', confidence: 'high', product: 'Widget',
    merchant: 'Alpha', merchant_id: 1, market: 'Widgets', location: 'Austin', currency: 'EUR',
    previous_price: 10, current_price: 12, change_absolute: 2, change_percent: 20,
    previous_observed_at: null, observed_at: '2026-10-01T00:00:00Z', explanation: '',
    record_ids: [1, 2], source_urls: [],
  }],
  recent_changes_total: 1,
  top_opportunities: [],
  recent_reports: [],
  recent_searches: [],
  health: {
    serpapi_configured: true, ai_provider_configured: false, requests_last_7_days: 3,
    failed_requests_last_7_days: 0, credits_used_this_month: 3, monthly_budget: null,
    budget_remaining: null,
  },
};

const renderPage = () => render(<MemoryRouter><Dashboard /></MemoryRouter>);

describe('Dashboard', () => {
  beforeEach(() => { getDashboard.mockReset(); failWith = null; });

  it('shows real counts and recent changes from the API', async () => {
    getDashboard.mockResolvedValue(summary);
    renderPage();
    await waitFor(() => expect(screen.getByText('Businesses tracked')).toBeInTheDocument());
    expect(screen.getByText('1 confirmed as competitors')).toBeInTheDocument();
    expect(screen.getByText(/Widget · Alpha/)).toBeInTheDocument();
    expect(screen.getByText(/\+20\.0%/)).toBeInTheDocument();
    expect(screen.getByText('not configured (facts only)')).toBeInTheDocument();
    // Search-credit usage is not shown on the dashboard.
    expect(screen.queryByText(/credit/i)).not.toBeInTheDocument();
  });

  it('explains an empty opportunity list rather than inventing one', async () => {
    getDashboard.mockResolvedValue(summary);
    renderPage();
    await waitFor(() => expect(screen.getByText(/No opportunities yet/)).toBeInTheDocument());
  });

  it('reports a failed load', async () => {
    failWith = new Error('down');
    renderPage();
    await waitFor(() => expect(screen.getByText(/Something went wrong/)).toBeInTheDocument());
  });
});
