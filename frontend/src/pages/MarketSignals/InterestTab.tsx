import { useEffect, useRef, useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, Grid, List, ListItem, ListItemText,
  MenuItem, Paper, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, TextField, Typography,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import BookmarkAddOutlinedIcon from '@mui/icons-material/BookmarkAddOutlined';
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip as ChartTooltip,
  XAxis, YAxis,
} from 'recharts';

import EmptyState from '../../components/EmptyState/EmptyState';
import {
  getInterestByRegion, getRelatedQueries, getSearchInterest, saveSearch,
} from '../../services/intelligenceApi';
import type {
  InterestByRegion, InterestOverTime, RelatedQueries,
} from '../../types/intelligence';
import {
  errorMessage, formatDate, formatPercent, isCanceled,
} from '../../utils/format';

const MAX_TERMS = 5;
const GEO_PATTERN = /^[A-Z]{2}(-[A-Z0-9]{1,3}){0,2}$/;

const DATE_OPTIONS = [
  { value: 'now 7-d', label: 'Past 7 days' },
  { value: 'today 1-m', label: 'Past month' },
  { value: 'today 3-m', label: 'Past 3 months' },
  { value: 'today 12-m', label: 'Past 12 months' },
  { value: 'today 5-y', label: 'Past 5 years' },
];
const dateLabel = (value: string) => DATE_OPTIONS.find((o) => o.value === value)?.label ?? value;

const REGION_LEVELS = ['COUNTRY', 'REGION', 'DMA', 'CITY'];

const parseTerms = (raw: string): string[] => {
  const seen = new Set<string>();
  return raw.split(',').map((t) => t.trim()).filter((t) => {
    if (!t || seen.has(t.toLowerCase())) return false;
    seen.add(t.toLowerCase());
    return true;
  });
};

type ChartRow = { t: number } & Record<string, number | boolean | undefined>;

/**
 * One row per point date, merging every term. A partial (incomplete) point is
 * drawn on a separate dashed line joined to the last complete point, so the
 * solid line never suggests an incomplete period is final.
 */
const buildRows = (data: InterestOverTime): ChartRow[] => {
  const rows = new Map<number, ChartRow>();
  data.series.forEach((s) => {
    s.points.forEach((p, i) => {
      const t = new Date(p.date).getTime();
      const row = rows.get(t) ?? { t };
      const nextPartial = s.points[i + 1]?.partial ?? false;
      if (!p.partial) row[s.term] = p.value;
      if (p.partial || nextPartial) row[`${s.term}__partial`] = p.value;
      if (p.partial) row[`${s.term}__isPartial`] = true;
      rows.set(t, row);
    });
  });
  return [...rows.values()].sort((a, b) => a.t - b.t);
};

/** Live result metadata shown next to every live section. */
const LiveMeta = ({ cacheHit }: { cacheHit: boolean }) => (
  cacheHit ? <Chip size="small" label="Cached result" color="success" variant="outlined" /> : null
);

