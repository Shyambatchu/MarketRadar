import { useEffect, useState } from 'react';
import {
  Alert, Box, Button, Grid, Link, Paper, Skeleton, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Typography, useTheme,
} from '@mui/material';
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip as ChartTooltip,
  XAxis, YAxis,
} from 'recharts';

import PageHeader from '../../components/PageHeader/PageHeader';
import CreditMeter from '../../components/CreditMeter/CreditMeter';
import { getUsageBreakdown } from '../../services/intelligenceApi';
import type { UsageBreakdown } from '../../types/intelligence';
import { errorMessage, formatDate, formatDateTime, formatMoney, isCanceled } from '../../utils/format';

const Kpi = ({ label, value, detail }: { label: string; value: string; detail?: React.ReactNode }) => (
  <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
    <Typography variant="subtitle2" color="text.secondary">{label}</Typography>
    <Typography variant="h5" component="p" sx={{ fontWeight: 600, mt: 0.5 }}>{value}</Typography>
    {detail && (
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{detail}</Typography>
    )}
  </Paper>
);

// Days come as ISO dates; parsing them as local midnight avoids the UTC shift
// that would label a bar with the previous day.
const dayLabel = (day: string): string => {
  const [y, m, d] = day.split('-').map(Number);
  return y && m && d
    ? new Date(y, m - 1, d).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : day;
};

