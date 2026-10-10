import { useTheme, type Theme } from '@mui/material/styles';
import { Box, Typography } from '@mui/material';
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';

import type { TrendSeries } from '../../types/trend';

const AVAILABILITY_LABEL: Record<string, string> = { '1': 'found', '0': 'unknown', '-1': 'not found' };

const formatMetricValue = (metric: string, value: number | null): string => {
  if (value === null) return '—';
  if (metric === 'price') return `$${value.toFixed(2)}`;
  if (metric === 'availability') return AVAILABILITY_LABEL[String(value)] ?? String(value);
  if (metric === 'position') return `#${value}`;
  return String(value);
};

const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

/**
 * Colour carries meaning only when there is a direction to colour: a series
 * with one distinct measurement is drawn muted, never green or amber.
 * For position a smaller number is better, so the axis is reversed and "up"
 * on screen always means "better".
 */
const lineColor = (series: TrendSeries, palette: Theme['palette']) => {
  if (series.status !== 'trend' || !series.direction || series.direction === 'flat'
      || series.metric === 'availability') {
    return series.status === 'trend' ? palette.primary.main : palette.text.disabled;
  }
  const better = series.metric === 'position' ? series.direction === 'down' : series.direction === 'up';
  return better ? palette.success.main : palette.warning.main;
};

const toData = (series: TrendSeries) =>
  series.points.map((p) => ({
    t: new Date(p.observed_at).getTime(),
    value: p.value,
    label: p.label,
    count: p.observation_count,
  }));

/** A tiny inline chart for a table row. */
export const Sparkline = ({ series }: { series: TrendSeries }) => {
  const theme = useTheme();
  const data = toData(series);
  if (data.filter((d) => d.value !== null).length === 0) {
    return <Typography variant="caption" color="text.disabled">—</Typography>;
  }
  const color = lineColor(series, theme.palette);
  return (
    <Box sx={{ width: 96, height: 28 }} aria-label={`${series.subject} ${series.metric} history`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <YAxis hide domain={['dataMin', 'dataMax']} reversed={series.metric === 'position'} />
          <XAxis hide dataKey="t" type="number" domain={['dataMin', 'dataMax']} />
          <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2}
                dot={data.length === 1 ? { r: 3, fill: color } : false}
                isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </Box>
  );
};

/** A full chart of every distinct measurement in one series. */
const TrendChart = ({ series }: { series: TrendSeries }) => {
  const theme = useTheme();
  const data = toData(series);
  const color = lineColor(series, theme.palette);
  const isAvailability = series.metric === 'availability';

  return (
    <Box>
      <Box sx={{ width: '100%', height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 12, right: 24, bottom: 4, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
            <XAxis dataKey="t" type="number" scale="time"
                   domain={data.length === 1 ? ['dataMin - 86400000', 'dataMax + 86400000'] : ['dataMin', 'dataMax']}
                   tickFormatter={(t: number) => shortDate(new Date(t).toISOString())}
                   tick={{ fontSize: 12, fill: theme.palette.text.secondary }} />
            <YAxis
              reversed={series.metric === 'position'}
              allowDecimals={series.metric === 'price' || series.metric === 'rating'}
              domain={isAvailability ? [-1, 1] : ['auto', 'auto']}
              ticks={isAvailability ? [-1, 0, 1] : undefined}
              tickFormatter={(v: number) => formatMetricValue(series.metric, v)}
              width={isAvailability ? 72 : 56}
              tick={{ fontSize: 12, fill: theme.palette.text.secondary }} />
            <Tooltip
              labelFormatter={(t) => new Date(Number(t)).toLocaleString()}
              formatter={(v, _n, item) => {
                const count = (item?.payload as { count?: number })?.count ?? 1;
                return [
                  `${formatMetricValue(series.metric, v as number)}${count > 1 ? ` (read ${count}×)` : ''}`,
                  series.metric,
                ];
              }} />
            <Line type={isAvailability ? 'stepAfter' : 'monotone'} dataKey="value"
                  stroke={color} strokeWidth={2.5}
                  dot={{ r: 4, fill: color }} activeDot={{ r: 6 }}
                  connectNulls={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </Box>
      <Typography variant="caption" color="text.secondary">
        {series.status === 'trend'
          ? `${series.distinct_points} distinct measurements from ${series.raw_observations} stored observations.`
          : 'One distinct measurement so far, so no direction is claimed. Repeated readings inside the cache window collapse into one point.'}
        {series.metric === 'position' && ' Higher on the chart is a better search position.'}
      </Typography>
    </Box>
  );
};

export default TrendChart;
