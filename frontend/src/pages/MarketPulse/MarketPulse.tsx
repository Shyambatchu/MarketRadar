import { useState, useEffect } from 'react';
import {
  Alert, Autocomplete, Box, Button, Chip, CircularProgress, Grid, Link, Paper,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tab, Tabs,
  TextField, Tooltip, Skeleton, Typography,
} from '@mui/material';
import InsightsOutlinedIcon from '@mui/icons-material/InsightsOutlined';
import SearchIcon from '@mui/icons-material/Search';

import { errorMessage, formatMoney, humanize, isCanceled } from '../../utils/format';
import PageHeader from '../../components/PageHeader/PageHeader';
import EmptyState from '../../components/EmptyState/EmptyState';
import { getMarketPulse, getMarketPulseOptions } from '../../services/marketPulseApi';
import type {
  MarketOption, MarketPulseResponse, PriceEntry,
} from '../../types/marketPulse';
import type { TrendSeries } from '../../types/trend';

/** Status colours describe evidence strength, never business quality. */
const STATUS_COLOR: Record<string, 'success' | 'info' | 'warning' | 'default'> = {
  verified: 'success', discovered: 'info', uncertain: 'warning',
  found: 'success', not_found: 'warning', unknown: 'default',
  unavailable: 'warning', trend: 'success', insufficient_history: 'default',
};

const STATUS_HELP: Record<string, string> = {
  verified: 'Identified from a structured local listing, or corroborated by two independent sources.',
  discovered: 'A real business, but the evidence so far is a single organic result.',
  uncertain: 'The evidence could not reliably distinguish this from another business.',
  found: 'The merchant\'s own site identifies this product.',
  not_found: 'A result specifically contradicted the request — a different size, variant or model.',
  unknown: 'Not enough evidence either way. This is not a claim that the product is unavailable.',
  unavailable: 'Product evidence exists, but no price could be attributed to this exact product.',
};

const SOURCE_LABEL: Record<string, string> = {
  google_maps_local: 'Google Local',
  google_organic: 'Google Organic',
  indexed_search: 'Indexed Search',
};

const formatDate = (value: string | null): string =>
  value ? new Date(value).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  }) : '—';

// The ordinal the backend uses to detect availability changes. It is not a
// score, so it is shown as its label, never as a number.
const AVAILABILITY_LABEL: Record<string, string> = {
  '1': 'found', '0': 'unknown', '-1': 'not_found',
};

/**
 * Price trend series carry no currency of their own. It is taken from the
 * verified price rows for the same product and merchant only when those rows
 * agree on exactly one currency; otherwise the bare number is shown.
 */
const seriesCurrency = (series: TrendSeries, prices: PriceEntry[]): string | null => {
  const currencies = new Set(
    prices
      .filter((p) => (p.product_name || p.product_query) === series.subject
        && (!p.merchant || !series.context || series.context.startsWith(p.merchant)))
      .map((p) => p.currency)
      .filter((c): c is string => Boolean(c)),
  );
  return currencies.size === 1 ? [...currencies][0] : null;
};

const formatTrendValue = (
  series: TrendSeries, which: 'first' | 'last', prices: PriceEntry[],
): string => {
  const value = which === 'first' ? series.first_value : series.last_value;
  if (value === null) return '—';
  switch (series.metric) {
    case 'price':
      return formatMoney(value, seriesCurrency(series, prices));
    case 'availability': {
      const point = which === 'first' ? series.points[0] : series.points[series.points.length - 1];
      return humanize(point?.label ?? AVAILABILITY_LABEL[String(value)] ?? String(value));
    }
    default:
      return String(value);
  }
};

const optionLabel = (o: MarketOption): string =>
  `${o.market ?? 'Unspecified market'} — ${o.location ?? 'no location'}`;

const StatusChip = ({ value }: { value: string }) => (
  <Tooltip title={STATUS_HELP[value] ?? ''}>
    <Chip size="small" variant="outlined" label={value.replace(/_/g, ' ')}
          color={STATUS_COLOR[value] ?? 'default'} />
  </Tooltip>
);

