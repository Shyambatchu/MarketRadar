import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Competitors from './Competitors';
import type { Competitor } from '../../types/competitor';

const listCompetitors = vi.fn();
// Failures bypass the spy: vitest reports a rejection its spy tracked even when handled.
let listFailure: Error | null = null;
const reviewCompetitor = vi.fn();
vi.mock('../../services/competitorApi', () => ({
  listCompetitors: (...a: unknown[]) => (listFailure ? Promise.reject(listFailure) : listCompetitors(...a)),
  reviewCompetitor: (...a: unknown[]) => reviewCompetitor(...a),
  getCompetitor: (id: number) => Promise.resolve(rows.find((r) => r.id === id)),
  searchCompetitors: vi.fn(),
}));
vi.mock('../../services/intelligenceApi', () => ({
  exportUrl: () => 'http://api/export/competitors.csv',
  saveSearch: vi.fn(),
}));

const make = (id: number, name: string, extra: Partial<Competitor> = {}): Competitor => ({
  id, name, normalized_name: name.toLowerCase(), domain: `${name.toLowerCase().replace(/\s/g, '')}.example`,
  website: null, address: '1 Main St', city: null, state: null, country: null,
  latitude: null, longitude: null, place_id: null, status: 'verified', entity_type: 'business',
  match_method: 'new', match_confidence: 'high', status_reason: null, rating: 4.5, reviews: 20,
  best_position: id, market: 'Coffee', location_requested: 'X', location_resolved: 'X',
  markets: ['Coffee'], locations: ['X'], discovery_sources: ['local'],
  discovery_methods: ['google_maps_local'], has_location_evidence: true,
  first_seen_at: '2026-09-01T00:00:00Z', last_seen_at: '2026-09-0' + id + 'T00:00:00Z',
  evidence_count: 1, evidence: [], review_status: null, display_name: null,
  review_note: null, reviewed_at: null, ...extra,
});

let rows: Competitor[] = [];

const renderPage = () => render(<MemoryRouter><Competitors /></MemoryRouter>);

describe('Competitors', () => {
  beforeEach(() => {
    rows = [
      make(1, 'Alpha Roasters'),
      make(2, 'Beta Beans', { review_status: 'confirmed', markets: ['Coffee', 'Tea'] }),
      make(3, 'Gamma Cafe', { status: 'discovered', rating: null, reviews: null, has_location_evidence: false }),
    ];
    listFailure = null;
    listCompetitors.mockReset();
    reviewCompetitor.mockReset();
    listCompetitors.mockResolvedValue({ total: rows.length, competitors: rows });
  });

  it('shows saved competitors as cards with a summary', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Alpha Roasters')).toBeInTheDocument());
    expect(screen.getByText('Beta Beans')).toBeInTheDocument();
    expect(screen.getByText('Awaiting review')).toBeInTheDocument();
    expect(screen.getByText('Location not verified')).toBeInTheDocument();
    expect(screen.getByText('3 of 3 shown')).toBeInTheDocument();
  });

  it('filters by text and by review status', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Alpha Roasters')).toBeInTheDocument());
    fireEvent.change(screen.getByPlaceholderText(/Search by name/), { target: { value: 'gamma' } });
    expect(screen.queryByText('Alpha Roasters')).not.toBeInTheDocument();
    expect(screen.getByText('Gamma Cafe')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /clear filters/i }));
    fireEvent.click(screen.getByText('Confirmed · 1'));
    expect(screen.getByText('Beta Beans')).toBeInTheDocument();
    expect(screen.queryByText('Alpha Roasters')).not.toBeInTheDocument();
  });

  it('records a review from a card and updates it in place', async () => {
    reviewCompetitor.mockResolvedValue({ ...rows[0], review_status: 'confirmed', reviewed_at: '2026-10-10T00:00:00Z' });
    renderPage();
    await waitFor(() => expect(screen.getByText('Alpha Roasters')).toBeInTheDocument());
    const card = screen.getByText('Alpha Roasters').closest('.MuiCard-root') as HTMLElement;
    fireEvent.click(within(card).getByRole('button', { name: 'Confirm' }));
    await waitFor(() => expect(reviewCompetitor).toHaveBeenCalledWith(1, { review_status: 'confirmed' }));
    await waitFor(() => expect(within(card).getByText('Confirmed')).toBeInTheDocument());
  });

  it('switches to a compact table and opens details from a row', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Alpha Roasters')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Table view' }));
    expect(screen.getByRole('table')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Gamma Cafe'));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Close details' })).toBeInTheDocument());
    expect(screen.getByText('At a glance')).toBeInTheDocument();
  });

  it('shows an error with retry when the list fails', async () => {
    listFailure = new Error('down');
    renderPage();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument());
  });
});
