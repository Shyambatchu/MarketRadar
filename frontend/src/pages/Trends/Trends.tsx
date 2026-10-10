import { useState, useEffect, Fragment } from 'react';
import {
  Alert, Autocomplete, Box, Button, Chip, CircularProgress, Collapse, Grid, IconButton,
  InputAdornment, LinearProgress, MenuItem, Paper, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Tab, Tabs, TextField, Tooltip, Typography,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import TrendingUpOutlinedIcon from '@mui/icons-material/TrendingUpOutlined';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import RemoveIcon from '@mui/icons-material/Remove';
import SwapVertIcon from '@mui/icons-material/SwapVert';
import HelpOutlineIcon from '@mui/icons-material/HelpOutlineOutlined';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';

import PageHeader from '../../components/PageHeader/PageHeader';
import EmptyState from '../../components/EmptyState/EmptyState';
import ExportButton from '../../components/ExportButton/ExportButton';
import TrendChart, { Sparkline } from '../../components/TrendChart/TrendChart';
import {
  getAvailabilityTrends, getMerchantPresence, getPriceTrends,
  getTrendSummary, getVisibilityTrends,
} from '../../services/trendApi';
import { getMarketPulseOptions } from '../../services/marketPulseApi';
import { exportUrl } from '../../services/intelligenceApi';
import type {
  MerchantPresenceResponse, TrendListResponse, TrendSeries,
  TrendSummaryResponse,
} from '../../types/trend';
import type { MarketOption } from '../../types/marketPulse';
import { errorMessage, formatDateTime, formatMoney, isCanceled } from '../../utils/format';

type VisibilityMetric = 'position' | 'rating' | 'reviews';

const VISIBILITY_METRICS: { value: VisibilityMetric; label: string; help: string }[] = [
  { value: 'position', label: 'Search position', help: 'Rank in search results — lower is better.' },
  { value: 'rating', label: 'Rating', help: 'Average star rating reported by the provider.' },
  { value: 'reviews', label: 'Review count', help: 'Number of reviews reported by the provider.' },
];

const SIGNALS = ['prices', 'availability', 'visibility'] as const;

const optionLabel = (o: MarketOption): string =>
  `${o.market ?? 'Any market'} — ${o.location ?? 'any location'}`;

/**
 * Price series carry the one currency all their points share. The shared type
 * does not declare it yet, so it is read defensively; without it the bare
 * number is shown rather than an assumed "$".
 */
const seriesCurrency = (series: TrendSeries): string | null =>
  series.currency ?? null;

/**
 * A direction is only ever shown when two distinct measurements exist.
 * "insufficient_history" deliberately has no arrow: one reading observed
 * repeatedly has not been watched holding steady, it has just been read again.
 */
const DirectionIcon = ({ series }: { series: TrendSeries }) => {
  if (series.status !== 'trend' || !series.direction) {
    return <HelpOutlineIcon fontSize="small" sx={{ color: 'text.disabled' }} />;
  }
  // Availability is an ordinal of statuses, not a quantity: a move from
  // "found" to "unknown" means the evidence weakened, not that the product
  // declined, so it is never coloured as good or bad.
  if (series.metric === 'availability') {
    return <SwapVertIcon fontSize="small" sx={{ color: 'text.secondary' }} />;
  }
  // For position, a smaller number is better, so colour follows meaning
  // rather than arithmetic.
  const lowerIsBetter = series.metric === 'position';
  if (series.direction === 'up') {
    return <ArrowUpwardIcon fontSize="small"
      sx={{ color: lowerIsBetter ? 'warning.main' : 'success.main' }} />;
  }
  if (series.direction === 'down') {
    return <ArrowDownwardIcon fontSize="small"
      sx={{ color: lowerIsBetter ? 'success.main' : 'warning.main' }} />;
  }
  return <RemoveIcon fontSize="small" sx={{ color: 'text.secondary' }} />;
};

const STATUS_HELP: Record<string, string> = {
  trend: 'Two or more distinct measurements, so a direction can be stated.',
  insufficient_history: 'Only one distinct measurement so far. Repeating a search inside the 7-day response cache returns identical data, so it does not count as a second reading.',
  no_data: 'Nothing recorded for this metric.',
};

const formatValue = (series: TrendSeries, value: number | null): string => {
  if (value === null) return '—';
  if (series.metric === 'price') return formatMoney(value, seriesCurrency(series));
  if (series.metric === 'availability') {
    return { 1: 'found', 0: 'unknown', '-1': 'not found' }[String(value)] ?? String(value);
  }
  if (series.metric === 'position') return `#${value}`;
  return String(value);
};

const formatChange = (s: TrendSeries): string | null => {
  if (s.status !== 'trend' || s.change_absolute === null) return null;
  const sign = s.change_absolute > 0 ? '+' : '';
  const abs = s.metric === 'price' ? formatMoney(s.change_absolute, seriesCurrency(s)) : String(s.change_absolute);
  const pct = s.change_percent !== null ? ` (${s.change_percent > 0 ? '+' : ''}${s.change_percent}%)` : '';
  return `${sign}${abs}${pct}`;
};

/**
 * The series that actually moved, charted. Only `trend` series qualify: a
 * single measurement has no movement to show. Largest relative change first.
 */
const Movements = ({ series }: { series: TrendSeries[] }) => {
  const moved = series
    .filter((s) => s.status === 'trend' && s.points.length >= 2)
    .sort((a, b) => Math.abs(b.change_percent ?? 0) - Math.abs(a.change_percent ?? 0))
    .slice(0, 3);
  if (moved.length === 0) return null;
  return (
    <Box sx={{ mb: 3 }}>
      <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1.5, fontWeight: 600 }}>
        Measured movements
      </Typography>
      <Grid container spacing={2}>
        {moved.map((s, i) => (
          <Grid key={`${s.subject}-${i}`} size={{ xs: 12, md: moved.length === 1 ? 12 : 6, lg: 12 / moved.length }}>
            <Paper variant="outlined" sx={{ p: 2, height: '100%' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                <DirectionIcon series={s} />
                <Typography variant="subtitle2" noWrap sx={{ flex: 1 }}>{s.subject}</Typography>
              </Box>
              <Typography variant="h6" sx={{ mb: 1 }}>
                {formatValue(s, s.first_value)} → {formatValue(s, s.last_value)}
                {formatChange(s) && s.metric !== 'availability' && (
                  <Typography component="span" variant="body2" color="text.secondary">
                    {'  '}{formatChange(s)}
                  </Typography>
                )}
              </Typography>
              <TrendChart series={s} />
            </Paper>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

interface SeriesTableProps {
  data: TrendListResponse | null;
  loading: boolean;
  error: string | null;
  filtered: boolean;
}

const SeriesTable = ({ data, loading, error, filtered }: SeriesTableProps) => {
  const [open, setOpen] = useState<number | null>(null);
  if (loading) {
    return <Box sx={{ p: 4, textAlign: 'center' }}><CircularProgress size={28} /></Box>;
  }
  if (!data) {
    // A failed load is not an empty history.
    return (
      <Alert severity="warning">
        This signal could not be loaded, so nothing can be said about it.{error ? ` ${error}` : ''}
      </Alert>
    );
  }
  if (data.series.length === 0) {
    return (
      <EmptyState
        title={filtered ? 'Nothing recorded for these filters' : 'Nothing recorded for this signal yet'}
        description={data.detail
          ?? (filtered
            ? 'Widen the market, location or product filter to see other recorded history.'
            : 'Run Competitors or Products searches to begin building observation history.')}
        icon={<TrendingUpOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
      />
    );
  }

  return (
    <>
      {data.analyzable === 0 && data.detail && (
        <Alert severity="info" sx={{ mb: 2 }}>{data.detail}</Alert>
      )}
      <Movements series={data.series} />
      <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell />
              <TableCell>Subject</TableCell>
              <TableCell>Context</TableCell>
              <TableCell align="right">First</TableCell>
              <TableCell align="right">Latest</TableCell>
              <TableCell align="right">Change</TableCell>
              <TableCell>History</TableCell>
              <TableCell align="right">Measurements</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Last observed</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.series.map((s, i) => (
              <Fragment key={`${s.subject}-${s.subject_id}-${i}`}>
              <TableRow hover onClick={() => setOpen(open === i ? null : i)}
                        sx={{ cursor: 'pointer', '& > td': open === i ? { borderBottom: 'none' } : undefined }}>
                <TableCell sx={{ whiteSpace: 'nowrap' }}>
                  <IconButton size="small" aria-label={open === i ? 'Hide chart' : 'Show chart'}
                              onClick={(e) => { e.stopPropagation(); setOpen(open === i ? null : i); }}>
                    {open === i ? <KeyboardArrowUpIcon fontSize="small" /> : <KeyboardArrowDownIcon fontSize="small" />}
                  </IconButton>
                  <DirectionIcon series={s} />
                </TableCell>
                <TableCell>
                  <Typography variant="subtitle2">{s.subject}</Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="caption" color="text.secondary">
                    {s.context || '—'}
                  </Typography>
                </TableCell>
                <TableCell align="right">{formatValue(s, s.first_value)}</TableCell>
                <TableCell align="right">{formatValue(s, s.last_value)}</TableCell>
                <TableCell align="right">
                  {s.status === 'trend' && s.metric === 'availability' ? (
                    <Typography variant="body2">
                      {formatValue(s, s.first_value)} → {formatValue(s, s.last_value)}
                    </Typography>
                  ) : s.status === 'trend' && s.change_absolute !== null ? (
                    <Typography variant="body2">
                      {s.change_absolute > 0 ? '+' : ''}
                      {s.metric === 'price'
                        ? formatMoney(s.change_absolute, seriesCurrency(s))
                        : s.change_absolute}
                      {s.change_percent !== null && (
                        <Typography component="span" variant="caption" color="text.secondary">
                          {' '}({s.change_percent > 0 ? '+' : ''}{s.change_percent}%)
                        </Typography>
                      )}
                    </Typography>
                  ) : (
                    <Typography variant="caption" color="text.disabled">
                      Not yet measurable
                    </Typography>
                  )}
                </TableCell>
                <TableCell><Sparkline series={s} /></TableCell>
                <TableCell align="right">
                  <Tooltip title={`${s.distinct_points} distinct measurement${
                    s.distinct_points === 1 ? '' : 's'} from ${s.raw_observations} stored observation${
                    s.raw_observations === 1 ? '' : 's'}. Repeats within the cache window collapse.`}>
                    <Typography variant="body2">
                      {s.distinct_points}
                      <Typography component="span" variant="caption" color="text.secondary">
                        {' '}/ {s.raw_observations}
                      </Typography>
                    </Typography>
                  </Tooltip>
                </TableCell>
                <TableCell>
                  <Tooltip title={s.detail || STATUS_HELP[s.status] || ''}>
                    <Chip size="small" variant="outlined"
                          label={s.status.replace(/_/g, ' ')}
                          color={s.status === 'trend' ? 'success' : 'default'} />
                  </Tooltip>
                </TableCell>
                <TableCell>
                  <Typography variant="caption" color="text.secondary">
                    {formatDateTime(s.last_observed_at)}
                  </Typography>
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell colSpan={10} sx={{ py: 0, ...(open === i ? {} : { borderBottom: 'none' }) }}>
                  <Collapse in={open === i} timeout="auto" unmountOnExit>
                    <Box sx={{ py: 2, px: 1 }}><TrendChart series={s} /></Box>
                  </Collapse>
                </TableCell>
              </TableRow>
              </Fragment>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
};

type SignalKey = 'summary' | 'prices' | 'availability' | 'visibility' | 'presence';

const SIGNAL_LABEL: Record<SignalKey, string> = {
  summary: 'summary',
  prices: 'prices',
  availability: 'availability',
  visibility: 'visibility',
  presence: 'merchant presence',
};

const Trends = () => {
  const [tab, setTab] = useState(0);
  // `loading` is the first load (full-page spinner); `refreshing` is a
  // re-fetch after a filter change (tables show their own spinner).
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [signalErrors, setSignalErrors] = useState<Partial<Record<SignalKey, string>>>({});

  const [summary, setSummary] = useState<TrendSummaryResponse | null>(null);
  const [prices, setPrices] = useState<TrendListResponse | null>(null);
  const [availability, setAvailability] = useState<TrendListResponse | null>(null);
  const [visibility, setVisibility] = useState<TrendListResponse | null>(null);
  const [presence, setPresence] = useState<MerchantPresenceResponse | null>(null);

  // Filters. Scope choices come from observed history (Market Pulse options),
  // so a selection always refers to something actually recorded.
  const [options, setOptions] = useState<MarketOption[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [scope, setScope] = useState<MarketOption | null>(null);
  const [productInput, setProductInput] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [metric, setMetric] = useState<VisibilityMetric>('position');

  const market = scope?.market ?? undefined;
  const location = scope?.location ?? undefined;
  const q = appliedQ || undefined;
  const filtered = !!scope || !!appliedQ;

  useEffect(() => {
    const controller = new AbortController();
    getMarketPulseOptions(controller.signal)
      .then((res) => setOptions(res.options))
      .catch((err) => {
        if (!isCanceled(err)) {
          setOptionsError(errorMessage(err, 'Observed markets could not be loaded, so the market filter is unavailable.'));
        }
      })
      .finally(() => { if (!controller.signal.aborted) setOptionsLoading(false); });
    return () => controller.abort();
  }, []);

  // Typing applies after a pause; Enter or the button applies at once.
  useEffect(() => {
    const handle = window.setTimeout(() => setAppliedQ(productInput.trim()), 600);
    return () => window.clearTimeout(handle);
  }, [productInput]);

  // Everything here is a database read — no provider request, no credit.
  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      setRefreshing(true);
      // Settled independently: one failing signal must not blank the others.
      const results = await Promise.allSettled([
        getTrendSummary(controller.signal),
        getPriceTrends({ q, market, location }, controller.signal),
        getAvailabilityTrends({ q, market, location }, controller.signal),
        getVisibilityTrends({ market, location, metric }, controller.signal),
        getMerchantPresence({ market, location }, controller.signal),
      ]);
      // An aborted (StrictMode / unmounted / superseded) load must not touch
      // state, or it briefly reports "no history" while the real request runs.
      if (controller.signal.aborted) return;

      const [s, p, a, v, m] = results;
      // A failed signal is cleared rather than left showing data for
      // different filters.
      setSummary(s.status === 'fulfilled' ? s.value : null);
      setPrices(p.status === 'fulfilled' ? p.value : null);
      setAvailability(a.status === 'fulfilled' ? a.value : null);
      setVisibility(v.status === 'fulfilled' ? v.value : null);
      setPresence(m.status === 'fulfilled' ? m.value : null);

      const keys: SignalKey[] = ['summary', 'prices', 'availability', 'visibility', 'presence'];
      const errs: Partial<Record<SignalKey, string>> = {};
      results.forEach((r, i) => {
        if (r.status === 'rejected') errs[keys[i]] = errorMessage(r.reason, 'Could not be loaded.');
      });
      setSignalErrors(errs);

      const failed = keys.filter((k) => errs[k]);
      if (failed.length) {
        const first = errs[failed[0]];
        setError(
          (failed.length === results.length
            ? 'Trend data could not be loaded.'
            : `Could not load: ${failed.map((k) => SIGNAL_LABEL[k]).join(', ')}.`)
          + (first ? ` ${first}` : ''));
      } else {
        setError(null);
      }
      setLoading(false);
      setRefreshing(false);
    };
    load();
    return () => controller.abort();
  }, [q, market, location, metric]);

  const applyProduct = () => setAppliedQ(productInput.trim());
  const clearFilters = () => { setScope(null); setProductInput(''); setAppliedQ(''); };

  const activeSignal = tab <= 2 ? SIGNALS[tab] : null;
  const exportHref = activeSignal
    ? exportUrl('trends', {
      signal: activeSignal,
      q: activeSignal === 'visibility' ? undefined : q,
      market, location,
      metric: activeSignal === 'visibility' ? metric : undefined,
    })
    : '';

  const noHistory = summary
    && summary.competitor_observations === 0
    && summary.product_observations === 0;

  return (
    <Box>
      <PageHeader
        title="Trends"
        subtitle="Change over time, derived from observations already recorded by Competitors and Products."
        action={activeSignal ? (
          <ExportButton href={exportHref} label={`Export ${activeSignal}`}
                        disabled={loading || refreshing}
          />
        ) : undefined}
      />

      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} sx={{ alignItems: 'center' }}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Autocomplete
              size="small"
              options={options}
              value={scope}
              onChange={(_, v) => setScope(v)}
              getOptionLabel={optionLabel}
              isOptionEqualToValue={(a, b) => a.market === b.market && a.location === b.location}
              loading={optionsLoading}
              disabled={!!optionsError}
              renderInput={(params) => (
                <TextField {...params} label="Market and location"
                           placeholder={optionsLoading ? 'Loading observed markets…' : 'All markets and locations'}
                           helperText={scope ? undefined : 'All recorded markets and locations'} />
              )}
              renderOption={(props, o) => (
                <li {...props} key={`${o.market}-${o.location}`}>
                  <Box>
                    <Typography variant="body2">{o.market ?? 'Any market'}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {o.location ?? 'any location'} · {o.merchants} merchant(s) ·{' '}
                      {o.product_observations} product observation(s)
                    </Typography>
                  </Box>
                </li>
              )}
              noOptionsText="No markets have been observed yet."
            />
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <TextField
              fullWidth size="small" label="Product"
              placeholder="Filter prices and availability"
              helperText="Applies to prices and availability"
              value={productInput}
              onChange={(e) => setProductInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') applyProduct(); }}
              slotProps={{
                input: {
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton size="small" aria-label="Apply product filter" onClick={applyProduct}>
                        <SearchIcon fontSize="small" />
                      </IconButton>
                    </InputAdornment>
                  ),
                },
              }}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 2 }}>
            <Button fullWidth size="small" startIcon={<ClearIcon />} onClick={clearFilters}
                    disabled={!filtered && !productInput}>
              Clear filters
            </Button>
          </Grid>
        </Grid>
        {optionsError && (
          <Typography variant="caption" color="error" sx={{ display: 'block', mt: 1 }}>
            {optionsError}
          </Typography>
        )}
        {refreshing && !loading && <LinearProgress sx={{ mt: 2 }} />}
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      {summary && (
        <>
          <Paper variant="outlined" elevation={0} sx={{ p: 2, mb: 3 }}>
            {filtered && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                These totals cover all recorded history; the filters apply to the tabs below.
              </Typography>
            )}
            <Grid container spacing={2}>
              {[
                ['Competitor observations', summary.competitor_observations],
                ['Product observations', summary.product_observations],
                ['Merchants tracked', summary.merchants_tracked],
                ['Verified price observations', summary.verified_price_observations],
                ['Comparable contexts', summary.contexts.length],
                ['Analyzable contexts', summary.analyzable_contexts],
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

          {summary.insufficient_history && summary.detail && (
            <Alert severity="info" sx={{ mb: 3 }}>
              <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                Not enough history to state a direction yet
              </Typography>
              {summary.detail}
            </Alert>
          )}
        </>
      )}

      {loading ? (
        <Box sx={{ p: 6, textAlign: 'center' }}><CircularProgress /></Box>
      ) : !summary && !prices && !availability && !visibility && !presence && error ? null : noHistory ? (
        <EmptyState
          title="No observation history yet"
          description="Trends are derived from what Competitors and Products have already recorded. Run a search in either module to begin building history — Trends itself makes no external requests."
          icon={<TrendingUpOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
        />
      ) : (
        <>
          <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
            <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" allowScrollButtonsMobile>
              <Tab label={`Prices (${prices?.total ?? 0})`} />
              <Tab label={`Availability (${availability?.total ?? 0})`} />
              <Tab label={`Visibility (${visibility?.total ?? 0})`} />
              <Tab label={`Merchant presence (${presence?.total ?? 0})`} />
              <Tab label={`Contexts (${summary?.contexts.length ?? 0})`} />
            </Tabs>
          </Box>

          {tab === 0 && (
            <SeriesTable data={prices} loading={refreshing} error={signalErrors.prices ?? null}
                         filtered={filtered} />
          )}
          {tab === 1 && (
            <SeriesTable data={availability} loading={refreshing}
                         error={signalErrors.availability ?? null} filtered={filtered} />
          )}
          {tab === 2 && (
            <>
              <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap', mb: 2 }}>
                <TextField
                  select size="small" label="Visibility metric" value={metric}
                  onChange={(e) => setMetric(e.target.value as VisibilityMetric)}
                  sx={{ minWidth: 200 }}
                >
                  {VISIBILITY_METRICS.map((m) => (
                    <MenuItem key={m.value} value={m.value}>{m.label}</MenuItem>
                  ))}
                </TextField>
                <Typography variant="caption" color="text.secondary">
                  {VISIBILITY_METRICS.find((m) => m.value === metric)?.help}
                  {appliedQ ? ' The product filter does not apply to visibility.' : ''}
                </Typography>
              </Box>
              <SeriesTable data={visibility} loading={refreshing}
                           error={signalErrors.visibility ?? null} filtered={!!scope} />
            </>
          )}

          {tab === 3 && (
            refreshing ? (
              <Box sx={{ p: 4, textAlign: 'center' }}><CircularProgress size={28} /></Box>
            ) : !presence ? (
              <Alert severity="warning">
                Merchant presence could not be loaded.{signalErrors.presence ? ` ${signalErrors.presence}` : ''}
              </Alert>
            ) : presence.merchants.length > 0 ? (
              <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Business</TableCell>
                      <TableCell>Market / Location</TableCell>
                      <TableCell>First seen</TableCell>
                      <TableCell>Last seen</TableCell>
                      <TableCell align="right">Searches</TableCell>
                      <TableCell>In latest search</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {presence.merchants.map((m, i) => (
                      <TableRow key={`${m.merchant_id}-${i}`} hover>
                        <TableCell>
                          <Typography variant="subtitle2">{m.merchant}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {m.domain || 'No domain reported'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{m.market || '—'}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {m.location || '—'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption">{formatDateTime(m.first_seen_at)}</Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption">{formatDateTime(m.last_seen_at)}</Typography>
                        </TableCell>
                        <TableCell align="right">{m.distinct_searches}</TableCell>
                        <TableCell>
                          {m.present_in_latest ? (
                            <Chip size="small" label="present" color="success" variant="outlined" />
                          ) : (
                            <Tooltip title="This business was not in the most recent search of its context. That is not proof it has gone — a later search may simply have returned a different slice of results.">
                              <Chip size="small" label="not in latest" color="warning" variant="outlined" />
                            </Tooltip>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            ) : (
              <EmptyState
                title={scope ? 'No merchant history for this market and location' : 'No merchant history yet'}
                description={presence?.detail ?? 'Run a Competitors search to begin recording merchant presence.'}
                icon={<TrendingUpOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
              />
            )
          )}

          {tab === 4 && !summary && (
            <Alert severity="warning">
              Contexts could not be loaded.{signalErrors.summary ? ` ${signalErrors.summary}` : ''}
            </Alert>
          )}
          {tab === 4 && summary && (
            <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Source</TableCell>
                    <TableCell>Market</TableCell>
                    <TableCell>Location</TableCell>
                    <TableCell align="right">Observations</TableCell>
                    <TableCell align="right">Distinct searches</TableCell>
                    <TableCell align="right">Span (hours)</TableCell>
                    <TableCell>Analyzable</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {summary.contexts.map((c, i) => (
                    <TableRow key={i} hover>
                      <TableCell>
                        <Chip size="small" label={c.source} variant="outlined" />
                      </TableCell>
                      <TableCell>{c.market || '—'}</TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {c.location || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">{c.observations}</TableCell>
                      <TableCell align="right">{c.distinct_searches}</TableCell>
                      <TableCell align="right">{c.span_hours ?? '—'}</TableCell>
                      <TableCell>
                        <Tooltip title={c.detail || 'Two or more searches recorded, so measurements can be compared.'}>
                          <Chip size="small" variant="outlined"
                                label={c.analyzable ? 'yes' : 'not yet'}
                                color={c.analyzable ? 'success' : 'default'} />
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </>
      )}
    </Box>
  );
};

export default Trends;
