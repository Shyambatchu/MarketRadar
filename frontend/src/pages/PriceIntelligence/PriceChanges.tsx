import { useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, Link, Paper, Stack, Typography, Tooltip,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import RefreshIcon from '@mui/icons-material/Refresh';

import ExportButton from '../../components/ExportButton/ExportButton';
import { exportUrl, getPriceAlerts } from '../../services/intelligenceApi';
import type { PriceAlert, PriceAlertResponse } from '../../types/intelligence';
import {
  errorMessage, formatDate, formatDateTime, formatMoney, formatPercent, humanize,
  isCanceled,
} from '../../utils/format';

const TYPE_COLOR: Record<string, 'warning' | 'success' | 'default' | 'info' | 'error'> = {
  price_increase: 'warning',
  price_decrease: 'success',
  conflicting_prices: 'error',
};

const CONFIDENCE_COLOR: Record<string, 'success' | 'info' | 'default'> = {
  high: 'success',
  medium: 'info',
  low: 'default',
};

interface PriceChangesProps {
  /** The last searched product; the user can switch to all products. */
  product: string | null;
  /** Bumped after a search saves new observations, to reload. */
  refreshKey: number;
}

const AlertCard = ({ alert }: { alert: PriceAlert }) => (
  <Paper variant="outlined" sx={{ p: 2 }}>
    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 1 }}>
      <Chip size="small" label={humanize(alert.type)} color={TYPE_COLOR[alert.type] ?? 'default'}
            variant={TYPE_COLOR[alert.type] ? 'filled' : 'outlined'} />
      <Chip size="small" variant="outlined" label={`${alert.confidence} confidence`}
            color={CONFIDENCE_COLOR[alert.confidence] ?? 'default'} />
      <Typography variant="subtitle2" sx={{ wordBreak: 'break-word' }}>{alert.product}</Typography>
      {alert.merchant && (
        <Typography variant="body2" color="text.secondary">at {alert.merchant}</Typography>
      )}
    </Box>

    {(alert.previous_price !== null || alert.current_price !== null) && (
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'baseline', flexWrap: 'wrap', mb: 0.5 }}>
        {alert.previous_price !== null && (
          <Typography variant="body1" color="text.secondary">
            {formatMoney(alert.previous_price, alert.currency)}
          </Typography>
        )}
        {alert.previous_price !== null && alert.current_price !== null && (
          <Typography variant="body1" color="text.secondary">→</Typography>
        )}
        {alert.current_price !== null && (
          <Typography variant="h6">{formatMoney(alert.current_price, alert.currency)}</Typography>
        )}
        {alert.change_percent !== null && (
          <Typography variant="body2" sx={{ fontWeight: 600 }}
                      color={alert.change_percent > 0 ? 'warning.main'
                        : alert.change_percent < 0 ? 'success.main' : 'text.secondary'}>
            {formatPercent(alert.change_percent)}
          </Typography>
        )}
      </Box>
    )}

    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
      {alert.previous_observed_at ? `${formatDate(alert.previous_observed_at)} → ` : ''}
      {alert.observed_at ? formatDate(alert.observed_at) : 'Date not recorded'}
      {alert.market ? ` · ${alert.market}` : ''}
      {alert.location ? ` · ${alert.location}` : ''}
    </Typography>

    <Typography variant="body2" sx={{ mb: alert.source_urls.length ? 1 : 0 }}>
      {alert.explanation}
    </Typography>

    {alert.source_urls.length > 0 && (
      <Stack spacing={0.25}>
        {alert.source_urls.map((url) => (
          <Link key={url} href={url} target="_blank" rel="noopener noreferrer" underline="hover"
                variant="caption" sx={{ wordBreak: 'break-all' }}>
            {url}
          </Link>
        ))}
      </Stack>
    )}
  </Paper>
);

/**
 * Detected price changes over stored verified prices. Reads the database
 * only — it never spends a search credit.
 */
