import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Card, Chip,
  CircularProgress, Grid, InputAdornment, Link, MenuItem, Pagination, Paper, Skeleton,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField,
  ToggleButton, ToggleButtonGroup, Tooltip, Typography,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import BookmarkAddOutlinedIcon from '@mui/icons-material/BookmarkAddOutlined';
import StorefrontOutlinedIcon from '@mui/icons-material/StorefrontOutlined';
import GridViewIcon from '@mui/icons-material/GridView';
import ViewListIcon from '@mui/icons-material/ViewList';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FilterAltOffOutlinedIcon from '@mui/icons-material/FilterAltOffOutlined';
import { isAxiosError } from 'axios';

import PageHeader from '../../components/PageHeader/PageHeader';
import EmptyState from '../../components/EmptyState/EmptyState';
import ExportButton from '../../components/ExportButton/ExportButton';
import {
  getCompetitor, listCompetitors, reviewCompetitor, searchCompetitors,
} from '../../services/competitorApi';
import { exportUrl, saveSearch } from '../../services/intelligenceApi';
import type { Competitor, CompetitorSearchResponse } from '../../types/competitor';
import { errorMessage, humanize } from '../../utils/format';
import type { ReviewUpdate } from './CompetitorReview';
import CompetitorCard from './CompetitorCard';
import CompetitorTable from './CompetitorTable';
import CompetitorDrawer from './CompetitorDrawer';
import {
  SORT_OPTIONS, matchesReview, matchesText, sortCompetitors, withReview,
  type ReviewFilter, type SortKey,
} from './competitorDisplay';

type Layout = 'cards' | 'table';
type Source = 'saved' | 'search';

const PAGE_SIZE: Record<Layout, number> = { cards: 12, table: 20 };
const LAYOUT_KEY = 'marketradar.competitors.layout';

const readLayout = (): Layout => {
  try {
    return localStorage.getItem(LAYOUT_KEY) === 'table' ? 'table' : 'cards';
  } catch {
    return 'cards';
  }
};

const searchErrorMessage = (err: unknown): string => {
  if (!isAxiosError(err)) return 'An unexpected error occurred.';
  const detail = err.response?.data?.detail;
  if (typeof detail === 'string' && detail) return detail;
  switch (err.response?.status) {
    case 400: return 'Provide a market or query and a location.';
    case 422: return 'That location could not be matched to a supported search location.';
    case 429: return 'The search limit has been reached, so no new discovery ran. Saved competitors remain available.';
    case 502: return 'The search provider did not respond, so no competitors could be discovered. This is not the same as finding none.';
    case 503: return 'Competitor discovery is not configured yet.';
    default: return errorMessage(err, 'Unable to discover competitors. Try again in a moment.');
  }
};

interface StatProps { label: string; value: number | string; hint?: string; tone?: string }

const Stat = ({ label, value, hint, tone }: StatProps) => (
  <Paper variant="outlined" sx={{ p: 2, height: '100%' }}>
    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
      {label}
    </Typography>
    <Typography variant="h5" sx={{ fontWeight: 700, color: tone ?? 'text.primary', mt: 0.5 }}>{value}</Typography>
    {hint && <Typography variant="caption" color="text.secondary">{hint}</Typography>}
  </Paper>
);

