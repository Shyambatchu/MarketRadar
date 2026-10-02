import { useState, useEffect, useRef } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogContent,
  DialogTitle, Divider, Grid, IconButton, Link, Paper, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, TextField, Tooltip,
  Typography,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import CloseIcon from '@mui/icons-material/Close';
import StorefrontOutlinedIcon from '@mui/icons-material/StorefrontOutlined';
import { isAxiosError } from 'axios';

import PageHeader from '../../components/PageHeader/PageHeader';
import EmptyState from '../../components/EmptyState/EmptyState';
import {
  getCompetitor, listCompetitors, searchCompetitors,
} from '../../services/competitorApi';
import type {
  Competitor, CompetitorSearchResponse,
} from '../../types/competitor';

/**
 * Status colours describe evidence strength, never business quality.
 * "uncertain" means we could not identify the business reliably -- it does not
 * mean the business is unimportant.
 */
const STATUS_COLOR: Record<string, 'success' | 'info' | 'warning' | 'default'> = {
  verified: 'success',
  discovered: 'info',
  uncertain: 'warning',
  rejected: 'default',
};

const STATUS_HELP: Record<string, string> = {
  verified: 'Identified from a structured local listing, or corroborated by two independent sources.',
  discovered: 'A real business, but the evidence so far is a single organic result.',
  uncertain: 'The evidence could not reliably distinguish this business from another.',
  rejected: 'Not presented as a competitor.',
};

/** Human names for the discovery methods the backend records. */
const SOURCE_LABEL: Record<string, string> = {
  google_maps_local: 'Google Local',
  google_organic: 'Google Organic',
  merchant_website: 'Merchant Website',
};

/**
 * The discovery source, derived from the methods actually recorded.
 * Never a persistence state: "saved" is not a source.
 */
const sourceLabel = (competitor: Competitor): string => {
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

const formatDate = (value: string | null): string =>
  value ? new Date(value).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  }) : '—';