const PriceChanges = ({ product, refreshKey }: PriceChangesProps) => {
  const [onlyProduct, setOnlyProduct] = useState(true);
  const [reload, setReload] = useState(0);
  const q = product && onlyProduct ? product : undefined;
  // Which request the shown state answers; loading is derived from it, so a
  // new request never shows the previous answer as current.
  const requestKey = `${q ?? ''}|${refreshKey}|${reload}`;
  const [state, setState] = useState<{
    key: string | null; error: string | null; data: PriceAlertResponse | null;
  }>({ key: null, error: null, data: null });

  useEffect(() => {
    const controller = new AbortController();
    getPriceAlerts({ q }, controller.signal)
      .then((data) => setState({ key: requestKey, error: null, data }))
      .catch((err) => {
        if (isCanceled(err)) return;
        setState({ key: requestKey, data: null,
          error: errorMessage(err, 'Price changes could not be loaded.') });
      });
    return () => controller.abort();
  }, [q, requestKey]);

  const loading = state.key !== requestKey;
  const { error, data } = state;

  return (
    <Box sx={{ mt: 6 }}>
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 1 }}>
        <Typography variant="h6" sx={{ flexGrow: 1 }}>Price changes</Typography>
        <Button size="small" startIcon={<RefreshIcon />} disabled={loading}
                onClick={() => setReload((n) => n + 1)}>
          Refresh
        </Button>
        <ExportButton href={exportUrl('price-alerts', { q })} disabled={loading || !!error} />
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Changes detected across verified prices already stored from earlier searches.
      </Typography>

      {product && (
        <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
          <Chip size="small" label={`Only “${product}”`}
                color={onlyProduct ? 'primary' : 'default'}
                variant={onlyProduct ? 'filled' : 'outlined'}
                onClick={() => setOnlyProduct(true)} />
          <Chip size="small" label="All products"
                color={!onlyProduct ? 'primary' : 'default'}
                variant={!onlyProduct ? 'filled' : 'outlined'}
                onClick={() => setOnlyProduct(false)} />
        </Box>
      )}

      {data && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 2 }}>
          <Typography variant="caption" color="text.secondary">
            {data.verified_observations} verified prices checked · updated {formatDateTime(data.generated_at)}
          </Typography>
          <Tooltip title={`A change is reported when a price moves by at least ${data.thresholds.min_change_percent}%. `
            + `Outliers are prices beyond ${data.thresholds.outlier_mad_k}x the median absolute deviation `
            + `(${data.thresholds.min_merchants_for_outliers}+ merchants needed). A spread is flagged above `
            + `${data.thresholds.dispersion_min_percent}%.`}>
            <InfoOutlinedIcon sx={{ fontSize: 16, color: 'text.secondary', cursor: 'help' }} aria-label="How changes are detected" />
          </Tooltip>
        </Box>
      )}

      {loading ? (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 3 }}>
          <CircularProgress size={20} />
          <Typography variant="body2" color="text.secondary">Loading price changes…</Typography>
        </Box>
      ) : error ? (
        <Alert severity="error" action={(
          <Button color="inherit" size="small" onClick={() => setReload((n) => n + 1)}>Retry</Button>
        )}>
          {error}
        </Alert>
      ) : data && data.alerts.length === 0 ? (
        <Alert severity="info">
          {data.detail || 'No price changes met the thresholds in the stored evidence.'}
        </Alert>
      ) : data ? (
        <Stack spacing={1.5}>
          {data.total > data.alerts.length && (
            <Typography variant="caption" color="text.secondary">
              Showing {data.alerts.length} of {data.total} changes.
            </Typography>
          )}
          {data.alerts.map((alert, i) => (
            <AlertCard key={`${alert.type}-${alert.product}-${alert.merchant ?? ''}-${i}`} alert={alert} />
          ))}
        </Stack>
      ) : null}
    </Box>
  );
};

export default PriceChanges;