const MarketPulse = () => {
  const [options, setOptions] = useState<MarketOption[]>([]);
  const [selected, setSelected] = useState<MarketOption | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<MarketPulseResponse | null>(null);
  const [tab, setTab] = useState(0);

  // Reading a snapshot is a database read, so it loads as soon as a market is
  // chosen; there is nothing to confirm before spending.
  const load = async (option: MarketOption | null = selected) => {
    if (!option) return;
    setLoading(true);
    setError(null);
    // A failed reload must not leave the previous context on screen.
    setData(null);
    try {
      setData(await getMarketPulse({
        market: option.market ?? undefined,
        location: option.location ?? undefined,
      }));
    } catch (err) {
      setError(errorMessage(err, 'Unable to load the market snapshot.'));
    } finally {
      setLoading(false);
    }
  };

  // Choices come from history, so a selection always refers to something
  // actually observed. No market category is invented.
  useEffect(() => {
    const controller = new AbortController();
    getMarketPulseOptions(controller.signal)
      .then((res) => {
        setOptions(res.options);
        // Open on the most recently observed market rather than an empty page.
        const selectable = res.options.filter((o) => o.market && o.location)
          .sort((a, b) => (b.last_observed_at ?? '').localeCompare(a.last_observed_at ?? ''));
        if (selectable.length > 0) {
          setSelected(selectable[0]);
          load(selectable[0]);
        }
      })
      .catch((err) => {
        if (!isCanceled(err)) {
          setError(errorMessage(err, 'Unable to load observed markets. Is the backend running?'));
        }
      })
      // An aborted (StrictMode) request must not end the loading state early.
      .finally(() => { if (!controller.signal.aborted) setLoadingOptions(false); });
    return () => controller.abort();
  }, []);

  const quality = data?.data_quality;

  return (
    <Box>
      <PageHeader
        title="Market Pulse"
        subtitle="A factual snapshot of one market and location, derived from observations already recorded."
      />

      <Paper sx={{ p: 3, mb: 4 }}>
        <Grid container spacing={2} sx={{ alignItems: 'center' }}>
          <Grid size={{ xs: 12, sm: 9 }}>
            <Autocomplete
              size="small"
              options={options}
              value={selected}
              onChange={(_, v) => { setSelected(v); setData(null); setError(null); if (v) load(v); }}
              // An option missing its market or location cannot be requested
              // on its own: omitting the filter would load every market.
              getOptionDisabled={(o) => !o.market || !o.location}
              getOptionLabel={optionLabel}
              isOptionEqualToValue={(a, b) =>
                a.market === b.market && a.location === b.location}
              loading={loadingOptions}
              renderInput={(params) => (
                <TextField {...params} label="Market / Industry and Location"
                           placeholder={loadingOptions
                             ? 'Loading observed markets…'
                             : 'Select an observed market and location'} />
              )}
              renderOption={(props, o) => (
                <li {...props} key={`${o.market}-${o.location}`}>
                  <Box>
                    <Typography variant="body2">{o.market ?? 'Unspecified market'}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {o.location ?? 'no location'} · {o.merchants} merchant(s) ·{' '}
                      {o.competitor_observations} competitor ·{' '}
                      {o.product_observations} product observation(s)
                    </Typography>
                  </Box>
                </li>
              )}
              noOptionsText="No markets have been observed yet."
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 3 }}>
            <Button
              fullWidth sx={{ height: 40 }}
              startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SearchIcon />}
              onClick={() => load()} disabled={loading || loadingOptions || !selected}
              variant="outlined"
            >
              Refresh
            </Button>
          </Grid>
        </Grid>
        {!loadingOptions && options.length === 0 && (
          <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
            Market Pulse reads history that Competitors and Products record. Run a
            search in either module to populate it — Market Pulse makes no
            external requests of its own.
          </Typography>
        )}
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      {loading && !data && (
        <Box aria-busy="true" aria-label="Loading snapshot">
          <Grid container spacing={2} sx={{ mb: 3 }}>
            {[0, 1, 2, 3].map((i) => (
              <Grid key={i} size={{ xs: 6, md: 3 }}><Skeleton variant="rounded" height={88} /></Grid>
            ))}
          </Grid>
          <Skeleton variant="rounded" height={40} sx={{ mb: 2 }} />
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} variant="rounded" height={44} sx={{ mb: 1 }} />)}
        </Box>
      )}

      {data && !data.has_data && (
        <EmptyState
          title="No observations for this selection"
          description={data.detail ?? 'Nothing has been recorded for this market and location yet.'}
          icon={<InsightsOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
        />
      )}

      {data && data.has_data && (
        <>
          {/* ---- 1. MARKET CONTEXT ---- */}
          <Paper variant="outlined" elevation={0} sx={{ p: 2, mb: 3 }}>
            <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
              {data.context.market ?? 'All markets'}
              {data.context.location ? ` · ${data.context.location}` : ''}
            </Typography>
            <Grid container spacing={2}>
              {[
                ['Merchants', data.context.merchants],
                ['Competitor observations', data.context.competitor_observations],
                ['Product observations', data.context.product_observations],
                ['Distinct searches', data.context.distinct_searches],
                ['First observed', formatDate(data.context.first_observed_at)],
                ['Last observed', formatDate(data.context.last_observed_at)],
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

          {/* ---- 7. DATA QUALITY ---- */}
          {quality && (
            <Paper variant="outlined" elevation={0} sx={{ p: 2, mb: 3 }}>
              <Typography variant="subtitle2" sx={{ mb: 1.5 }}>Evidence quality</Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: quality.notes.length ? 2 : 0 }}>
                {[
                  [`${quality.competitors_verified} verified`, 'verified'],
                  [`${quality.competitors_discovered} discovered`, 'discovered'],
                  [`${quality.competitors_uncertain} uncertain`, 'uncertain'],
                  [`${quality.products_found} product found`, 'found'],
                  [`${quality.products_unknown} product unknown`, 'unknown'],
                  [`${quality.prices_verified} price verified`, 'verified'],
                  [`${quality.prices_unavailable} price unavailable`, 'unavailable'],
                  [`${quality.trend_series_with_direction}/${quality.trend_series} trend direction`, 'trend'],
                ].map(([label, kind]) => (
                  <Chip key={label} size="small" variant="outlined" label={label}
                        color={STATUS_COLOR[kind as string] ?? 'default'} />
                ))}
              </Box>
              {quality.notes.map((note, i) => (
                <Alert key={i} severity="info" sx={{ mt: 1 }}>{note}</Alert>
              ))}
            </Paper>
          )}

          <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
            <Tabs value={tab} onChange={(_, v) => setTab(v)}>
              <Tab label={`Competitors (${data.competitors.length})`} />
              <Tab label={`Products (${data.products.length})`} />
              <Tab label={`Prices (${data.prices.length})`} />
              <Tab label={`Visibility (${data.visibility.length})`} />
              <Tab label={`Trends (${data.trends.length})`} />
            </Tabs>
          </Box>

          {/* ---- 2. COMPETITOR LANDSCAPE ---- */}
          {tab === 0 && (
            data.competitors.length === 0 ? (
              <EmptyState title="No competitor observations in this context"
                          description="Run a Competitors search for this market and location to record businesses."
                          icon={<InsightsOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />} />
            ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Business</TableCell>
                    <TableCell>Domain</TableCell>
                    <TableCell>Source</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>First seen</TableCell>
                    <TableCell>Last seen</TableCell>
                    <TableCell>In latest</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.competitors.map((c, i) => (
                    <TableRow key={c.merchant_id ?? `c-${i}`} hover>
                      <TableCell>
                        <Typography variant="subtitle2">{c.name}</Typography>
                        {!c.has_location_evidence && (
                          <Typography variant="caption" color="warning.main">
                            Location not verified
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        {c.domain ? (
                          <Link href={c.website ?? `https://${c.domain}`}
                                target="_blank" rel="noopener" underline="hover">
                            {c.domain}
                          </Link>
                        ) : (
                          <Typography variant="caption" color="text.disabled">Not reported</Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {c.discovery_methods.map((m) => SOURCE_LABEL[m] ?? m).join(' + ') || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell><StatusChip value={c.status} /></TableCell>
                      <TableCell>
                        <Typography variant="caption">{formatDate(c.first_seen_at)}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption">{formatDate(c.last_seen_at)}</Typography>
                      </TableCell>
                      <TableCell>
                        <Tooltip title={c.presence_note ?? ''}>
                          <Chip size="small" variant="outlined"
                                label={c.present_in_latest ? 'present' : 'not in latest'}
                                color={c.present_in_latest ? 'success' : 'warning'} />
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            )
          )}

          {/* ---- 3. PRODUCT SIGNALS ---- */}
          {tab === 1 && (
            data.products.length === 0 ? (
              <EmptyState title="No product observations in this context"
                          description="Run a Products search for this market and location to record product evidence."
                          icon={<InsightsOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />} />
            ) : (
              <TableContainer component={Paper}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Product</TableCell>
                      <TableCell>Merchant</TableCell>
                      <TableCell>Size</TableCell>
                      <TableCell>Evidence</TableCell>
                      <TableCell>Product status</TableCell>
                      <TableCell>Price status</TableCell>
                      <TableCell>Observed</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.products.map((p) => (
                      <TableRow key={p.observation_id} hover>
                        <TableCell>
                          <Typography variant="subtitle2">
                            {p.product_name || p.product_query}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{p.merchant ?? '—'}</Typography>
                        </TableCell>
                        <TableCell>
                          {p.observed_size ? (
                            <Chip size="small" variant="outlined" label={p.observed_size}
                                  color={p.size_confirmed ? 'default' : 'warning'} />
                          ) : '—'}
                        </TableCell>
                        <TableCell>
                          <Tooltip title={p.inventory_confirmed
                            ? 'Evidence covers stock at a specific physical store.'
                            : 'A catalogue listing. It shows the merchant offers the product — not that a physical store holds stock.'}>
                            <Chip size="small" variant="outlined"
                                  label={p.evidence_scope === 'catalog' ? 'Catalogue' : p.evidence_scope} />
                          </Tooltip>
                        </TableCell>
                        <TableCell><StatusChip value={p.product_status} /></TableCell>
                        <TableCell>
                          <Tooltip title={p.verification_reason
                            ? p.verification_reason.replace(/_/g, ' ')
                            : STATUS_HELP[p.price_status] ?? ''}>
                            <Chip size="small" variant="outlined"
                                  label={p.price_status}
                                  color={STATUS_COLOR[p.price_status] ?? 'default'} />
                          </Tooltip>
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption">{formatDate(p.observed_at)}</Typography>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )
          )}

          {/* ---- 4. PRICE SIGNALS ---- */}
          {tab === 2 && (
            <>
              <Alert severity={data.price_statistics.sufficient ? 'success' : 'info'} sx={{ mb: 2 }}>
                {data.price_statistics.detail ?? 'No verified price observations.'}
                {data.price_statistics.sufficient && (
                  <Box sx={{ mt: 1 }}>
                    Lowest {formatMoney(data.price_statistics.lowest, data.price_statistics.currency)} ·
                    {' '}Average {formatMoney(data.price_statistics.average, data.price_statistics.currency)} ·
                    {' '}Highest {formatMoney(data.price_statistics.highest, data.price_statistics.currency)}
                  </Box>
                )}
              </Alert>
              {data.prices.length === 0 ? (
                <EmptyState title="No verified prices in this context"
                            description="Only verified prices appear here. A price that could not be attributed to the exact product is never counted."
                            icon={<InsightsOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />} />
              ) : (
                <TableContainer component={Paper}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Product</TableCell>
                        <TableCell>Merchant</TableCell>
                        <TableCell align="right">Price</TableCell>
                        <TableCell>Evidence</TableCell>
                        <TableCell>Source</TableCell>
                        <TableCell>Observed</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {data.prices.map((p) => (
                        <TableRow key={p.observation_id} hover>
                          <TableCell>
                            <Typography variant="subtitle2">
                              {p.product_name || p.product_query}
                            </Typography>
                            {p.observed_size && (
                              <Typography variant="caption" color="text.secondary">
                                {p.observed_size}
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell>{p.merchant ?? '—'}</TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" color="success.main">
                              {formatMoney(p.price, p.currency)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip size="small" variant="outlined"
                                  label={p.evidence_scope === 'catalog' ? 'Catalogue' : p.evidence_scope} />
                          </TableCell>
                          <TableCell>
                            {p.source_url ? (
                              <Link href={p.source_url} target="_blank" rel="noopener" underline="hover">
                                {p.source_domain ?? 'source'}
                              </Link>
                            ) : '—'}
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption">{formatDate(p.observed_at)}</Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </>
          )}

          {/* ---- 5. VISIBILITY SIGNALS ---- */}
          {tab === 3 && (
            data.visibility.length === 0 ? (
              <EmptyState title="No visibility measurements in this context"
                          description="Search positions and ratings come from Competitors searches."
                          icon={<InsightsOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />} />
            ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Business</TableCell>
                    <TableCell align="right">Best position</TableCell>
                    <TableCell align="right">Latest position</TableCell>
                    <TableCell align="right">Rating</TableCell>
                    <TableCell align="right">Reviews</TableCell>
                    <TableCell align="right">Observations</TableCell>
                    <TableCell>Last observed</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.visibility.map((v, i) => (
                    <TableRow key={v.merchant_id ?? `v-${i}`} hover>
                      <TableCell>
                        <Typography variant="subtitle2">{v.merchant}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {v.domain ?? 'No domain reported'}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">{v.best_position ?? '—'}</TableCell>
                      <TableCell align="right">{v.latest_position ?? '—'}</TableCell>
                      <TableCell align="right">{v.rating ?? '—'}</TableCell>
                      <TableCell align="right">{v.reviews ?? '—'}</TableCell>
                      <TableCell align="right">{v.observation_count}</TableCell>
                      <TableCell>
                        <Typography variant="caption">{formatDate(v.observed_at)}</Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            )
          )}

          {/* ---- 6. TREND SIGNALS ---- */}
          {tab === 4 && (
            data.trends.length === 0 ? (
              <EmptyState title="No trend signals in this context"
                          description="Trends need observations recorded over time for this market and location."
                          icon={<InsightsOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />} />
            ) : (
              <>
                {quality && quality.trend_series_with_direction === 0 && (
                  <Alert severity="info" sx={{ mb: 2 }}>
                    No direction can be stated yet. Every series holds a single
                    distinct measurement — repeating a search inside the response
                    cache returns identical readings, which is not a second
                    measurement.
                  </Alert>
                )}
                <TableContainer component={Paper}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Subject</TableCell>
                        <TableCell>Metric</TableCell>
                        <TableCell>Context</TableCell>
                        <TableCell align="right">First</TableCell>
                        <TableCell align="right">Latest</TableCell>
                        <TableCell align="right">Measurements</TableCell>
                        <TableCell>Status</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {data.trends.map((t, i) => (
                        <TableRow key={`${t.subject}-${t.metric}-${i}`} hover>
                          <TableCell>
                            <Typography variant="subtitle2">{t.subject}</Typography>
                          </TableCell>
                          <TableCell>
                            <Chip size="small" variant="outlined" label={t.metric} />
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption" color="text.secondary">
                              {t.context ?? '—'}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">{formatTrendValue(t, 'first', data.prices)}</TableCell>
                          <TableCell align="right">{formatTrendValue(t, 'last', data.prices)}</TableCell>
                          <TableCell align="right">
                            <Tooltip title={`${t.distinct_points} distinct measurement(s) from ${t.raw_observations} stored observation(s).`}>
                              <Typography variant="body2">
                                {t.distinct_points}
                                <Typography component="span" variant="caption" color="text.secondary">
                                  {' '}/ {t.raw_observations}
                                </Typography>
                              </Typography>
                            </Tooltip>
                          </TableCell>
                          <TableCell>
                            <Tooltip title={t.detail ?? ''}>
                              <Chip size="small" variant="outlined"
                                    label={t.status === 'trend' && t.direction
                                      ? `${t.direction}`
                                      : t.status.replace(/_/g, ' ')}
                                    color={STATUS_COLOR[t.status] ?? 'default'} />
                            </Tooltip>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </>
            )
          )}
        </>
      )}

      {!data && !error && !loadingOptions && options.length > 0 && (
        <EmptyState
          title="Select a market and location"
          description="Market Pulse assembles what was observed for one market and place. Choose one above and load its snapshot."
          icon={<InsightsOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
        />
      )}
    </Box>
  );
};

export default MarketPulse;
