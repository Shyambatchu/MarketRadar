import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography, Grid, Paper, IconButton, Skeleton } from '@mui/material';
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

import MetricCard from '../../components/MetricCard/MetricCard';
import CreditMeter from '../../components/CreditMeter/CreditMeter';
import { getTrendSummary } from '../../services/trendApi';
import type { TrendSummaryResponse } from '../../types/trend';

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

const lastObserved = (summary: TrendSummaryResponse): string | null => {
  const times = summary.contexts
    .map((c) => c.last_observed_at)
    .filter((t): t is string => !!t)
    .sort();
  return times.length ? times[times.length - 1] : null;
};

const Dashboard = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const [summary, setSummary] = useState<TrendSummaryResponse | null>(null);
  const [summaryFailed, setSummaryFailed] = useState(false);

  // A database read: no provider request, no credit.
  useEffect(() => {
    const controller = new AbortController();
    getTrendSummary(controller.signal)
      .then(setSummary)
      .catch(() => { if (!controller.signal.aborted) setSummaryFailed(true); });
    return () => controller.abort();
  }, []);

  const contextRows = summary ? toContextRows(summary) : [];
  const markets = summary
    ? new Set(summary.contexts.map((c) => `${c.market}|${c.location}`)).size
    : 0;
  const repeatedMarkets = summary
    ? new Set(summary.contexts.filter((c) => c.analyzable)
      .map((c) => `${c.market}|${c.location}`)).size
    : 0;
  const latest = summary ? lastObserved(summary) : null;
  const hasHistory = !!summary
    && (summary.competitor_observations > 0 || summary.product_observations > 0);

  const metrics = summary ? [
    { title: 'Businesses tracked', value: summary.merchants_tracked,
      subtitle: `${summary.competitor_observations} competitor observations`,
      icon: <StorefrontOutlinedIcon /> },
    { title: 'Markets observed', value: markets,
      subtitle: `${repeatedMarkets} searched more than once`,
      icon: <PlaceOutlinedIcon /> },
    { title: 'Product observations', value: summary.product_observations,
      subtitle: 'merchant catalogue checks',
      icon: <Inventory2OutlinedIcon /> },
    { title: 'Verified prices', value: summary.verified_price_observations,
      subtitle: "read from the merchant's own page",
      icon: <FactCheckOutlinedIcon /> },
  ] : [];

  const cards = [
    {
      title: 'Start Market Research',
      description: 'Search and analyze market visibility across search engines and local results.',
      icon: <SearchOutlinedIcon sx={{ color: 'primary.main', fontSize: 28 }} />,
      path: '/research',
      iconBg: 'primary.light',
    },
    {
      title: 'Analyze Competitors',
      description: 'Identify the businesses competing in a market and place, with the evidence for each.',
      icon: <StorefrontOutlinedIcon sx={{ color: 'success.dark', fontSize: 28 }} />,
      path: '/competitors',
      iconBg: 'success.light',
    },
    {
      title: 'Find Products',
      description: "Check which merchants' catalogues list a product, and at what verified price.",
      icon: <Inventory2OutlinedIcon sx={{ color: 'info.dark', fontSize: 28 }} />,
      path: '/products',
      iconBg: 'info.light',
    },
    {
      title: 'Track Trends',
      description: 'See what changed between distinct measurements, and what cannot be compared yet.',
      icon: <TrendingUpOutlinedIcon sx={{ color: 'warning.dark', fontSize: 28 }} />,
      path: '/trends',
      iconBg: 'warning.light',
    },
    {
      title: 'Compare Local Prices',
      description: 'Compare verified prices for one product across nearby stores.',
      icon: <AttachMoneyOutlinedIcon sx={{ color: 'secondary.dark', fontSize: 28 }} />,
      path: '/prices',
      iconBg: 'secondary.light',
    },
    {
      title: 'Market Pulse',
      description: 'A factual snapshot of one observed market and location.',
      icon: <InsightsOutlinedIcon sx={{ color: 'primary.dark', fontSize: 28 }} />,
      path: '/pulse',
      iconBg: 'primary.light',
    },
    {
      title: 'AI Analyst',
      description: 'Evidence-referenced statements computed from a Market Pulse snapshot.',
      icon: <PsychologyOutlinedIcon sx={{ color: 'success.dark', fontSize: 28 }} />,
      path: '/analyst',
      iconBg: 'success.light',
    },
  ];

  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', mt: 2 }}>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h1" sx={{ fontSize: '2.25rem', mb: 1, color: 'text.primary' }}>
          Welcome to MarketRadar
        </Typography>
        <Typography variant="subtitle1" color="text.secondary" sx={{ fontSize: '1.125rem' }}>
          Monitor markets, competitors, pricing, trends and search visibility.
        </Typography>
        {latest && (
          <Typography variant="caption" color="text.secondary">
            Latest observation {new Date(latest).toLocaleString(undefined, {
              year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
            })}
          </Typography>
        )}
      </Box>

      {!summaryFailed && (
        <Grid container spacing={3} sx={{ mb: 3 }}>
          {summary
            ? metrics.map((m) => (
              <Grid key={m.title} size={{ xs: 12, sm: 6, md: 3 }}>
                <MetricCard {...m} />
              </Grid>
            ))
            : [0, 1, 2, 3].map((i) => (
              <Grid key={i} size={{ xs: 12, sm: 6, md: 3 }}>
                <Skeleton variant="rounded" height={140} />
              </Grid>
            ))}
        </Grid>
      )}

      <Grid container spacing={3} sx={{ mb: 6 }}>
        <Grid size={{ xs: 12, md: 8 }}>
          <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, fontWeight: 600 }}>
              Observations by market
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
                    <YAxis type="category" dataKey="name" width={200}
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
        <Grid size={{ xs: 12, md: 4 }}>
          <CreditMeter variant="full" />
        </Grid>
      </Grid>

      <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, fontWeight: 600 }}>
        Modules
      </Typography>
      <Grid container spacing={3} sx={{ mb: 6 }}>
        {cards.map((card, idx) => (
          <Grid key={idx} size={{xs: 12, sm: 6, md: 3}}>
            <Paper
              role="link"
              tabIndex={0}
              aria-label={card.title}
              onClick={() => navigate(card.path)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  navigate(card.path);
                }
              }}
              sx={{
                p: 3,
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                cursor: 'pointer',
                transition: 'all 0.2s ease-in-out',
                '&:hover': {
                  transform: 'translateY(-2px)',
                  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
                  borderColor: 'primary.main'
                },
              }}
            >
              <Box
                sx={{
                  width: 48,
                  height: 48,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  bgcolor: card.iconBg,
                  mb: 2,
                  opacity: 0.8
                }}
              >
                {card.icon}
              </Box>
              <Typography variant="h6" sx={{ mb: 1, fontWeight: 600 }}>
                {card.title}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ flexGrow: 1, mb: 2, lineHeight: 1.5 }}>
                {card.description}
              </Typography>
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 'auto' }}>
                <IconButton size="small" sx={{ pointerEvents: 'none' }}>
                  <ChevronRightIcon />
                </IconButton>
              </Box>
            </Paper>
          </Grid>
        ))}
      </Grid>

      {!hasHistory && (
        <Paper
          elevation={0}
          sx={{
            p: 3,
            display: 'flex',
            alignItems: 'flex-start',
            gap: 2,
            bgcolor: 'primary.light',
            border: 'none',
            borderRadius: 2,
            opacity: 0.9
          }}
        >
          <Box sx={{ p: 1, bgcolor: '#fff', borderRadius: '50%', display: 'flex' }}>
            <InsertChartOutlinedIcon color="primary" />
          </Box>
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, color: 'primary.dark', mb: 0.5 }}>
              Ready to get started?
            </Typography>
            <Typography variant="body2" sx={{ color: 'primary.dark' }}>
              Use the navigation menu to explore different modules or start with a market research search.
            </Typography>
          </Box>
        </Paper>
      )}
    </Box>
  );
};

export default Dashboard;
