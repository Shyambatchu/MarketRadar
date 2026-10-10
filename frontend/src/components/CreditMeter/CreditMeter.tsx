import { useEffect, useState } from 'react';
import { Box, LinearProgress, Paper, Skeleton, Tooltip, Typography } from '@mui/material';
import BoltOutlinedIcon from '@mui/icons-material/BoltOutlined';
import SavingsOutlinedIcon from '@mui/icons-material/SavingsOutlined';

import { getUsageStats } from '../../services/serpapiApi';
import type { UsageStatsResponse } from '../../types/serpapi';

interface CreditMeterProps {
  /** `compact` fits the sidebar footer; `full` is a dashboard panel. */
  variant?: 'compact' | 'full';
  /** Changing this re-reads usage (e.g. the current route, so a search is reflected). */
  refreshKey?: string;
}

/**
 * SerpApi credit usage. Reading it costs nothing: local figures come from the
 * database and the quota from SerpApi's free account endpoint.
 *
 * Local figures are what this app recorded itself doing; they are never shown
 * as a quota. Only the account endpoint is an authority on what remains, and
 * when it cannot be read the quota is shown as unavailable, never computed.
 */
const CreditMeter = ({ variant = 'compact', refreshKey }: CreditMeterProps) => {
  const [usage, setUsage] = useState<UsageStatsResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getUsageStats(controller.signal)
      .then((u) => { setUsage(u); setFailed(false); })
      .catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => controller.abort();
  }, [refreshKey]);

  if (failed && !usage) {
    return variant === 'full' ? (
      <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
        <Typography variant="subtitle2" color="text.secondary">Search credits</Typography>
        <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
          Usage could not be read.
        </Typography>
      </Paper>
    ) : null;
  }
  if (!usage) {
    return variant === 'full'
      ? <Skeleton variant="rounded" height={160} />
      : <Skeleton variant="rounded" height={56} sx={{ mb: 1.5 }} />;
  }

  const lookups = usage.local_credits_used + usage.local_cache_hits;
  const hitRate = lookups > 0 ? Math.round((usage.local_cache_hits / lookups) * 100) : null;

  const quotaKnown = usage.account_quota_available
    && usage.searches_per_month !== null && usage.searches_per_month > 0
    && usage.this_month_usage !== null;
  const quotaPct = quotaKnown
    ? Math.min(100, (usage.this_month_usage! / usage.searches_per_month!) * 100)
    : 0;
  const quotaColor = quotaPct >= 90 ? 'error' : quotaPct >= 70 ? 'warning' : 'primary';

  const quotaLine = quotaKnown ? (
    <Tooltip title={`SerpApi account: ${usage.this_month_usage} of ${usage.searches_per_month} plan searches used this month${
      usage.total_searches_left !== null ? `, ${usage.total_searches_left} left in total` : ''}${
      usage.plan_renewal_date ? `. Renews ${usage.plan_renewal_date}.` : '.'}`}>
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="caption" color="text.secondary">
            {usage.plan_name ? `${usage.plan_name.replace(/\s*plan$/i, '')} plan · this month` : 'This month'}
          </Typography>
          <Typography variant="caption" sx={{ fontWeight: 600 }}>
            {usage.this_month_usage} / {usage.searches_per_month}
          </Typography>
        </Box>
        <LinearProgress variant="determinate" value={quotaPct} color={quotaColor}
                        sx={{ height: 6, borderRadius: 3 }}
                        aria-label="SerpApi searches used this month" />
      </Box>
    </Tooltip>
  ) : (
    <Tooltip title={usage.account_quota_detail || 'The SerpApi account endpoint could not be read.'}>
      <Typography variant="caption" color="text.disabled">Account quota unavailable</Typography>
    </Tooltip>
  );

  if (variant === 'compact') {
    return (
      <Box sx={{ mb: 1.5 }}>
        <Box sx={{ display: 'flex', gap: 1.5, mb: 1 }}>
          <Tooltip title="Live SerpApi searches this app has made (1 credit each).">
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <BoltOutlinedIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
              <Typography variant="caption"><b>{usage.local_credits_used}</b> credits used</Typography>
            </Box>
          </Tooltip>
          <Tooltip title="Searches answered from the 7-day cache instead of SerpApi: each one is a credit not spent.">
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <SavingsOutlinedIcon sx={{ fontSize: 16, color: 'success.main' }} />
              <Typography variant="caption"><b>{usage.local_cache_hits}</b> saved</Typography>
            </Box>
          </Tooltip>
        </Box>
        {quotaLine}
      </Box>
    );
  }

  return (
    <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
      <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2, fontWeight: 600 }}>
        Search credits
      </Typography>
      <Box sx={{ display: 'flex', gap: 3, mb: 2 }}>
        <Tooltip title={`${usage.local_requests_recorded} live requests recorded${
          usage.local_failed_requests ? `, ${usage.local_failed_requests} of them failed at the provider` : ''}.`}>
          <Box>
            <Typography variant="h4">{usage.local_credits_used}</Typography>
            <Typography variant="caption" color="text.secondary">credits spent</Typography>
          </Box>
        </Tooltip>
        <Box>
          <Typography variant="h4" color="success.main">{usage.local_cache_hits}</Typography>
          <Typography variant="caption" color="text.secondary">saved by cache</Typography>
        </Box>
        {hitRate !== null && (
          <Box>
            <Typography variant="h4">{hitRate}%</Typography>
            <Typography variant="caption" color="text.secondary">cache hit rate</Typography>
          </Box>
        )}
      </Box>
      {quotaLine}
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
        Identical searches within 7 days are served from cache at no cost.
      </Typography>
    </Paper>
  );
};

export default CreditMeter;
