import { useEffect, useMemo, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import {
  Alert, Autocomplete, Box, Chip, Grid, Link, List, ListItem, ListItemText, MenuItem,
  Paper, Skeleton, TextField, Tooltip as MuiTooltip, Typography,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import SearchOutlinedIcon from '@mui/icons-material/SearchOutlined';
import StorefrontOutlinedIcon from '@mui/icons-material/StorefrontOutlined';
import TrendingUpOutlinedIcon from '@mui/icons-material/TrendingUpOutlined';
import AttachMoneyOutlinedIcon from '@mui/icons-material/AttachMoneyOutlined';
import Inventory2OutlinedIcon from '@mui/icons-material/Inventory2Outlined';
import InsightsOutlinedIcon from '@mui/icons-material/InsightsOutlined';
import PsychologyOutlinedIcon from '@mui/icons-material/PsychologyOutlined';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import InsertChartOutlinedIcon from '@mui/icons-material/InsertChartOutlined';
import PlaceOutlinedIcon from '@mui/icons-material/PlaceOutlined';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import LightbulbOutlinedIcon from '@mui/icons-material/LightbulbOutlined';
import SensorsOutlinedIcon from '@mui/icons-material/SensorsOutlined';
import CircleIcon from '@mui/icons-material/Circle';

import MetricCard from '../../components/MetricCard/MetricCard';
import { getTrendSummary } from '../../services/trendApi';
import { getMarketPulseOptions } from '../../services/marketPulseApi';
import { getDashboard } from '../../services/intelligenceApi';
import { beginNavigation } from '../../services/loadingTracker';
import type { TrendSummaryResponse } from '../../types/trend';
import type { MarketOption } from '../../types/marketPulse';
import type { DashboardSummary, PriceAlert } from '../../types/intelligence';
import {
  errorMessage, formatDate, formatDateTime, formatMoney, formatPercent, humanize, isCanceled,
} from '../../utils/format';

interface ContextRow {
  name: string;
  competitors: number;
  products: number;
}

/** Observations per market + location, split by the module that recorded them. */
const toContextRows = (summary: TrendSummaryResponse): ContextRow[] => {
  const rows = new Map<string, ContextRow>();
  for (const c of summary.contexts) {
    const name = [c.market || 'Unlabelled', c.location].filter(Boolean).join(' · ');
    const row = rows.get(name) ?? { name, competitors: 0, products: 0 };
    if (c.source === 'products') row.products += c.observations;
    else row.competitors += c.observations;
    rows.set(name, row);
  }
  return [...rows.values()]
    .sort((a, b) => (b.competitors + b.products) - (a.competitors + a.products))
    .slice(0, 6);
};

const PERIODS = [
  { value: 0, label: 'All time' },
  { value: 7, label: 'Last 7 days' },
  { value: 30, label: 'Last 30 days' },
  { value: 90, label: 'Last 90 days' },
];

const ALERT_COLOR: Record<string, 'error' | 'success' | 'warning' | 'info' | 'default'> = {
  price_increase: 'error',
  price_decrease: 'success',
  outlier: 'warning',
  conflicting_prices: 'warning',
  new_offer: 'info',
};

const changeLine = (a: PriceAlert): string => {
  if (a.previous_price !== null && a.current_price !== null) {
    return `${formatMoney(a.previous_price, a.currency)} → ${formatMoney(a.current_price, a.currency)}`
      + (a.change_percent !== null ? ` (${formatPercent(a.change_percent)})` : '');
  }
  if (a.current_price !== null) return formatMoney(a.current_price, a.currency);
  if (a.previous_price !== null) return `last seen at ${formatMoney(a.previous_price, a.currency)}`;
  return '';
};

const optionLabel = (o: MarketOption) =>
  `${o.market ?? 'Unlabelled'}${o.location ? ` · ${o.location}` : ''}`;

const Dashboard = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const [summary, setSummary] = useState<TrendSummaryResponse | null>(null);
  const [summaryFailed, setSummaryFailed] = useState(false);
  const [options, setOptions] = useState<MarketOption[]>([]);
  const [selected, setSelected] = useState<MarketOption | null>(null);
  const [days, setDays] = useState(0);
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(true);

  // Database reads only: no provider request, no credit.
  useEffect(() => {
    const controller = new AbortController();
    getTrendSummary(controller.signal)
      .then(setSummary)
      .catch(() => { if (!controller.signal.aborted) setSummaryFailed(true); });
    getMarketPulseOptions(controller.signal)
      .then((data) => setOptions(data.options))
      .catch(() => { /* filters fall back to "all markets" */ });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    getDashboard({
      market: selected?.market ?? undefined,
      location: selected?.location ?? undefined,
      days: days || undefined,
    }, controller.signal)
      .then(setDashboard)
      .catch((err) => { if (!isCanceled(err)) setDashboardError(errorMessage(err)); })
      .finally(() => { if (!controller.signal.aborted) setDashboardLoading(false); });
    return () => controller.abort();
  }, [selected, days]);

  // A filter change starts a new load; the effect above performs it.
  const changeFilters = (next: { selected?: MarketOption | null; days?: number }) => {
    setDashboardLoading(true);
    setDashboardError(null);
    if (next.selected !== undefined) setSelected(next.selected);
    if (next.days !== undefined) setDays(next.days);
  };

  const contextRows = summary ? toContextRows(summary) : [];
  const hasHistory = !!summary
    && (summary.competitor_observations > 0 || summary.product_observations > 0);
  const counts = dashboard?.counts;
  const filtered = !!selected || days > 0;

  const metrics = useMemo(() => counts ? [
    { title: 'Businesses tracked', value: counts.businesses,
      subtitle: `${counts.confirmed_competitors} confirmed as competitors`,
      icon: <StorefrontOutlinedIcon /> },
    { title: 'Markets observed', value: counts.markets,
      subtitle: `${counts.competitor_observations} competitor observations`,
      icon: <PlaceOutlinedIcon /> },
    { title: 'Products found', value: counts.products_found,
      subtitle: `${counts.product_observations} catalogue checks`,
      icon: <Inventory2OutlinedIcon /> },
    { title: 'Verified prices', value: counts.verified_prices,
      subtitle: 'single-product page or matched listing',
      icon: <FactCheckOutlinedIcon /> },
  ] : [], [counts]);

  const cards = [
    { title: 'Market Research', description: 'Search results, related questions and local businesses for any query.',
      icon: <SearchOutlinedIcon sx={{ color: 'primary.main', fontSize: 28 }} />, path: '/research', iconBg: 'primary.light' },
    { title: 'Competitors', description: 'Identify, review and track the businesses competing in a market and place.',
      icon: <StorefrontOutlinedIcon sx={{ color: 'success.dark', fontSize: 28 }} />, path: '/competitors', iconBg: 'success.light' },
    { title: 'Products', description: "Check which merchants' catalogues list a product, and at what verified price.",
      icon: <Inventory2OutlinedIcon sx={{ color: 'info.dark', fontSize: 28 }} />, path: '/products', iconBg: 'info.light' },
    { title: 'Price Intelligence', description: 'Compare verified local prices and review detected price changes.',
      icon: <AttachMoneyOutlinedIcon sx={{ color: 'secondary.dark', fontSize: 28 }} />, path: '/prices', iconBg: 'secondary.light' },
    { title: 'Market Signals', description: 'Relative search interest (Google Trends) and market news.',
      icon: <SensorsOutlinedIcon sx={{ color: 'warning.dark', fontSize: 28 }} />, path: '/signals', iconBg: 'warning.light' },
    { title: 'Trends', description: 'What changed between distinct measurements, and what cannot be compared yet.',
      icon: <TrendingUpOutlinedIcon sx={{ color: 'warning.dark', fontSize: 28 }} />, path: '/trends', iconBg: 'warning.light' },
    { title: 'Market Pulse', description: 'A factual snapshot of one observed market and location.',
      icon: <InsightsOutlinedIcon sx={{ color: 'primary.dark', fontSize: 28 }} />, path: '/pulse', iconBg: 'primary.light' },
    { title: 'AI Analyst', description: 'Ask questions answered only from stored, cited evidence.',
      icon: <PsychologyOutlinedIcon sx={{ color: 'success.dark', fontSize: 28 }} />, path: '/analyst', iconBg: 'success.light' },
  ];

  const health = dashboard?.health;
  const freshness = dashboard?.freshness;

  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', mt: 2 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h1" sx={{ fontSize: { xs: '1.75rem', md: '2.25rem' }, mb: 1, color: 'text.primary' }}>
          Welcome to MarketRadar
        </Typography>
        <Typography variant="subtitle1" color="text.secondary" sx={{ fontSize: '1.125rem' }}>
          Monitor markets, competitors, pricing, trends and search visibility.
        </Typography>
        {freshness?.last_observed_at && (
          <Typography variant="caption" color="text.secondary">
            Latest observation {formatDateTime(freshness.last_observed_at)}
          </Typography>
        )}
      </Box>

      {/* Filters narrow the evidence sections; usage and health are installation-wide. */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} sx={{ alignItems: 'center' }}>
          <Grid size={{ xs: 12, sm: 7 }}>
            <Autocomplete
              size="small" options={options} value={selected}
              onChange={(_, value) => changeFilters({ selected: value })}
              getOptionLabel={optionLabel}
              isOptionEqualToValue={(a, b) => a.market === b.market && a.location === b.location}
              renderInput={(params) => (
                <TextField {...params} label="Market and location" placeholder="All observed markets" />
              )}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 3 }}>
            <TextField
              select fullWidth size="small" label="Period" value={days}
              onChange={(e) => changeFilters({ days: Number(e.target.value) })}
            >
              {PERIODS.map((p) => <MenuItem key={p.value} value={p.value}>{p.label}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid size={{ xs: 12, sm: 2 }}>
            <Typography variant="caption" color="text.secondary">
              {filtered ? 'Filtered view' : 'All evidence'}
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      {dashboardError && <Alert severity="error" sx={{ mb: 3 }}>{dashboardError}</Alert>}

      <Grid container spacing={3} sx={{ mb: 3 }}>
        {dashboardLoading && !dashboard
          ? [0, 1, 2, 3].map((i) => (
            <Grid key={i} size={{ xs: 12, sm: 6, md: 3 }}>
              <Skeleton variant="rounded" height={140} />
            </Grid>
          ))
          : metrics.map((m) => (
            <Grid key={m.title} size={{ xs: 12, sm: 6, md: 3 }}>
              <MetricCard {...m} />
            </Grid>
          ))}
      </Grid>

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 7 }}>
          <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', mb: 1 }}>
              <Typography variant="subtitle2" color="text.secondary" sx={{ fontWeight: 600 }}>
                Recent price changes
              </Typography>
              <Link component={RouterLink} to="/prices" variant="caption">All price changes</Link>
            </Box>
            {dashboardLoading && !dashboard ? (
              <Skeleton variant="rounded" height={180} />
            ) : dashboard && dashboard.recent_changes.length > 0 ? (
              <List dense disablePadding>
                {dashboard.recent_changes.map((a, i) => (
                  <ListItem key={i} disableGutters divider={i < dashboard.recent_changes.length - 1}>
                    <ListItemText
                      primary={(
                        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                          <Chip size="small" label={humanize(a.type)} color={ALERT_COLOR[a.type] ?? 'default'}
                                variant="outlined" />
                          <Typography variant="body2" sx={{ fontWeight: 500 }}>
                            {a.product}{a.merchant ? ` · ${a.merchant}` : ''}
                          </Typography>
                        </Box>
                      )}
                      secondary={`${changeLine(a)}${a.location ? ` · ${a.location}` : ''}`
                        + ` · ${formatDate(a.observed_at ?? a.previous_observed_at)}`}
                    />
                  </ListItem>
                ))}
              </List>
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>
                No price change met the detection thresholds{filtered ? ' for this selection' : ''}.
                A change needs two distinct verified readings at one merchant.
              </Typography>
            )}
            {dashboard && dashboard.recent_changes_total > dashboard.recent_changes.length && (
              <Typography variant="caption" color="text.secondary">
                Showing {dashboard.recent_changes.length} of {dashboard.recent_changes_total}.
              </Typography>
            )}
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 5 }}>
          <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', mb: 1 }}>
              <Typography variant="subtitle2" color="text.secondary" sx={{ fontWeight: 600 }}>
                Top opportunities
              </Typography>
              <Link component={RouterLink} to="/opportunities" variant="caption">Review all</Link>
            </Box>
            {dashboardLoading && !dashboard ? (
              <Skeleton variant="rounded" height={180} />
            ) : dashboard && dashboard.top_opportunities.length > 0 ? (
              <List dense disablePadding>
                {dashboard.top_opportunities.map((o) => (
                  <ListItem key={o.id} disableGutters>
                    <MuiTooltip title="Ranking score out of 100 — not a probability of success">
                      <Chip size="small" label={o.score.toFixed(0)} color="primary"
                            sx={{ mr: 1.5, minWidth: 44 }} />
                    </MuiTooltip>
                    <ListItemText primary={o.title}
                                  secondary={`${humanize(o.category)} · ${o.confidence} confidence`} />
                  </ListItem>
                ))}
              </List>
            ) : (
              <Box sx={{ py: 2 }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  No opportunities yet. They are built from stored price changes and search-interest signals.
                </Typography>
                <Link component={RouterLink} to="/opportunities" variant="body2">
                  <LightbulbOutlinedIcon fontSize="inherit" sx={{ mr: 0.5, verticalAlign: 'middle' }} />
                  Generate opportunities
                </Link>
              </Box>
            )}
          </Paper>
        </Grid>
      </Grid>

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12 }}>
          <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, fontWeight: 600 }}>
              Observations by market (all evidence)
            </Typography>
            {!summary && !summaryFailed ? (
              <Skeleton variant="rounded" height={220} />
            ) : hasHistory && contextRows.length > 0 ? (
              <Box sx={{ width: '100%', height: Math.max(160, contextRows.length * 52 + 60) }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={contextRows} layout="vertical"
                            margin={{ top: 0, right: 16, bottom: 0, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false}
                                   stroke={theme.palette.divider} />
                    <XAxis type="number" allowDecimals={false}
                           tick={{ fontSize: 12, fill: theme.palette.text.secondary }} />
                    <YAxis type="category" dataKey="name" width={160}
                           tick={{ fontSize: 12, fill: theme.palette.text.primary }} />
                    <Tooltip cursor={{ fill: theme.palette.action.hover }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="competitors" name="Competitor observations" stackId="a"
                         fill={theme.palette.primary.main} />
                    <Bar dataKey="products" name="Product observations" stackId="a"
                         fill={theme.palette.success.main} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
                {summaryFailed
                  ? 'Observation history could not be loaded. Is the backend running?'
                  : 'No observations yet. Run a Competitors or Products search to start building market history.'}
              </Typography>
            )}
          </Paper>
        </Grid>
      </Grid>

      <Grid container spacing={3} sx={{ mb: 5 }}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1.5, fontWeight: 600 }}>
              Data freshness and system status
            </Typography>
            {!dashboard ? (
              <Skeleton variant="rounded" height={140} />
            ) : (
              <Box sx={{ display: 'grid', gap: 0.75 }}>
                {[
                  ['Last market observation', formatDateTime(freshness?.last_observed_at)],
                  ['Last news collected', formatDateTime(freshness?.last_news_collected_at)],
                  ['Last search-interest request', formatDateTime(freshness?.last_search_interest_collected_at)],
                ].map(([label, value]) => (
                  <Box key={label} sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
                    <Typography variant="body2" color="text.secondary">{label}</Typography>
                    <Typography variant="body2" sx={{ textAlign: 'right' }}>{value}</Typography>
                  </Box>
                ))}
                {[
                  ['SerpApi key', health?.serpapi_configured ? 'configured' : 'not configured', health?.serpapi_configured],
                  ['AI provider', health?.ai_provider_configured ? 'configured' : 'not configured (facts only)', health?.ai_provider_configured],
                  ['Failed requests (7 days)', String(health?.failed_requests_last_7_days ?? 0), !health?.failed_requests_last_7_days],
                ].map(([label, value, ok]) => (
                  <Box key={label as string} sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
                    <Typography variant="body2" color="text.secondary">{label}</Typography>
                    <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <CircleIcon sx={{ fontSize: 9, color: ok ? 'success.main' : 'warning.main' }} />
                      {value}
                    </Typography>
                  </Box>
                ))}
              </Box>
            )}
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', mb: 1 }}>
              <Typography variant="subtitle2" color="text.secondary" sx={{ fontWeight: 600 }}>
                Recent reports
              </Typography>
              <Link component={RouterLink} to="/reports" variant="caption">Reports</Link>
            </Box>
            {!dashboard ? <Skeleton variant="rounded" height={120} /> : dashboard.recent_reports.length ? (
              <List dense disablePadding>
                {dashboard.recent_reports.map((r) => (
                  <ListItem key={r.id} disableGutters>
                    <ListItemText primary={r.title} secondary={formatDateTime(r.created_at)} />
                  </ListItem>
                ))}
              </List>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No reports yet. Generate one from the Reports page.
              </Typography>
            )}
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', mb: 1 }}>
              <Typography variant="subtitle2" color="text.secondary" sx={{ fontWeight: 600 }}>
                Recent research
              </Typography>
              <Link component={RouterLink} to="/research" variant="caption">Market Research</Link>
            </Box>
            {!dashboard ? <Skeleton variant="rounded" height={120} /> : dashboard.recent_searches.length ? (
              <List dense disablePadding>
                {dashboard.recent_searches.map((s, i) => (
                  <ListItem key={i} disableGutters>
                    <ListItemText
                      primary={s.query}
                      secondary={`${s.location ?? 'No location'} · ${formatDateTime(s.searched_at)}${s.cache_hit ? ' · cached' : ''}`}
                    />
                  </ListItem>
                ))}
              </List>
            ) : (
              <Typography variant="body2" color="text.secondary">No searches recorded yet.</Typography>
            )}
          </Paper>
        </Grid>
      </Grid>

      <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, fontWeight: 600 }}>
        Modules
      </Typography>
      <Grid container spacing={3} sx={{ mb: 6 }}>
        {cards.map((card) => (
          <Grid key={card.path} size={{ xs: 12, sm: 6, md: 3 }}>
            <Paper
              role="link"
              tabIndex={0}
              aria-label={card.title}
              onClick={() => { beginNavigation(); navigate(card.path); }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  beginNavigation();
                  navigate(card.path);
                }
              }}
              sx={{
                p: 3, height: '100%', display: 'flex', flexDirection: 'column', cursor: 'pointer',
                transition: 'all 0.2s ease-in-out',
                '&:hover': {
                  transform: 'translateY(-2px)',
                  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
                  borderColor: 'primary.main',
                },
              }}
            >
              <Box sx={{
                width: 48, height: 48, borderRadius: '50%', display: 'flex', alignItems: 'center',
                justifyContent: 'center', bgcolor: card.iconBg, mb: 2, opacity: 0.8,
              }}>
                {card.icon}
              </Box>
              <Typography variant="h6" sx={{ mb: 1, fontWeight: 600 }}>{card.title}</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ flexGrow: 1, mb: 2, lineHeight: 1.5 }}>
                {card.description}
              </Typography>
              {/* Decorative: the whole card is the link. */}
              <ChevronRightIcon aria-hidden sx={{ alignSelf: 'flex-end', color: 'text.secondary' }} />
            </Paper>
          </Grid>
        ))}
      </Grid>

      {summary && !hasHistory && (
        <Paper elevation={0} sx={{
          p: 3, display: 'flex', alignItems: 'flex-start', gap: 2, bgcolor: 'primary.light',
          border: 'none', borderRadius: 2, opacity: 0.9,
        }}>
          <Box sx={{ p: 1, bgcolor: '#fff', borderRadius: '50%', display: 'flex' }}>
            <InsertChartOutlinedIcon color="primary" />
          </Box>
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, color: 'primary.dark', mb: 0.5 }}>
              Ready to get started?
            </Typography>
            <Typography variant="body2" sx={{ color: 'primary.dark' }}>
              Run a Competitors search for a market and location to start building history,
              or load the demo database described in the README.
            </Typography>
          </Box>
        </Paper>
      )}
    </Box>
  );
};

export default Dashboard;
