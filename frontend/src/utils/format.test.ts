import { describe, expect, it } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';
import { errorMessage, formatMoney, formatPercent, humanize } from './format';

const httpError = (status: number, detail?: string) => {
  const err = new AxiosError('failed');
  err.response = {
    status, statusText: '', headers: {}, config: { headers: new AxiosHeaders() },
    data: detail ? { detail } : {},
  };
  return err;
};

describe('formatMoney', () => {
  it('never invents a currency symbol', () => {
    expect(formatMoney(12.5, null)).toBe('12.50');
    expect(formatMoney(12.5, 'XYZ1')).toBe('12.50 XYZ1');
  });
  it('formats known ISO currencies', () => {
    expect(formatMoney(12.5, 'EUR')).toMatch(/12[.,]50/);
    expect(formatMoney(12.5, 'EUR')).toMatch(/€|EUR/);
  });
  it('renders missing values as a dash, not "$---"', () => {
    expect(formatMoney(null, 'USD')).toBe('—');
    expect(formatMoney(undefined)).toBe('—');
  });
});

describe('formatPercent and humanize', () => {
  it('signs positive changes', () => {
    expect(formatPercent(12.345)).toBe('+12.3%');
    expect(formatPercent(-4)).toBe('-4.0%');
    expect(formatPercent(null)).toBe('—');
  });
  it('humanizes snake_case labels', () => {
    expect(humanize('price_increase')).toBe('price increase');
  });
});

describe('errorMessage', () => {
  it('prefers the backend detail', () => {
    expect(errorMessage(httpError(400, 'Radius must be between 1 and 100 miles.')))
      .toBe('Radius must be between 1 and 100 miles.');
  });
  it('never reports a provider failure as an empty result', () => {
    expect(errorMessage(httpError(502))).toMatch(/not the same as finding nothing/);
  });
  it('names an exhausted budget', () => {
    expect(errorMessage(httpError(429))).toMatch(/budget/);
  });
  it('explains an unreachable backend', () => {
    expect(errorMessage(new AxiosError('Network Error'))).toMatch(/could not be reached/);
  });
});