const Competitors = () => {
  const [market, setMarket] = useState('');
  const [location, setLocation] = useState('');
  const [query, setQuery] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CompetitorSearchResponse | null>(null);
  const [saved, setSaved] = useState<Competitor[]>([]);
  const [savedTotal, setSavedTotal] = useState(0);
  // A failed load is reported, never shown as an empty history.
  const [savedError, setSavedError] = useState<string | null>(null);
  const [detail, setDetail] = useState<Competitor | null>(null);
  const [marketFilter, setMarketFilter] = useState<string | null>(null);

  const isSearching = useRef(false);

  // Saved competitors are shown before any search, so the page is useful on
  // arrival without spending a credit.
  useEffect(() => {
    const controller = new AbortController();
    listCompetitors({}, controller.signal)
      .then((data) => { setSaved(data.competitors); setSavedTotal(data.total); })
      .catch((err) => {
        if (!isAxiosError(err) || err.code !== 'ERR_CANCELED') {
          setSavedError(isAxiosError(err) && !err.response
            ? 'Saved competitors could not be loaded. Is the backend running?'
            : 'Saved competitors could not be loaded.');
        }
      });
    return () => controller.abort();
  }, []);

  const handleSearch = async () => {
    // A location is required: discovery finds businesses in a market *and* a
    // place, and an unscoped search returns unrelated results that would be
    // persisted as competitors.
    if ((!market.trim() && !query.trim()) || !location.trim() || isSearching.current) return;
    isSearching.current = true;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await searchCompetitors({
        market: market.trim(), query: query.trim(), location: location.trim(),
      });
      setResult(data);
      try {
        const list = await listCompetitors({});
        setSaved(list.competitors);
      } catch {
        // Refreshing the saved list is cosmetic; the search result stands.
      }
    } catch (err) {
      if (isAxiosError(err)) {
        const detailMessage = err.response?.data?.detail;
        // Each of these means something different and must not be collapsed
        // into "no competitors found".
        if (err.response?.status === 400) {
          setError(detailMessage || 'That search is missing something it needs. Provide a market or query and a location.');
        } else if (err.response?.status === 422) {
          setError(detailMessage || 'That location could not be matched to a supported search location.');
        } else if (err.response?.status === 502) {
          setError(detailMessage || 'The search provider did not respond, so no competitors could be discovered. This is not the same as finding none.');
        } else if (err.response?.status === 503) {
          setError(detailMessage || 'Competitor discovery is not configured yet.');
        } else {
          setError(detailMessage || 'Unable to discover competitors. Try again in a moment.');
        }
      } else {
        setError('An unexpected error occurred.');
      }
    } finally {
      setLoading(false);
      isSearching.current = false;
    }
  };

  const openDetail = async (competitor: Competitor) => {
    if (competitor.id === null) {
      setDetail(competitor);
      return;
    }
    try {
      setDetail(await getCompetitor(competitor.id));
    } catch {
      // Fall back to what the search already returned.
      setDetail(competitor);
    }
  };

  const showingSaved = !result;
  // Every market the saved list touches, so a mixed list can be scoped.
  const savedMarkets = Array.from(
    new Set(saved.flatMap((c) => c.markets))).sort();
  const rows = result
    ? result.competitors
    : (marketFilter === null
      ? saved
      : saved.filter((c) => c.markets.includes(marketFilter)));
  const problemStages = result
    ? result.stages.filter((s) => s.status === 'error' || s.status === 'degraded')
    : [];

  return (
    <Box>
      <PageHeader
        title="Competitors"
        subtitle="Discover and analyze businesses competing in a selected market and location."
      />

      <Paper sx={{ p: 3, mb: 4 }}>
        <Grid container spacing={2} sx={{ alignItems: 'center' }}>
          <Grid size={{ xs: 12, sm: 3 }}>
            <TextField
              fullWidth size="small" label="Market / Industry"
              placeholder="e.g. Coffee Shops"
              value={market} onChange={(e) => setMarket(e.target.value)}
              disabled={loading}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 3 }}>
            <TextField
              fullWidth size="small" label="Location" required
              placeholder="e.g. Austin, Texas"
              value={location} onChange={(e) => setLocation(e.target.value)}
              disabled={loading}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              fullWidth size="small" label="Search Query"
              placeholder="Defaults to the market when left blank"
              value={query} onChange={(e) => setQuery(e.target.value)}
              disabled={loading}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 2 }}>
            <Button
              fullWidth variant="contained" sx={{ height: 40 }}
              startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SearchIcon />}
              onClick={handleSearch}
              disabled={loading || (!market.trim() && !query.trim()) || !location.trim()}
            >
              Search
            </Button>
          </Grid>
        </Grid>

        {result && (
          <Box sx={{ mt: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            {result.location_resolved &&
              result.location_resolved !== result.location_requested && (
                <Typography variant="caption" color="text.secondary">
                  Location resolved to {result.location_resolved}
                </Typography>
              )}
            {result.cache_hit && (
              <Chip size="small" label="Cached result" color="success" variant="outlined" />
            )}
          </Box>
        )}
      </Paper>

      {problemStages.map((s) => (
        <Alert key={s.stage} severity={s.status === 'error' ? 'error' : 'warning'} sx={{ mb: 2 }}>
          {s.stage.replace(/_/g, ' ')}: {s.status}
          {s.detail ? ` — ${s.detail}` : ''}
        </Alert>
      ))}

      {error && <Alert severity="error" sx={{ mb: 4 }}>{error}</Alert>}

      {result && (
        <Paper variant="outlined" elevation={0} sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1.5 }}>Discovery funnel</Typography>
          <Grid container spacing={2}>
            {[
              ['Local results', result.local_results_found],
              ['Organic results', result.organic_results_found],
              ['Business candidates', result.business_candidates],
              ['Not a business', result.rejected_non_business],
              ['Duplicates merged', result.duplicates_merged],
              ['Verified', result.competitors_verified],
              ['Discovered', result.competitors_discovered],
              ['Uncertain', result.competitors_uncertain],
              ['New this search', result.new_competitors],
            ].map(([label, value]) => (
              <Grid size={{ xs: 6, sm: 4, md: 'grow' }} key={label as string}>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  {label}
                </Typography>
                <Typography variant="h6">{value}</Typography>
              </Grid>
            ))}
          </Grid>
        </Paper>
      )}

      {showingSaved && savedError ? (
        <Alert severity="error">{savedError}</Alert>
      ) : rows.length === 0 ? (
        <EmptyState
          title={showingSaved
            ? 'No competitors discovered yet'
            : 'No competitor businesses were found for this search'}
          description={showingSaved
            ? 'Enter a market or industry and a location above to discover competing businesses.'
            : result && result.rejected_non_business > 0
              ? `The search returned ${result.local_results_found + result.organic_results_found} results, but none of them identified a business. ${result.rejected_non_business} were directories, articles, marketplaces or social profiles.`
              : 'The search ran successfully and returned no businesses for this market and location.'}
          icon={<StorefrontOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
        />
      ) : (
        <>
          <Box sx={{ mb: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <Typography variant="h6">
              {showingSaved
                ? `Saved competitors (${savedTotal > saved.length
                  ? `showing ${saved.length} of ${savedTotal}` : saved.length})`
                : `Competitors (${rows.length})`}
            </Typography>
            {/* A saved list spans every search ever run, so it needs scoping.
                Filtering is client-side over rows already loaded; the backend
                also accepts ?market= for the same thing. */}
            {showingSaved && savedMarkets.length > 1 && (
              <>
                <Chip size="small" label="All markets"
                      color={marketFilter === null ? 'primary' : 'default'}
                      variant={marketFilter === null ? 'filled' : 'outlined'}
                      onClick={() => setMarketFilter(null)} />
                {savedMarkets.map((m) => (
                  <Chip key={m} size="small" label={m}
                        color={marketFilter === m ? 'primary' : 'default'}
                        variant={marketFilter === m ? 'filled' : 'outlined'}
                        onClick={() => setMarketFilter(m)} />
                ))}
              </>
            )}
          </Box>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Business</TableCell>
                  <TableCell>Domain</TableCell>
                  <TableCell>Discovery context</TableCell>
                  <TableCell>Location</TableCell>
                  <TableCell>Source</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Evidence</TableCell>
                  <TableCell>Observed</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((c, i) => (
                  <TableRow key={c.id ?? i} hover>
                    <TableCell>
                      <Typography variant="subtitle2">{c.name}</Typography>
                      {c.rating !== null && (
                        <Typography variant="caption" color="text.secondary">
                          {c.rating}★{c.reviews !== null ? ` · ${c.reviews} reviews` : ''}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      {/* Identity only. A social or marketplace URL is evidence
                          the business exists, not a domain it owns, so it is
                          never shown here -- it appears under Details. */}
                      {c.domain ? (
                        <Link href={c.website ?? `https://${c.domain}`}
                              target="_blank" rel="noopener" underline="hover">
                          {c.domain}
                        </Link>
                      ) : (
                        <Tooltip title={c.website
                          ? 'No website of its own was reported. A linked page on another platform is recorded as evidence instead — see Details.'
                          : 'No website was reported for this business.'}>
                          <Typography variant="caption" color="text.disabled">
                            Not reported
                          </Typography>
                        </Tooltip>
                      )}
                    </TableCell>
                    <TableCell>
                      {c.markets.length > 0 ? (
                        <>
                          <Typography variant="body2">{c.markets.join(', ')}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {c.locations.join(', ') || 'No location recorded'}
                          </Typography>
                        </>
                      ) : (
                        <Typography variant="caption" color="text.disabled">—</Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      {c.has_location_evidence ? (
                        <Typography variant="body2" color="text.secondary">
                          {c.address || [c.city, c.state, c.country].filter(Boolean).join(', ')}
                        </Typography>
                      ) : (
                        <Tooltip title="No provider returned an address or coordinates for this business, so its location could not be confirmed. Nothing is inferred from the domain.">
                          <Typography variant="caption" color="warning.main">
                            Location not verified
                          </Typography>
                        </Tooltip>
                      )}
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {sourceLabel(c)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Tooltip title={c.status_reason
                        ? `${STATUS_HELP[c.status] ?? ''} (${c.status_reason.replace(/_/g, ' ')})`
                        : STATUS_HELP[c.status] ?? ''}>
                        <Chip size="small" label={c.status}
                              color={STATUS_COLOR[c.status] ?? 'default'}
                              variant="outlined" />
                      </Tooltip>
                    </TableCell>
                    <TableCell align="right">{c.evidence_count}</TableCell>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {formatDate(c.last_seen_at)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Button size="small" onClick={() => openDetail(c)}>Details</Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      {result && result.rejected_results.length > 0 && (
        <Box sx={{ mt: 4 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>
            Results that were not businesses ({result.rejected_results.length})
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Kept visible so nothing is discarded silently. A directory or article
            about competitors is not itself a competitor.
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Result</TableCell>
                  <TableCell>Domain</TableCell>
                  <TableCell>Classified as</TableCell>
                  <TableCell>Reason</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {result.rejected_results.map((r, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      {r.url ? (
                        <Link href={r.url} target="_blank" rel="noopener" underline="hover">
                          {r.title || r.url}
                        </Link>
                      ) : (r.title || '—')}
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption">{r.domain || '—'}</Typography>
                    </TableCell>
                    <TableCell>
                      <Chip size="small" label={r.entity_type} variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {r.reason.replace(/_/g, ' ')}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      <Dialog open={detail !== null} onClose={() => setDetail(null)} maxWidth="md" fullWidth>
        {detail && (
          <>
            <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box>
                <Typography variant="h6">{detail.name}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {detail.domain || 'No domain reported'}
                </Typography>
              </Box>
              <IconButton onClick={() => setDetail(null)} size="small">
                <CloseIcon />
              </IconButton>
            </DialogTitle>
            <DialogContent dividers>
              <Grid container spacing={2} sx={{ mb: 2 }}>
                {[
                  ['Status', detail.status],
                  ['Entity type', detail.entity_type],
                  ['Discovery source', sourceLabel(detail)],
                  ['Market / Industry', detail.markets.join(', ') || 'Not recorded'],
                  ['Discovery location', detail.locations.join(', ') || 'Not recorded'],
                  ['Identity match', detail.match_method.replace(/_/g, ' ')],
                  ['Match confidence', detail.match_confidence],
                  ['Own domain', detail.domain || 'Not reported'],
                  ['Address', detail.has_location_evidence
                    ? (detail.address || 'Not reported')
                    : 'Location not verified'],
                  ['Coordinates', detail.latitude !== null && detail.longitude !== null
                    ? `${detail.latitude}, ${detail.longitude}` : 'Not reported'],
                  ['Place ID', detail.place_id || 'Not reported'],
                  ['Rating', detail.rating !== null ? String(detail.rating) : 'Not reported'],
                  ['Reviews', detail.reviews !== null ? String(detail.reviews) : 'Not reported'],
                  ['Best search position', detail.best_position !== null ? String(detail.best_position) : 'Not reported'],
                  ['First seen', formatDate(detail.first_seen_at)],
                  ['Last seen', formatDate(detail.last_seen_at)],
                ].map(([label, value]) => (
                  <Grid size={{ xs: 6, sm: 4 }} key={label}>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      {label}
                    </Typography>
                    <Typography variant="body2">{value}</Typography>
                  </Grid>
                ))}
              </Grid>

              {detail.status_reason && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  {STATUS_HELP[detail.status]} Reason recorded:{' '}
                  {detail.status_reason.replace(/_/g, ' ')}.
                </Alert>
              )}

              {!detail.has_location_evidence && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  No provider returned an address or coordinates for this
                  business, so its location could not be confirmed. Nothing is
                  inferred from the domain name, and it is not promoted to
                  verified on that basis.
                </Alert>
              )}

              {!detail.domain && detail.website && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  This business listed{' '}
                  <Link href={detail.website} target="_blank" rel="noopener">
                    {detail.website}
                  </Link>{' '}
                  as its web presence. That page belongs to another platform, so
                  it is kept as evidence but not recorded as this business's own
                  domain — otherwise every business sharing that platform would
                  collide into one record.
                </Alert>
              )}

              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Discovery evidence ({detail.evidence.length})
              </Typography>
              {detail.evidence.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No evidence rows are recorded for this competitor.
                </Typography>
              ) : (
                <TableContainer variant="outlined" component={Paper}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Source</TableCell>
                        <TableCell>Match</TableCell>
                        <TableCell>Pos</TableCell>
                        <TableCell>Source URL</TableCell>
                        <TableCell>Source domain</TableCell>
                        <TableCell>Observed</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {detail.evidence.map((e, i) => (
                        <TableRow key={i}>
                          <TableCell>
                            <Chip size="small" variant="outlined"
                                  label={SOURCE_LABEL[e.discovery_method]
                                    ?? e.discovery_method.replace(/_/g, ' ')} />
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption">
                              {(e.match_method === 'unmatched' ? 'new' : e.match_method)
                                .replace(/_/g, ' ')}
                              {e.match_confidence !== 'unmatched' && ` · ${e.match_confidence}`}
                            </Typography>
                          </TableCell>
                          <TableCell>{e.position ?? '—'}</TableCell>
                          <TableCell sx={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {e.source_url ? (
                              <Link href={e.source_url} target="_blank" rel="noopener" underline="hover">
                                {e.source_url}
                              </Link>
                            ) : '—'}
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption">{e.source_domain || '—'}</Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption">{formatDate(e.observed_at)}</Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </DialogContent>
          </>
        )}
      </Dialog>
    </Box>
  );
};

export default Competitors;