const InterestTab = ({ initialQuery }: { initialQuery: string }) => {
  const theme = useTheme();
  const palette = [
    theme.palette.primary.main, theme.palette.secondary.main, theme.palette.success.main,
    theme.palette.warning.main, theme.palette.error.main,
  ];

  const [termsInput, setTermsInput] = useState(initialQuery);
  const [geo, setGeo] = useState('');
  const [date, setDate] = useState('today 12-m');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<InterestOverTime | null>(null);

  const [regionLevel, setRegionLevel] = useState('');
  const [regionLoading, setRegionLoading] = useState(false);
  const [regionError, setRegionError] = useState<string | null>(null);
  const [regions, setRegions] = useState<InterestByRegion | null>(null);

  const [relatedLoading, setRelatedLoading] = useState(false);
  const [relatedError, setRelatedError] = useState<string | null>(null);
  const [related, setRelated] = useState<RelatedQueries | null>(null);

  const [saveMessage, setSaveMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  const controllers = useRef<Record<string, AbortController | undefined>>({});
  useEffect(() => {
    const active = controllers.current;
    return () => Object.values(active).forEach((c) => c?.abort());
  }, []);

  /** Aborts any earlier request of the same kind so a stale reply cannot land. */
  const begin = (key: string): AbortController => {
    controllers.current[key]?.abort();
    const controller = new AbortController();
    controllers.current[key] = controller;
    return controller;
  };

  const terms = parseTerms(termsInput);
  const geoValue = geo.trim().toUpperCase();
  const tooManyTerms = terms.length > MAX_TERMS;
  const geoInvalid = geoValue !== '' && !GEO_PATTERN.test(geoValue);

  const compare = async () => {
    if (terms.length === 0 || tooManyTerms || geoInvalid) return;
    const controller = begin('interest');
    // The secondary panels describe the previous comparison; clear them too.
    controllers.current.regions?.abort();
    controllers.current.related?.abort();
    setLoading(true);
    setError(null);
    setData(null);
    setRegions(null);
    setRegionError(null);
    setRelated(null);
    setRelatedError(null);
    setSaveMessage(null);
    try {
      const res = await getSearchInterest(
        { q: terms.join(','), geo: geoValue || undefined, date }, controller.signal);
      if (!controller.signal.aborted) setData(res);
    } catch (err) {
      if (!isCanceled(err)) setError(errorMessage(err));
    } finally {
      if (controllers.current.interest === controller) setLoading(false);
    }
  };

  // Secondary requests use the first term and the scope of the comparison on
  // screen, not whatever has been typed since.
  const scope = data ? { q: data.terms[0], geo: data.geo ?? undefined, date: data.date } : null;

  const loadRegions = async () => {
    if (!scope) return;
    const controller = begin('regions');
    setRegionLoading(true);
    setRegionError(null);
    setRegions(null);
    try {
      const res = await getInterestByRegion(
        { ...scope, region: regionLevel || undefined }, controller.signal);
      if (!controller.signal.aborted) setRegions(res);
    } catch (err) {
      if (!isCanceled(err)) setRegionError(errorMessage(err));
    } finally {
      if (controllers.current.regions === controller) setRegionLoading(false);
    }
  };

  const loadRelated = async () => {
    if (!scope) return;
    const controller = begin('related');
    setRelatedLoading(true);
    setRelatedError(null);
    setRelated(null);
    try {
      const res = await getRelatedQueries(scope, controller.signal);
      if (!controller.signal.aborted) setRelated(res);
    } catch (err) {
      if (!isCanceled(err)) setRelatedError(errorMessage(err));
    } finally {
      if (controllers.current.related === controller) setRelatedLoading(false);
    }
  };

  const handleSave = async () => {
    if (!data) return;
    setSaving(true);
    setSaveMessage(null);
    try {
      const res = await saveSearch({ module: 'interest', query: data.terms.join(', ') });
      setSaveMessage({ ok: true, text: res.created ? 'Search saved.' : 'This search was already saved.' });
    } catch (err) {
      setSaveMessage({ ok: false, text: errorMessage(err, 'The search could not be saved.') });
    } finally {
      setSaving(false);
    }
  };

  const rows = data ? buildRows(data) : [];
  const anyPartial = data?.series.some((s) => s.points.some((p) => p.partial)) ?? false;
  const maxRegion = regions ? Math.max(1, ...regions.regions.map((r) => r.value)) : 1;

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box component="form" onSubmit={(e) => { e.preventDefault(); compare(); }}>
          <Grid container spacing={2} sx={{ alignItems: 'flex-start' }}>
            <Grid size={{ xs: 12, md: 5 }}>
              <TextField
                fullWidth size="small" label="Terms" value={termsInput}
                onChange={(e) => setTermsInput(e.target.value)} disabled={loading}
                placeholder="e.g. cold brew, iced latte"
                error={tooManyTerms}
                helperText={tooManyTerms
                  ? `At most ${MAX_TERMS} terms can be compared (you entered ${terms.length}).`
                  : `Comma-separated, up to ${MAX_TERMS}.`}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 2 }}>
              <TextField
                fullWidth size="small" label="Geo (optional)" value={geo}
                onChange={(e) => setGeo(e.target.value)} disabled={loading}
                placeholder="US, US-NJ, IN" error={geoInvalid}
                helperText={geoInvalid ? 'Use a code like US, US-NJ or IN.' : 'Empty = worldwide'}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 2 }}>
              <TextField
                select fullWidth size="small" label="Time range" value={date}
                onChange={(e) => setDate(e.target.value)} disabled={loading}
              >
                {DATE_OPTIONS.map((o) => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>)}
              </TextField>
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <Button
                fullWidth type="submit" variant="contained" sx={{ height: 40 }}
                startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <ShowChartIcon />}
                disabled={loading || terms.length === 0 || tooManyTerms || geoInvalid}
              >
                Compare interest
              </Button>
            </Grid>
          </Grid>
        </Box>
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      {!data && !error && !loading && (
        <EmptyState
          title="Compare search interest"
          description="Enter up to five terms to see Google Trends interest over time. Nothing is requested until you click Compare interest."
          icon={<ShowChartIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
        />
      )}

      {data && (
        <>
          <Box sx={{ mb: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <Typography variant="h6" sx={{ flexGrow: 1 }}>
              {data.terms.join(' vs ')}
              <Typography component="span" variant="body2" color="text.secondary">
                {' '}· {data.geo ?? 'Worldwide'} · {dateLabel(data.date)}
              </Typography>
            </Typography>
            <LiveMeta cacheHit={data.cache_hit} />
            <Button size="small" variant="outlined" startIcon={<BookmarkAddOutlinedIcon />}
                    onClick={handleSave} disabled={saving}>
              Save search
            </Button>
          </Box>
          {saveMessage && (
            <Alert severity={saveMessage.ok ? 'success' : 'error'} sx={{ mb: 2 }}
                   onClose={() => setSaveMessage(null)}>
              {saveMessage.text}
            </Alert>
          )}

          <Alert severity="info" sx={{ mb: 2 }}>{data.disclaimer}</Alert>

          {!data.has_data ? (
            <EmptyState
              title="Google Trends returned no data points"
              description="The request succeeded, but there was not enough search volume for these terms in this place and time range."
              icon={<ShowChartIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
            />
          ) : (
            <>
              <Paper sx={{ p: 2, mb: 3 }}>
                <Box sx={{ width: '100%', height: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                      <XAxis
                        dataKey="t" type="number" scale="time" domain={['dataMin', 'dataMax']}
                        tickFormatter={(t: number) => formatDate(new Date(t).toISOString())}
                        tick={{ fontSize: 12 }} minTickGap={24}
                      />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} width={36} />
                      <ChartTooltip
                        content={({ active, payload }) => {
                          const row = payload?.[0]?.payload as ChartRow | undefined;
                          if (!active || !row) return null;
                          return (
                            <Paper sx={{ p: 1 }} elevation={3}>
                              <Typography variant="caption" sx={{ display: 'block', fontWeight: 600 }}>
                                {formatDate(new Date(row.t).toISOString())}
                              </Typography>
                              {data.series.map((s, i) => {
                                const value = row[s.term] ?? row[`${s.term}__partial`];
                                if (value === undefined) return null;
                                return (
                                  <Typography key={s.term} variant="caption"
                                              sx={{ display: 'block', color: palette[i % palette.length] }}>
                                    {s.term}: {String(value)}
                                    {row[`${s.term}__isPartial`] ? ' (partial)' : ''}
                                  </Typography>
                                );
                              })}
                            </Paper>
                          );
                        }}
                      />
                      <Legend />
                      {data.series.map((s, i) => (
                        <Line key={s.term} type="monotone" dataKey={s.term} name={s.term}
                              stroke={palette[i % palette.length]} strokeWidth={2} dot={false}
                              connectNulls isAnimationActive={false} />
                      ))}
                      {data.series.map((s, i) => (
                        <Line key={`${s.term}__partial`} type="monotone" dataKey={`${s.term}__partial`}
                              name={`${s.term} (partial)`} legendType="none"
                              stroke={palette[i % palette.length]} strokeWidth={2}
                              strokeDasharray="4 4" strokeOpacity={0.6} dot={false}
                              connectNulls isAnimationActive={false} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </Box>
                <Typography variant="caption" color="text.secondary">
                  Relative interest, 0–100, where 100 is the peak for these terms in this place
                  and range.
                  {anyPartial && ' The dashed segment marks the most recent period, which is still incomplete and may change.'}
                </Typography>
              </Paper>

              <TableContainer component={Paper} sx={{ mb: 3 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Term</TableCell>
                      <TableCell align="right">Average</TableCell>
                      <TableCell align="right">Latest</TableCell>
                      <TableCell>Peak date</TableCell>
                      <TableCell>Relative change</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.series.map((s, i) => (
                      <TableRow key={s.term}>
                        <TableCell>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Box sx={{ width: 10, height: 10, borderRadius: '50%', flexShrink: 0,
                                       bgcolor: palette[i % palette.length] }} />
                            <Typography variant="subtitle2">{s.term}</Typography>
                          </Box>
                        </TableCell>
                        <TableCell align="right">{s.average ?? '—'}</TableCell>
                        <TableCell align="right">{s.latest ?? '—'}</TableCell>
                        <TableCell>{formatDate(s.peak_date)}</TableCell>
                        <TableCell>
                          {s.relative_change_percent !== null ? formatPercent(s.relative_change_percent) : (
                            <Typography variant="caption" color="text.secondary">
                              {s.change_detail ?? '—'}
                            </Typography>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </>
          )}

          <Typography variant="h6" sx={{ mb: 0.5 }}>More about “{data.terms[0]}”</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
            Load either panel for more detail on this term.
          </Typography>
          <Grid container spacing={3}>
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper variant="outlined" sx={{ p: 2, height: '100%' }}>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 2 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600, flexGrow: 1 }}>
                    Interest by region
                  </Typography>
                  <TextField
                    select size="small" label="Level" value={regionLevel} sx={{ minWidth: 120 }}
                    onChange={(e) => setRegionLevel(e.target.value)} disabled={regionLoading}
                  >
                    <MenuItem value="">Default</MenuItem>
                    {REGION_LEVELS.map((r) => <MenuItem key={r} value={r}>{r}</MenuItem>)}
                  </TextField>
                  <Button size="small" variant="outlined" onClick={loadRegions} disabled={regionLoading}
                          startIcon={regionLoading ? <CircularProgress size={16} color="inherit" /> : undefined}>
                    Load regions
                  </Button>
                </Box>
                {regionError && <Alert severity="error">{regionError}</Alert>}
                {regions && (
                  <>
                    <Box sx={{ mb: 1 }}><LiveMeta cacheHit={regions.cache_hit} /></Box>
                    {regions.regions.length === 0 ? (
                      <Typography variant="body2" color="text.secondary">
                        The request succeeded but Google Trends reported no regional breakdown.
                      </Typography>
                    ) : (
                      <Box sx={{ maxHeight: 360, overflowY: 'auto' }}>
                        {regions.regions.map((r, i) => (
                          <Box key={`${r.geo ?? r.location}-${i}`} sx={{ mb: 1 }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
                              <Typography variant="body2" noWrap>{r.location ?? r.geo ?? '—'}</Typography>
                              <Typography variant="body2" color="text.secondary">{r.value}</Typography>
                            </Box>
                            <Box sx={{ height: 6, borderRadius: 1, bgcolor: 'action.hover' }}>
                              <Box sx={{ height: '100%', borderRadius: 1, bgcolor: 'primary.main',
                                         width: `${(r.value / maxRegion) * 100}%` }} />
                            </Box>
                          </Box>
                        ))}
                      </Box>
                    )}
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                      {regions.disclaimer}
                    </Typography>
                  </>
                )}
              </Paper>
            </Grid>

            <Grid size={{ xs: 12, md: 6 }}>
              <Paper variant="outlined" sx={{ p: 2, height: '100%' }}>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 2 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600, flexGrow: 1 }}>
                    Related queries
                  </Typography>
                  <Button size="small" variant="outlined" onClick={loadRelated} disabled={relatedLoading}
                          startIcon={relatedLoading ? <CircularProgress size={16} color="inherit" /> : undefined}>
                    Load related queries
                  </Button>
                </Box>
                {relatedError && <Alert severity="error">{relatedError}</Alert>}
                {related && (
                  <>
                    <Box sx={{ mb: 1 }}><LiveMeta cacheHit={related.cache_hit} /></Box>
                    <Grid container spacing={2}>
                      {([['Rising', related.rising, true], ['Top', related.top, false]] as const).map(
                        ([title, items, rising]) => (
                          <Grid size={{ xs: 12, sm: 6 }} key={title}>
                            <Typography variant="subtitle2">{title}</Typography>
                            {items.length === 0 ? (
                              <Typography variant="body2" color="text.secondary">None reported.</Typography>
                            ) : (
                              <List dense disablePadding>
                                {items.map((item, i) => (
                                  <ListItem key={`${item.query}-${i}`} disableGutters
                                            secondaryAction={
                                              <Typography variant="caption" color="text.secondary">
                                                {rising
                                                  ? (item.value_label ?? item.value ?? '—')
                                                  : (item.value ?? item.value_label ?? '—')}
                                              </Typography>
                                            }>
                                    <ListItemText primary={item.query} sx={{ pr: 6 }} />
                                  </ListItem>
                                ))}
                              </List>
                            )}
                          </Grid>
                        ))}
                    </Grid>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                      {related.detail}
                    </Typography>
                  </>
                )}
              </Paper>
            </Grid>
          </Grid>
        </>
      )}
    </Box>
  );
};

export default InterestTab;