const Competitors = () => {
  const [searchParams] = useSearchParams();
  // Links from other pages prefill the form; nothing runs until Search.
  const [market, setMarket] = useState(() => searchParams.get('market') ?? '');
  const [location, setLocation] = useState(() => searchParams.get('location') ?? '');
  const [query, setQuery] = useState('');

  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [result, setResult] = useState<CompetitorSearchResponse | null>(null);
  const [source, setSource] = useState<Source>('saved');

  const [saved, setSaved] = useState<Competitor[]>([]);
  const [savedTotal, setSavedTotal] = useState(0);
  const [savedError, setSavedError] = useState<string | null>(null);
  const [savedLoading, setSavedLoading] = useState(true);

  // Browsing controls, shared by the saved list and a search's results.
  const [text, setText] = useState('');
  const [marketFilter, setMarketFilter] = useState('');
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>('all');
  const [sort, setSort] = useState<SortKey>('recent');
  const [layout, setLayout] = useState<Layout>(readLayout);
  const [page, setPage] = useState(1);

  const [detail, setDetail] = useState<Competitor | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [reviewBusyId, setReviewBusyId] = useState<number | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);

  const [lastSearch, setLastSearch] = useState<{ market: string; query: string; location: string } | null>(null);
  const [saveMessage, setSaveMessage] = useState<{ text: string; error: boolean } | null>(null);
  const isSearching = useRef(false);

  const loadSaved = (signal?: AbortSignal) => listCompetitors({}, signal)
    .then((data) => {
      setSaved(data.competitors);
      setSavedTotal(data.total);
      setSavedError(null);
    })
    .catch((err) => {
      if (!isAxiosError(err) || err.code !== 'ERR_CANCELED') {
        setSavedError(errorMessage(err, 'Saved competitors could not be loaded.'));
      }
    })
    .finally(() => { if (!signal?.aborted) setSavedLoading(false); });

  // Saved competitors show on arrival, so the page is useful before any search.
  useEffect(() => {
    const controller = new AbortController();
    loadSaved(controller.signal);
    return () => controller.abort();
  }, []);

  const resetBrowsing = () => {
    setText('');
    setMarketFilter('');
    setReviewFilter('all');
    setPage(1);
  };

  const handleSearch = async () => {
    // A location is required: discovery finds businesses in a market *and* a
    // place, and an unscoped search would persist unrelated results.
    if ((!market.trim() && !query.trim()) || !location.trim() || isSearching.current) return;
    isSearching.current = true;
    setSearching(true);
    setSearchError(null);
    setSaveMessage(null);
    try {
      const params = { market: market.trim(), query: query.trim(), location: location.trim() };
      const data = await searchCompetitors(params);
      setResult(data);
      setLastSearch(params);
      setSource('search');
      resetBrowsing();
      setSort('position');
      loadSaved();
    } catch (err) {
      setSearchError(searchErrorMessage(err));
    } finally {
      setSearching(false);
      isSearching.current = false;
    }
  };

  const openDetail = async (competitor: Competitor) => {
    setReviewError(null);
    setDetailError(null);
    setDetail(competitor);
    if (competitor.id === null) return;
    setDetailLoading(true);
    try {
      const full = await getCompetitor(competitor.id);
      setDetail((current) => (current?.id === full.id ? full : current));
    } catch (err) {
      setDetailError(errorMessage(err, 'The full evidence for this business could not be loaded.'));
    } finally {
      setDetailLoading(false);
    }
  };

  const handleReview = async (competitor: Competitor, update: ReviewUpdate) => {
    if (competitor.id === null || reviewBusyId !== null) return;
    const id = competitor.id;
    setReviewBusyId(id);
    setReviewError(null);
    try {
      const updated = await reviewCompetitor(id, update);
      setSaved((rows) => rows.map((r) => (r.id === id ? withReview(r, updated) : r)));
      setResult((current) => current && {
        ...current,
        competitors: current.competitors.map((r) => (r.id === id ? withReview(r, updated) : r)),
      });
      setDetail((current) => (current?.id === id ? withReview(current, updated) : current));
    } catch (err) {
      setReviewError(errorMessage(err, 'Your review could not be saved. Try again.'));
    } finally {
      setReviewBusyId(null);
    }
  };

  const handleSaveSearch = async () => {
    if (!lastSearch) return;
    try {
      const res = await saveSearch({
        module: 'competitors', query: lastSearch.market || lastSearch.query,
        market: lastSearch.market || undefined, location: lastSearch.location || undefined,
      });
      setSaveMessage({ text: res.created ? 'Search saved.' : 'Already saved.', error: false });
    } catch (err) {
      setSaveMessage({ text: errorMessage(err, 'The search could not be saved.'), error: true });
    }
  };

  const base = source === 'search' && result ? result.competitors : saved;
  const markets = useMemo(
    () => Array.from(new Set(base.flatMap((c) => c.markets))).sort(), [base]);
  const inScope = base.filter((c) => (!marketFilter || c.markets.includes(marketFilter))
    && matchesText(c, text));
  const reviewCounts: Record<ReviewFilter, number> = {
    all: inScope.length,
    unreviewed: inScope.filter((c) => matchesReview(c, 'unreviewed')).length,
    confirmed: inScope.filter((c) => matchesReview(c, 'confirmed')).length,
    rejected: inScope.filter((c) => matchesReview(c, 'rejected')).length,
  };
  const visible = sortCompetitors(inScope.filter((c) => matchesReview(c, reviewFilter)), sort);
  const pageSize = PAGE_SIZE[layout];
  const pageCount = Math.max(1, Math.ceil(visible.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const pageRows = visible.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const filtersActive = !!text || !!marketFilter || reviewFilter !== 'all';
  const listLoading = source === 'saved' && savedLoading;
  const problemStages = source === 'search' && result
    ? result.stages.filter((s) => s.status === 'error' || s.status === 'degraded') : [];

  const changeLayout = (next: Layout | null) => {
    if (!next) return;
    setLayout(next);
    setPage(1);
    try { localStorage.setItem(LAYOUT_KEY, next); } catch { /* preference only */ }
  };

  return (
    <Box>
      <PageHeader
        title="Competitors"
        subtitle="Find the businesses competing in a market and place, then confirm which ones matter to you."
        action={(
          <ExportButton
            label="Export"
            href={exportUrl('competitors', {
              market: marketFilter || undefined,
              review_status: reviewFilter === 'all' ? undefined : reviewFilter,
            })}
            disabled={savedLoading || saved.length === 0}
          />
        )}
      />

      {/* ---------------- discovery ---------------- */}
      <Paper sx={{ p: { xs: 2, md: 2.5 }, mb: 3 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1.5 }}>Discover competitors</Typography>
        <Grid container spacing={1.5} sx={{ alignItems: 'flex-start' }}>
          <Grid size={{ xs: 12, sm: 6, md: 3.5 }}>
            <TextField fullWidth size="small" label="Market or industry" placeholder="e.g. Coffee shops"
                       value={market} onChange={(e) => setMarket(e.target.value)} disabled={searching}
                       onKeyDown={(e) => { if (e.key === 'Enter') handleSearch(); }} />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3.5 }}>
            <TextField fullWidth size="small" label="Location" required placeholder="e.g. Austin, Texas"
                       value={location} onChange={(e) => setLocation(e.target.value)} disabled={searching}
                       onKeyDown={(e) => { if (e.key === 'Enter') handleSearch(); }} />
          </Grid>
          <Grid size={{ xs: 12, sm: 8, md: 3 }}>
            <TextField fullWidth size="small" label="Custom query (optional)" placeholder="Uses the market if blank"
                       value={query} onChange={(e) => setQuery(e.target.value)} disabled={searching}
                       onKeyDown={(e) => { if (e.key === 'Enter') handleSearch(); }} />
          </Grid>
          <Grid size={{ xs: 12, sm: 4, md: 2 }}>
            <Button fullWidth variant="contained" sx={{ height: 40 }}
                    startIcon={searching ? <CircularProgress size={18} color="inherit" /> : <SearchIcon />}
                    onClick={handleSearch}
                    disabled={searching || (!market.trim() && !query.trim()) || !location.trim()}>
              {searching ? 'Searching…' : 'Search'}
            </Button>
          </Grid>
        </Grid>
        {searching && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            Looking up local listings and web results for this market…
          </Typography>
        )}
      </Paper>

      {searchError && <Alert severity="error" sx={{ mb: 3 }} onClose={() => setSearchError(null)}>{searchError}</Alert>}
      {reviewError && detail === null && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setReviewError(null)}>{reviewError}</Alert>
      )}

      {/* ---------------- which list ---------------- */}
      {result && (
        <Box sx={{ mb: 2, display: 'flex', gap: 1.5, alignItems: 'center', flexWrap: 'wrap' }}>
          <ToggleButtonGroup size="small" exclusive value={source}
                             onChange={(_, v: Source | null) => { if (v) { setSource(v); resetBrowsing(); } }}>
            <ToggleButton value="search">Latest search ({result.competitors.length})</ToggleButton>
            <ToggleButton value="saved">All saved ({savedTotal})</ToggleButton>
          </ToggleButtonGroup>
          {source === 'search' && (
            <>
              <Typography variant="body2" color="text.secondary">
                {result.effective_query} · {result.location_resolved ?? result.location_requested}
              </Typography>
              {result.cache_hit && <Chip size="small" variant="outlined" label="Recent cached result" />}
              <Button size="small" startIcon={<BookmarkAddOutlinedIcon />} onClick={handleSaveSearch}>
                Save search
              </Button>
              {saveMessage && (
                <Typography variant="caption" color={saveMessage.error ? 'error' : 'success.main'}>
                  {saveMessage.text}
                </Typography>
              )}
            </>
          )}
        </Box>
      )}

      {problemStages.map((s) => (
        <Alert key={s.stage} severity={s.status === 'error' ? 'error' : 'warning'} sx={{ mb: 2 }}>
          {humanize(s.stage)}: {s.status}{s.detail ? ` — ${s.detail}` : ''}
        </Alert>
      ))}

      {/* ---------------- summary ---------------- */}
      {source === 'search' && result ? (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid size={{ xs: 6, md: 3 }}>
            <Stat label="Businesses found" value={result.competitors.length}
                  hint={`${result.new_competitors} new to your list`} />
          </Grid>
          <Grid size={{ xs: 6, md: 3 }}>
            <Stat label="Verified identity" value={result.competitors_verified} tone="success.main"
                  hint={`${result.competitors_discovered} discovered · ${result.competitors_uncertain} uncertain`} />
          </Grid>
          <Grid size={{ xs: 6, md: 3 }}>
            <Stat label="Results screened" value={result.local_results_found + result.organic_results_found}
                  hint={`${result.local_results_found} local · ${result.organic_results_found} web`} />
          </Grid>
          <Grid size={{ xs: 6, md: 3 }}>
            <Stat label="Filtered out" value={result.rejected_non_business}
                  hint={`directories, articles, social · ${result.duplicates_merged} duplicates merged`} />
          </Grid>
        </Grid>
      ) : !savedLoading && !savedError && saved.length > 0 && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid size={{ xs: 6, md: 3 }}>
            <Stat label="Businesses" value={savedTotal} hint={`across ${markets.length} market${markets.length === 1 ? '' : 's'}`} />
          </Grid>
          <Grid size={{ xs: 6, md: 3 }}>
            <Stat label="Confirmed" value={saved.filter((c) => c.review_status === 'confirmed').length}
                  tone="success.main" hint="your competitors" />
          </Grid>
          <Grid size={{ xs: 6, md: 3 }}>
            <Stat label="Awaiting review" value={saved.filter((c) => c.review_status === null).length}
                  tone="warning.main" hint="confirm or reject each" />
          </Grid>
          <Grid size={{ xs: 6, md: 3 }}>
            <Stat label="Verified identity" value={saved.filter((c) => c.status === 'verified').length}
                  hint="strong listing evidence" />
          </Grid>
        </Grid>
      )}

      {/* ---------------- browse controls ---------------- */}
      {(base.length > 0 || listLoading) && !savedError && (
        <Paper variant="outlined" sx={{ p: 1.5, mb: 2, display: 'flex', gap: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
          <TextField
            size="small" placeholder="Search by name, website or address" value={text}
            onChange={(e) => { setText(e.target.value); setPage(1); }}
            sx={{ flex: '1 1 220px', minWidth: 200 }}
            slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> } }}
          />
          {markets.length > 1 && (
            <TextField select size="small" label="Market" value={marketFilter}
                       onChange={(e) => { setMarketFilter(e.target.value); setPage(1); }}
                       sx={{ minWidth: 170 }}
                       slotProps={{ select: { displayEmpty: true }, inputLabel: { shrink: true } }}>
              <MenuItem value="">All markets</MenuItem>
              {markets.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
            </TextField>
          )}
          <TextField select size="small" label="Sort by" value={sort}
                     onChange={(e) => setSort(e.target.value as SortKey)} sx={{ minWidth: 170 }}>
            {SORT_OPTIONS.map((o) => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
          </TextField>
          <ToggleButtonGroup size="small" exclusive value={layout} onChange={(_, v) => changeLayout(v)}
                             aria-label="Layout" sx={{ ml: { md: 'auto' } }}>
            <ToggleButton value="cards" aria-label="Card view"><Tooltip title="Cards"><GridViewIcon fontSize="small" /></Tooltip></ToggleButton>
            <ToggleButton value="table" aria-label="Table view"><Tooltip title="Table"><ViewListIcon fontSize="small" /></Tooltip></ToggleButton>
          </ToggleButtonGroup>
          <Box sx={{ flexBasis: '100%', display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
            {([['all', 'All'], ['unreviewed', 'Awaiting review'], ['confirmed', 'Confirmed'], ['rejected', 'Rejected']] as [ReviewFilter, string][])
              .map(([value, label]) => (
                <Chip key={value} size="small" label={`${label} · ${reviewCounts[value]}`}
                      color={reviewFilter === value ? 'primary' : 'default'}
                      variant={reviewFilter === value ? 'filled' : 'outlined'}
                      onClick={() => { setReviewFilter(value); setPage(1); }} />
              ))}
            {filtersActive && (
              <Button size="small" startIcon={<FilterAltOffOutlinedIcon />} onClick={resetBrowsing}>Clear filters</Button>
            )}
            <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
              {visible.length} of {base.length} shown
            </Typography>
          </Box>
        </Paper>
      )}

      {/* ---------------- list ---------------- */}
      {source === 'saved' && savedError ? (
        <Alert severity="error" action={<Button color="inherit" size="small" onClick={() => { setSavedLoading(true); loadSaved(); }}>Retry</Button>}>
          {savedError}
        </Alert>
      ) : listLoading ? (
        <Grid container spacing={2} aria-busy="true" aria-label="Loading competitors">
          {Array.from({ length: 6 }).map((_, i) => (
            <Grid key={i} size={{ xs: 12, sm: 6, lg: 4 }}>
              <Card variant="outlined" sx={{ p: 2 }}>
                <Box sx={{ display: 'flex', gap: 1.5, mb: 2 }}>
                  <Skeleton variant="circular" width={40} height={40} />
                  <Box sx={{ flexGrow: 1 }}><Skeleton width="70%" /><Skeleton width="45%" /></Box>
                </Box>
                <Skeleton width="55%" /><Skeleton width="85%" />
                <Skeleton variant="rounded" height={28} sx={{ mt: 2 }} />
              </Card>
            </Grid>
          ))}
        </Grid>
      ) : base.length === 0 ? (
        <EmptyState
          title={source === 'saved' ? 'No competitors yet' : 'No competing businesses found'}
          description={source === 'saved'
            ? 'Enter a market and a location above to discover the businesses competing there.'
            : result && result.rejected_non_business > 0
              ? `${result.rejected_non_business} results were directories, articles or social profiles rather than businesses.`
              : 'The search ran and returned no businesses for this market and location.'}
          icon={<StorefrontOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
        />
      ) : visible.length === 0 ? (
        <EmptyState
          title="Nothing matches these filters"
          description="Try a different name, market or review status."
          actionText="Clear filters" onAction={resetBrowsing}
          icon={<FilterAltOffOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
        />
      ) : layout === 'cards' ? (
        <Grid container spacing={2}>
          {pageRows.map((c, i) => (
            <Grid key={c.id ?? `c-${i}`} size={{ xs: 12, sm: 6, lg: 4 }}>
              <CompetitorCard competitor={c} busy={reviewBusyId === c.id}
                              onReview={handleReview} onOpen={openDetail} />
            </Grid>
          ))}
        </Grid>
      ) : (
        <CompetitorTable rows={pageRows} busyId={reviewBusyId} onReview={handleReview} onOpen={openDetail} />
      )}

      {pageCount > 1 && !listLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
          <Pagination count={pageCount} page={currentPage} color="primary" shape="rounded"
                      onChange={(_, p) => { setPage(p); window.scrollTo({ top: 0, behavior: 'smooth' }); }} />
        </Box>
      )}

      {/* ---------------- what the search filtered out ---------------- */}
      {source === 'search' && result && result.rejected_results.length > 0 && (
        <Accordion variant="outlined" disableGutters sx={{ mt: 3, '&:before': { display: 'none' } }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2">
              {result.rejected_results.length} results were not businesses
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ ml: 1.5, alignSelf: 'center' }}>
              directories, articles, marketplaces and social profiles
            </Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ p: 0 }}>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Result</TableCell>
                    <TableCell>Classified as</TableCell>
                    <TableCell>Reason</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {result.rejected_results.map((r, i) => (
                    <TableRow key={i}>
                      <TableCell sx={{ maxWidth: 360 }}>
                        {r.url ? (
                          <Link href={r.url} target="_blank" rel="noopener noreferrer" underline="hover">
                            {r.title || r.url}
                          </Link>
                        ) : (r.title || '—')}
                        {r.domain && (
                          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>{r.domain}</Typography>
                        )}
                      </TableCell>
                      <TableCell><Chip size="small" label={humanize(r.entity_type)} variant="outlined" /></TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">{humanize(r.reason)}</Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </AccordionDetails>
        </Accordion>
      )}

      <CompetitorDrawer
        competitor={detail} loading={detailLoading} error={detailError}
        reviewBusy={reviewBusyId !== null && reviewBusyId === detail?.id}
        reviewError={reviewError} onReview={handleReview}
        onClose={() => { setDetail(null); setReviewError(null); setDetailError(null); }}
      />
    </Box>
  );
};

export default Competitors;
