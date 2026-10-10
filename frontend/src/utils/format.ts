import { isAxiosError } from 'axios';

/**
 * A price with its currency. When the currency is unknown the bare number is
 * shown -- never a "$" that the evidence did not establish.
 */
export const formatMoney = (value: number | null | undefined, currency?: string | null): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  if (currency && /^[A-Z]{3}$/.test(currency)) {
    try {
      return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value);
    } catch {
      // An unrecognised code falls through to the plain form below.
    }
  }
  return value.toFixed(2) + (currency ? ` ${currency}` : '');
};

export const formatDate = (value: string | null | undefined): string =>
  value ? new Date(value).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  }) : '—';

export const formatDateTime = (value: string | null | undefined): string =>
  value ? new Date(value).toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  }) : '—';

export const formatPercent = (value: number | null | undefined, signed = true): string =>
  value === null || value === undefined ? '—'
    : `${signed && value > 0 ? '+' : ''}${value.toFixed(1)}%`;

/** snake_case backend labels as readable text. */
export const humanize = (value: string | null | undefined): string =>
  (value ?? '').replace(/_/g, ' ');

/**
 * A readable message for a failed request. The backend's `detail` is shown
 * when present; otherwise the status decides, so a provider failure (502) is
 * never presented as "nothing found" and a spent budget (429) is named.
 */
export const errorMessage = (err: unknown, fallback = 'Something went wrong. Try again in a moment.'): string => {
  if (!isAxiosError(err)) return fallback;
  if (!err.response) return 'The backend could not be reached. Is it running?';
  const detail = err.response.data?.detail;
  if (typeof detail === 'string' && detail) return detail;
  switch (err.response.status) {
    case 400: return 'That request is missing something it needs.';
    case 404: return 'That item no longer exists.';
    case 422: return 'That location could not be matched to a supported search location.';
    case 429: return 'The search budget is used up. Cached results remain available.';
    case 502: return 'The data provider did not respond. This is not the same as finding nothing.';
    case 503: return 'This feature needs an API key that is not configured.';
    default: return fallback;
  }
};

export const isCanceled = (err: unknown): boolean =>
  isAxiosError(err) && err.code === 'ERR_CANCELED';
