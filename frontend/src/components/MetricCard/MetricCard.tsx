import { Paper, Typography, Box } from '@mui/material';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: {
    value: number;
    label: string;
    isPositive: boolean;
  };
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, subtitle, icon, trend }) => {
  return (
    <Paper sx={{ p: 3, display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
        <Typography variant="subtitle2" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {title}
        </Typography>
        {icon && <Box sx={{ color: 'text.disabled' }}>{icon}</Box>}
      </Box>
      <Typography variant="h3" color="text.primary" sx={{ mb: 1 }}>
        {value}
      </Typography>
      {(subtitle || trend) && (
        <Box sx={{ display: 'flex', alignItems: 'center', mt: 'auto', gap: 1 }}>
          {trend && (
            <Typography variant="body2" color={trend.isPositive ? 'success.main' : 'error.main'} sx={{ fontWeight: 500 }}>
              {trend.isPositive ? '+' : ''}{trend.value}%
            </Typography>
          )}
          {subtitle && (
            <Typography variant="caption" color="text.secondary">
              {subtitle}
            </Typography>
          )}
        </Box>
      )}
    </Paper>
  );
};

export default MetricCard;