const Usage = () => {
  const theme = useTheme();
  const [reloadKey, setReloadKey] = useState(0);
  // The result remembers which load it answers, so a retry shows the skeleton
  // again without resetting state inside the effect.
  const [result, setResult] = useState<{
    key: number; data: UsageBreakdown | null; error: string | null;
  } | null>(null);
  const current = result?.key === reloadKey ? result : null;
  const data = current?.data ?? null;
  const error = current?.error ?? null;

  useEffect(() => {
    const controller = new AbortController();
    getUsageBreakdown(controller.signal)
      .then((res) => setResult({ key: reloadKey, data: res, error: null }))
      .catch((err) => {
        if (!isCanceled(err)) {
          setResult({ key: reloadKey, data: null, error: errorMessage(err, 'Usage could not be loaded.') });
        }
      });
    return () => controller.abort();
  }, [reloadKey]);

  // The API lists newest first; a chart reads left-to-right in time.
  const daily = data ? [...data.daily].reverse().map((d) => ({ ...d, label: dayLabel(d.day) })) : [];
  const hasDaily = daily.some((d) => d.credits_used > 0 || d.requests > 0);

  return (
    <Box>
      <PageHeader
        title="Usage & Cost"
        subtitle="SerpApi credits this app has spent, by feature and by day, with an estimated cost."
      />

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}
               action={<Button color="inherit" size="small" onClick={() => setReloadKey((k) => k + 1)}>Retry</Button>}>
          {error}
        </Alert>
      )}

      {!data && !error && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {[0, 1, 2].map((i) => (
            <Grid key={i} size={{ xs: 12, sm: 4 }}><Skeleton variant="rounded" height={110} /></Grid>
          ))}
          <Grid size={{ xs: 12 }}><Skeleton variant="rounded" height={260} /></Grid>
        </Grid>
      )}

      {data && (
        <>
          {data.budget_exhausted && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              The monthly app budget of {data.monthly_budget} credits is used up. Live searches are
              blocked until next month; cached results remain available.
            </Alert>
          )}

          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid size={{ xs: 12, sm: 4 }}>
              <Kpi
                label="Credits used this month"
                value={data.credits_used_this_month.toLocaleString()}
                detail={`As of ${formatDateTime(data.generated_at)}`}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              {data.monthly_budget === null ? (
                <Kpi
                  label="Monthly budget"
                  value="No app budget set"
                  detail="SerpApi account quota applies."
                />
              ) : (
                <Kpi
                  label="Monthly budget"
                  value={`${data.monthly_budget.toLocaleString()} credits`}
                  detail={data.budget_remaining === null
                    ? 'Remaining: unavailable'
                    : `${data.budget_remaining.toLocaleString()} remaining`}
                />
              )}
            </Grid>
            <Grid size={{ xs: 12, sm: 4 }}>
              <Kpi
                label="Estimated cost this month"
                value={data.estimated_cost_this_month_usd === null
                  ? 'Not estimated'
                  : formatMoney(data.estimated_cost_this_month_usd, 'USD')}
                detail={data.estimated_cost_this_month_usd === null ? data.cost_basis : 'Estimate, not an invoice'}
              />
            </Grid>
          </Grid>

          <Box sx={{ mb: 3 }}>
            <CreditMeter variant="full" />
          </Box>

          <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
            <Typography variant="subtitle2" gutterBottom>How cost is estimated</Typography>
            <Typography variant="body2">
              Cost per search:{' '}
              <strong>
                {data.cost_per_search_usd === null
                  ? 'not estimated'
                  : formatMoney(data.cost_per_search_usd, 'USD')}
              </strong>
              {' — '}{data.cost_basis}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              SerpApi bills a monthly plan rather than per search, so cost per search is the plan
              price divided by the plan's searches
              {data.plan_monthly_price_usd !== undefined && data.plan_searches_per_month !== undefined
                ? ` (${formatMoney(data.plan_monthly_price_usd, 'USD')} / ${data.plan_searches_per_month.toLocaleString()} searches)`
                : ''}
              . Figures here are estimates.
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Pricing source:{' '}
              <Link href={data.pricing_source} target="_blank" rel="noopener noreferrer"
                    sx={{ wordBreak: 'break-all' }}>
                {data.pricing_source}
              </Link>{' '}
              (retrieved {formatDate(data.pricing_retrieved)})
            </Typography>
          </Paper>

          <Typography variant="h6" gutterBottom>By feature</Typography>
          {data.by_endpoint.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
              <Typography variant="body2" color="text.secondary">
                No SerpApi requests have been recorded yet.
              </Typography>
            </Paper>
          ) : (
            <TableContainer component={Paper} sx={{ mb: 3 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Feature</TableCell>
                    <TableCell>Engine</TableCell>
                    <TableCell align="right">Requests</TableCell>
                    <TableCell align="right">Credits</TableCell>
                    <TableCell align="right">Failed</TableCell>
                    <TableCell align="right">Avg response (s)</TableCell>
                    <TableCell>Last request</TableCell>
                    <TableCell align="right">Est. cost</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.by_endpoint.map((row) => (
                    <TableRow key={`${row.endpoint}-${row.engine}-${row.feature}`} hover>
                      <TableCell>{row.feature}</TableCell>
                      <TableCell>{row.engine}</TableCell>
                      <TableCell align="right">{row.requests.toLocaleString()}</TableCell>
                      <TableCell align="right">{row.credits_used.toLocaleString()}</TableCell>
                      <TableCell align="right">{row.failed_requests.toLocaleString()}</TableCell>
                      <TableCell align="right">
                        {row.avg_response_seconds === null ? '—' : row.avg_response_seconds.toFixed(2)}
                      </TableCell>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>{formatDateTime(row.last_request_at)}</TableCell>
                      <TableCell align="right">
                        {row.estimated_cost_usd === null ? 'Not estimated' : formatMoney(row.estimated_cost_usd, 'USD')}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}

          <Typography variant="h6" gutterBottom>Daily credits</Typography>
          <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
            {hasDaily ? (
              <Box sx={{ width: '100%', height: 260 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={daily} margin={{ top: 8, right: 16, bottom: 24, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} vertical={false} />
                    <XAxis
                      dataKey="label" tick={{ fontSize: 12, fill: theme.palette.text.secondary }}
                      label={{ value: 'Day', position: 'insideBottom', offset: -16, fill: theme.palette.text.secondary, fontSize: 12 }}
                    />
                    <YAxis
                      allowDecimals={false} width={56}
                      tick={{ fontSize: 12, fill: theme.palette.text.secondary }}
                      label={{ value: 'Credits', angle: -90, position: 'insideLeft', fill: theme.palette.text.secondary, fontSize: 12 }}
                    />
                    <ChartTooltip
                      formatter={(value, _name, item) => {
                        const requests = (item?.payload as { requests?: number })?.requests ?? 0;
                        return [`${value} credit(s) · ${requests} request(s)`, 'Used'];
                      }}
                    />
                    <Bar dataKey="credits_used" fill={theme.palette.primary.main}
                         radius={[3, 3, 0, 0]} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No credits have been spent in the recorded period, so there is nothing to chart.
              </Typography>
            )}
          </Paper>
        </>
      )}

      <Typography variant="body2" color="text.secondary">
        Cached responses cost nothing: a repeated search is served from the database without a
        new SerpApi request. Trends, Market Pulse, the Analyst, Opportunities and Reports read
        stored evidence and never spend credits. Set the optional <code>SERPAPI_MONTHLY_BUDGET</code>{' '}
        environment variable to block live searches once this app has used that many credits in
        a month.
      </Typography>
    </Box>
  );
};

export default Usage;
