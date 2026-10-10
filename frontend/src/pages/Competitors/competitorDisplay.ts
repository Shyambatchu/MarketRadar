import type { Competitor } from '../../types/competitor';

/**
 * Status colours describe evidence strength, never business quality.
 * "uncertain" means we could not identify the business reliably -- it does not
 * mean the business is unimportant.
 */
export const STATUS_COLOR: Record<string, 'success' | 'info' | 'warning' | 'default'> = {
  verified: 'success',
  discovered: 'info',
  uncertain: 'warning',
  rejected: 'default',
};

export const STATUS_LABEL: Record<string, string> = {
  verified: 'Verified identity',
  discovered: 'Discovered',
  uncertain: 'Uncertain identity',
  rejected: 'Not a competitor',
};

export const STATUS_HELP: Record<string, string> = {
  verified: 'Identified from a structured local listing, or corroborated by two independent sources.',
  discovered: 'A real business, but the evidence so far is a single organic result.',
  uncertain: 'The evidence could not reliably distinguish this business from another.',
  rejected: 'Not presented as a competitor.',
};

/** Human names for the discovery methods the backend records. */
export const SOURCE_LABEL: Record<string, string> = {
  google_maps_local: 'Google Local',
  google_organic: 'Google Organic',
  merchant_website: 'Merchant Website',
};

/** The discovery source, derived from the methods actually recorded. */
export const sourceLabel = (competitor: Competitor): string => {
  const labels = competitor.discovery_methods
    .map((m) => SOURCE_LABEL[m] ?? m.replace(/_/g, ' '));
  if (labels.length === 0) return 'Not recorded';
  if (labels.length === 1) return labels[0];
  // "Google Local + Organic" reads better than repeating the provider.
  if (labels.every((l) => l.startsWith('Google '))) {
    return `Google ${labels.map((l) => l.replace('Google ', '')).join(' + ')}`;
  }
  return labels.join(' + ');
};

export const displayName = (c: Competitor): string => c.display_name || c.name;

export const initials = (name: string): string => {
  const words = name.replace(/[^\p{L}\p{N}\s]/gu, ' ').split(/\s+/).filter(Boolean);
  return ((words[0]?.[0] ?? '?') + (words[1]?.[0] ?? '')).toUpperCase();
};

// A stable colour per business, so the same company is recognisable across
// views. Purely decorative: it encodes nothing about the business.
const AVATAR_COLORS = ['#4F46E5', '#0891B2', '#059669', '#D97706', '#DB2777', '#7C3AED', '#2563EB', '#65A30D'];
export const avatarColor = (seed: string): string => {
  let hash = 0;
  for (const ch of seed) hash = (hash * 31 + ch.charCodeAt(0)) | 0;
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
};

export const locationText = (c: Competitor): string | null =>
  c.has_location_evidence
    ? (c.address || [c.city, c.state, c.country].filter(Boolean).join(', ') || null)
    : null;

export type ReviewFilter = 'all' | 'unreviewed' | 'confirmed' | 'rejected';
export type SortKey = 'recent' | 'name' | 'rating' | 'evidence' | 'position';

export const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'recent', label: 'Recently seen' },
  { value: 'name', label: 'Name (A–Z)' },
  { value: 'rating', label: 'Highest rated' },
  { value: 'evidence', label: 'Most evidence' },
  { value: 'position', label: 'Best search position' },
];

export const matchesReview = (c: Competitor, filter: ReviewFilter): boolean =>
  filter === 'all'
  || (filter === 'unreviewed' ? c.review_status === null : c.review_status === filter);

export const matchesText = (c: Competitor, text: string): boolean => {
  const needle = text.trim().toLowerCase();
  if (!needle) return true;
  return [c.name, c.display_name, c.domain, c.address, ...c.markets, ...c.locations]
    .some((v) => v && v.toLowerCase().includes(needle));
};

const time = (v: string | null) => (v ? new Date(v).getTime() : 0);

export const sortCompetitors = (rows: Competitor[], key: SortKey): Competitor[] => {
  const copy = [...rows];
  switch (key) {
    case 'name':
      return copy.sort((a, b) => displayName(a).localeCompare(displayName(b)));
    case 'rating':
      // Unrated businesses go last rather than being treated as zero stars.
      return copy.sort((a, b) => (b.rating ?? -1) - (a.rating ?? -1)
        || (b.reviews ?? 0) - (a.reviews ?? 0));
    case 'evidence':
      return copy.sort((a, b) => b.evidence_count - a.evidence_count);
    case 'position':
      return copy.sort((a, b) => (a.best_position ?? 9999) - (b.best_position ?? 9999));
    default:
      return copy.sort((a, b) => time(b.last_seen_at) - time(a.last_seen_at));
  }
};

/** Copy only the review fields onto a row, keeping whatever else it carries. */
export const withReview = (row: Competitor, updated: Competitor): Competitor => ({
  ...row,
  review_status: updated.review_status,
  display_name: updated.display_name,
  review_note: updated.review_note,
  reviewed_at: updated.reviewed_at,
});
