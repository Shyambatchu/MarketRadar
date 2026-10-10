import { useNavigate } from 'react-router-dom';
import {
  Box, Button, Chip, Grid, Paper, Skeleton, Step, StepLabel, Stepper, Typography,
} from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import SensorsOutlinedIcon from '@mui/icons-material/SensorsOutlined';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';

import type { OpportunitySources } from '../../types/intelligence';
import { beginNavigation } from '../../services/loadingTracker';

interface Props {
  sources: OpportunitySources | null;
  compact?: boolean;
}

interface SourceCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  ready: boolean;
  stats: string[];
  nextStep: string;
  actions: { label: string; to: string }[];
}

const SourceCard = ({ icon, title, description, ready, stats, nextStep, actions }: SourceCardProps) => {
  const navigate = useNavigate();
  return (
    <Paper variant="outlined" sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        <Box sx={{ color: 'primary.main', display: 'flex' }}>{icon}</Box>
        <Typography variant="subtitle2" sx={{ fontWeight: 600, flexGrow: 1 }}>{title}</Typography>
        <Chip size="small" variant={ready ? 'filled' : 'outlined'} color={ready ? 'success' : 'default'}
              icon={ready ? <CheckCircleIcon /> : <RadioButtonUncheckedIcon />}
              label={ready ? 'Producing leads' : 'Needs data'} />
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>{description}</Typography>
      <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', mb: 1.5 }}>
        {stats.map((s) => <Chip key={s} size="small" label={s} sx={{ bgcolor: 'action.hover' }} />)}
      </Box>
      {!ready && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
          <b>Next step:</b> {nextStep}
        </Typography>
      )}
      <Box sx={{ mt: 'auto', display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        {actions.map((a) => (
          <Button key={a.to} size="small" variant={ready ? 'text' : 'outlined'}
                  onClick={() => { beginNavigation(); navigate(a.to); }}>
            {a.label}
          </Button>
        ))}
      </Box>
    </Paper>
  );
};

/**
 * Explains, with live counts, where opportunities come from and what to do
 * to get more: opportunities are never searched for, they are computed from
 * evidence the other modules collect.
 */
const OpportunitySourcesPanel = ({ sources, compact = false }: Props) => {
  const price = sources?.price_evidence;
  const interest = sources?.search_interest;

  return (
    <Box>
      {!compact && (
        <Stepper alternativeLabel sx={{ mb: 3, display: { xs: 'none', sm: 'flex' } }}>
          {['Collect evidence in other modules', 'Opportunities are built and scored', 'Save, review or dismiss each lead'].map((label) => (
            <Step key={label} active completed={false}><StepLabel>{label}</StepLabel></Step>
          ))}
        </Stepper>
      )}
      {!sources ? (
        <Grid container spacing={2}>
          {[0, 1, 2].map((i) => <Grid key={i} size={{ xs: 12, md: 4 }}><Skeleton variant="rounded" height={190} /></Grid>)}
        </Grid>
      ) : (
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 4 }}>
            <SourceCard
              icon={<TrendingUpIcon />}
              title="Competitor price changes"
              description="When a competitor raises or cuts the price of a product you track, or starts offering it."
              ready={(price?.signals.price_moves ?? 0) + (price?.signals.new_offers ?? 0) > 0}
              stats={[
                `${price?.products_tracked ?? 0} products tracked`,
                `${price?.products_with_history ?? 0} checked more than once`,
                `${price?.signals.price_moves ?? 0} price moves`,
              ]}
              nextStep={(price?.products_tracked ?? 0) === 0
                ? 'Search a product in Products or Price Intelligence to start tracking prices.'
                : 'Check the same product again later. A change needs two separate checks.'}
              actions={[{ label: 'Check prices', to: '/prices' }, { label: 'Find products', to: '/products' }]}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <SourceCard
              icon={<CompareArrowsIcon />}
              title="Price gaps between merchants"
              description="When merchants sell the same product at very different prices at the same time."
              ready={(price?.signals.price_gaps ?? 0) > 0}
              stats={[
                `${price?.verified_prices ?? 0} verified prices`,
                `${price?.signals.price_gaps ?? 0} gaps found`,
              ]}
              nextStep="Compare one product across nearby stores so at least two merchants have a verified price."
              actions={[{ label: 'Compare local prices', to: '/prices' }]}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 4 }}>
            <SourceCard
              icon={<SensorsOutlinedIcon />}
              title="Rising search interest"
              description="When Google Trends shows interest in a term rising sharply over the period you compared."
              ready={(interest?.rising_terms ?? 0) > 0}
              stats={[
                `${interest?.comparisons_collected ?? 0} comparisons collected`,
                `${interest?.rising_terms ?? 0} rising terms`,
              ]}
              nextStep="Compare search interest for terms in your market on Market Signals."
              actions={[{ label: 'Compare search interest', to: '/signals?tab=interest' }]}
            />
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default OpportunitySourcesPanel;
