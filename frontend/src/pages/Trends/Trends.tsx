import { useState, useEffect } from 'react';
import {
  Alert, Box, Chip, CircularProgress, Grid, Paper, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Tab, Tabs, Tooltip,
  Typography,
} from '@mui/material';
import TrendingUpOutlinedIcon from '@mui/icons-material/TrendingUpOutlined';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import RemoveIcon from '@mui/icons-material/Remove';
import SwapVertIcon from '@mui/icons-material/SwapVert';
import HelpOutlineIcon from '@mui/icons-material/HelpOutlineOutlined';
import { isAxiosError } from 'axios';

import PageHeader from '../../components/PageHeader/PageHeader';
import EmptyState from '../../components/EmptyState/EmptyState';
import {
  getAvailabilityTrends, getMerchantPresence, getPriceTrends,
  getTrendSummary, getVisibilityTrends,
} from '../../services/trendApi';
import type {
  MerchantPresenceResponse, TrendListResponse, TrendSeries,
  TrendSummaryResponse,
} from '../../types/trend';

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

const formatDateTime = (value: string | null): string =>
  value ? new Date(value).toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }) : '—';

const formatValue = (series: TrendSeries, value: number | null): string => {
  if (value === null) return '—';
  if (series.metric === 'price') return `$${value.toFixed(2)}`;
  if (series.metric === 'availability') {
    return { 1: 'found', 0: 'unknown', '-1': 'not found' }[String(value)] ?? String(value);
  }
  return String(value);
};

const SeriesTable = ({ data, loading }: { data: TrendListResponse | null; loading: boolean }) => {
  if (loading) {
    return <Box sx={{ p: 4, textAlign: 'center' }}><CircularProgress size={28} /></Box>;
  }
  if (!data) {
    // A failed load is not an empty history.
    return <Alert severity="warning">This signal could not be loaded, so nothing can be said about it.</Alert>;
  }
  if (data.series.length === 0) {
    return (
      <EmptyState
        title="Nothing recorded for this signal yet"
        description={data?.detail
          ?? 'Run Competitors or Products searches to begin building observation history.'}
        icon={<TrendingUpOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
      />
    );
  }

  return (
    <>
      {data.analyzable === 0 && data.detail && (
        <Alert severity="info" sx={{ mb: 2 }}>{data.detail}</Alert>
      )}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell />
              <TableCell>Subject</TableCell>
              <TableCell>Context</TableCell>
              <TableCell align="right">First</TableCell>
              <TableCell align="right">Latest</TableCell>
              <TableCell align="right">Change</TableCell>
              <TableCell align="right">Measurements</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Last observed</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.series.map((s, i) => (
              <TableRow key={`${s.subject}-${s.subject_id}-${i}`} hover>
                <TableCell><DirectionIcon series={s} /></TableCell>
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
                        ? `$${s.change_absolute.toFixed(2)}`
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
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
};

const Trends = () => {
  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [summary, setSummary] = useState<TrendSummaryResponse | null>(null);
  const [prices, setPrices] = useState<TrendListResponse | null>(null);
  const [availability, setAvailability] = useState<TrendListResponse | null>(null);
  const [visibility, setVisibility] = useState<TrendListResponse | null>(null);
  const [presence, setPresence] = useState<MerchantPresenceResponse | null>(null);

  // Everything here is a database read — no provider request, no credit.
  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      // Settled independently: one failing signal must not blank the others.
      const results = await Promise.allSettled([
        getTrendSummary(controller.signal),
        getPriceTrends({}, controller.signal),
        getAvailabilityTrends({}, controller.signal),
        getVisibilityTrends({ metric: 'position' }, controller.signal),
        getMerchantPresence({}, controller.signal),
      ]);
      // An aborted (StrictMode / unmounted) load must not touch state, or it
      // briefly reports "no history" while the real request is in flight.
      if (controller.signal.aborted) return;

      const [s, p, a, v, m] = results;
      if (s.status === 'fulfilled') setSummary(s.value);
      if (p.status === 'fulfilled') setPrices(p.value);
      if (a.status === 'fulfilled') setAvailability(a.value);
      if (v.status === 'fulfilled') setVisibility(v.value);
      if (m.status === 'fulfilled') setPresence(m.value);

      const failed = results.filter((r) => r.status === 'rejected') as PromiseRejectedResult[];
      if (failed.length) {
        const first = failed[0].reason;
        const detail = isAxiosError(first) ? first.response?.data?.detail : null;
        setError(
          (failed.length === results.length
            ? 'Trend data could not be loaded.'
            : `${failed.length} of ${results.length} trend signals could not be loaded.`)
          + (typeof detail === 'string' ? ` ${detail}`
            : isAxiosError(first) && !first.response ? ' Is the backend running?' : ''));
      }
      setLoading(false);
    };
    load();
    return () => controller.abort();
  }, []);

  const noHistory = summary
    && summary.competitor_observations === 0
    && summary.product_observations === 0;

  return (
    <Box>
      <PageHeader
        title="Trends"
        subtitle="Change over time, derived from observations already recorded by Competitors and Products."
      />

      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      {summary && (
        <>
          <Paper variant="outlined" elevation={0} sx={{ p: 2, mb: 3 }}>
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
      ) : !summary && error ? null : noHistory ? (
        <EmptyState
          title="No observation history yet"
          description="Trends are derived from what Competitors and Products have already recorded. Run a search in either module to begin building history — Trends itself makes no external requests."
          icon={<TrendingUpOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
        />
      ) : (
        <>
          <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
            <Tabs value={tab} onChange={(_, v) => setTab(v)}>
              <Tab label={`Prices (${prices?.total ?? 0})`} />
              <Tab label={`Availability (${availability?.total ?? 0})`} />
              <Tab label={`Visibility (${visibility?.total ?? 0})`} />
              <Tab label={`Merchant presence (${presence?.total ?? 0})`} />
              <Tab label={`Contexts (${summary?.contexts.length ?? 0})`} />
            </Tabs>
          </Box>

          {tab === 0 && <SeriesTable data={prices} loading={false} />}
          {tab === 1 && <SeriesTable data={availability} loading={false} />}
          {tab === 2 && <SeriesTable data={visibility} loading={false} />}

          {tab === 3 && (
            !presence ? (
              <Alert severity="warning">Merchant presence could not be loaded.</Alert>
            ) : presence.merchants.length > 0 ? (
              <TableContainer component={Paper}>
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
                title="No merchant history yet"
                description={presence?.detail ?? 'Run a Competitors search to begin recording merchant presence.'}
                icon={<TrendingUpOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
              />
            )
          )}

          {tab === 4 && summary && (
            <TableContainer component={Paper}>
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
