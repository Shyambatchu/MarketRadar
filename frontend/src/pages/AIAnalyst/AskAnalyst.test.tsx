import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AskAnalyst from './AskAnalyst';
import type { AnalystAnswer } from '../../types/analyst';

const askAnalyst = vi.fn();
let failWith: Error | null = null;
vi.mock('../../services/analystApi', () => ({
  // A failure is returned by a plain function, not the spy: vitest's spy
  // tracks returned promises and reports a rejection it tracked even when
  // the component handled it.
  askAnalyst: (...args: unknown[]) => (failWith ? Promise.reject(failWith) : askAnalyst(...args)),
}));

const base: AnalystAnswer = {
  generated_at: '2026-10-01T00:00:00Z', question: 'What changed?',
  context: {
    market: 'Widgets', location: 'Austin', first_observed_at: null, last_observed_at: null,
    observation_span_hours: null, distinct_searches: 2, merchants: 2,
    competitor_observations: 2, product_observations: 4,
  },
  mode: 'deterministic', provider_configured: false, provider_name: null, answer: null,
  facts: [], interpretations: [], hypotheses: [], missing_data: [], confidence: null,
  relevant_evidence: ['F2'],
  evidence: [
    { id: 'F1', kind: 'observation', section: 'prices', statement: 'Two merchants were priced.',
      source_urls: [], observed_at: null, record_ids: [1] },
    { id: 'F2', kind: 'price_alert', section: 'price_alerts', statement: 'Price rose 20% at Alpha.',
      source_urls: ['https://alpha.example/p'], observed_at: '2026-09-30T00:00:00Z', record_ids: [3, 4] },
  ],
  answer_rejected: false, rejection_reason: null, provider_error: null,
  detail: 'No AI provider is configured.',
};

describe('AskAnalyst', () => {
  beforeEach(() => { askAnalyst.mockReset(); failWith = null; });

  it('is disabled until a market is selected', () => {
    render(<AskAnalyst market={null} location={null} disabled />);
    expect(screen.getByRole('button', { name: /^ask$/i })).toBeDisabled();
  });

  it('shows relevant evidence with sources when no provider is configured', async () => {
    askAnalyst.mockResolvedValue(base);
    render(<AskAnalyst market="Widgets" location="Austin" disabled={false} />);
    fireEvent.change(screen.getByLabelText('Your question'), { target: { value: 'What changed?' } });
    fireEvent.click(screen.getByRole('button', { name: /^ask$/i }));
    await waitFor(() => expect(screen.getByText('Price rose 20% at Alpha.')).toBeInTheDocument());
    expect(askAnalyst).toHaveBeenCalledWith({ question: 'What changed?', market: 'Widgets', location: 'Austin' });
    expect(screen.getByText('Evidence only (no written answer)')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'alpha.example' })).toHaveAttribute('href', 'https://alpha.example/p');
    // F1 was not relevant, so it stays hidden until asked for.
    expect(screen.queryByText('Two merchants were priced.')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /show all evidence/i }));
    expect(screen.getByText('Two merchants were priced.')).toBeInTheDocument();
  });

  it('renders an assisted answer with clickable citations', async () => {
    askAnalyst.mockResolvedValue({
      ...base, mode: 'assisted', provider_configured: true, provider_name: 'anthropic',
      answer: 'Alpha raised its price.', confidence: 'medium', detail: null,
      facts: [{ statement: 'Alpha raised its price by 20%.', citations: ['F2'] }],
      hypotheses: [{ statement: 'Check whether the size changed.', citations: ['F2'] }],
    });
    render(<AskAnalyst market="Widgets" location="Austin" disabled={false} />);
    fireEvent.click(screen.getByText('Which products have unusual price differences?'));
    await waitFor(() => expect(screen.getByText('Alpha raised its price.')).toBeInTheDocument());
    expect(screen.getByText('Hypotheses to investigate')).toBeInTheDocument();
    expect(screen.getAllByText('F2').length).toBeGreaterThan(1);
  });

  it('explains a withheld answer', async () => {
    askAnalyst.mockResolvedValue({
      ...base, answer_rejected: true,
      rejection_reason: 'The answer cited a figure that does not appear in the evidence.',
    });
    render(<AskAnalyst market="Widgets" location="Austin" disabled={false} />);
    fireEvent.click(screen.getByText('What changed in this market during the selected period?'));
    await waitFor(() => expect(screen.getByText(/written answer was withheld/)).toBeInTheDocument());
  });

  it('reports a failed request', async () => {
    failWith = new Error('boom');
    render(<AskAnalyst market="Widgets" location="Austin" disabled={false} />);
    fireEvent.click(screen.getByText('What changed in this market during the selected period?'));
    await waitFor(() => expect(screen.getByText('The question could not be answered.')).toBeInTheDocument());
  });
});
