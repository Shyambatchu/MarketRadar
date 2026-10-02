import { useState, useEffect } from 'react';
import {
  Alert, Autocomplete, Box, Button, Chip, CircularProgress, Divider, Grid,
  List, ListItem, ListItemIcon, ListItemText, Paper, TextField, Tooltip,
  Typography,
} from '@mui/material';
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutlineOutlined';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutlineOutlined';
import HelpOutlineIcon from '@mui/icons-material/HelpOutlineOutlined';
import { isAxiosError } from 'axios';

import PageHeader from '../../components/PageHeader/PageHeader';
import EmptyState from '../../components/EmptyState/EmptyState';
import { getMarketPulseOptions } from '../../services/marketPulseApi';
import { getAnalysis } from '../../services/analystApi';
import type { MarketOption } from '../../types/marketPulse';
import type { AnalystResponse, Observation } from '../../types/analyst';

/**
 * Icons describe the kind of statement, not a sentiment. An
 * `insufficient_evidence` item is not a bad result — it is an honest one.
 */
const KIND_ICON: Record<string, React.ReactNode> = {
  observation: <CheckCircleOutlineIcon fontSize="small" color="success" />,
  limitation: <ErrorOutlineIcon fontSize="small" color="warning" />,
  insufficient_evidence: <HelpOutlineIcon fontSize="small" sx={{ color: 'text.disabled' }} />,
};

const KIND_HELP: Record<string, string> = {
  observation: 'A fact computed directly from the recorded observations.',
  limitation: 'A limitation of the evidence, stated so it is not mistaken for a finding.',
  insufficient_evidence: 'There is not enough evidence to say either way. This is not a negative finding.',
};

const optionLabel = (o: MarketOption): string =>
  `${o.market ?? 'Unspecified market'} — ${o.location ?? 'no location'}`;

const Section = ({ title, items }: { title: string; items: Observation[] }) => {
  if (items.length === 0) return null;
  return (
    <Paper variant="outlined" elevation={0} sx={{ p: 2, mb: 2 }}>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>{title}</Typography>
      <List dense disablePadding>
        {items.map((o, i) => (
          <ListItem key={i} alignItems="flex-start" disableGutters>
            <ListItemIcon sx={{ minWidth: 34, mt: 0.5 }}>
              <Tooltip title={KIND_HELP[o.kind] ?? ''}>
                <Box sx={{ display: 'flex' }}>
                  {KIND_ICON[o.kind] ?? KIND_ICON.observation}
                </Box>
              </Tooltip>
            </ListItemIcon>
            <ListItemText
              primary={<Typography variant="body2">{o.statement}</Typography>}
              secondary={
                <Typography variant="caption" color="text.disabled">
                  evidence: {o.evidence.section}
                  {o.evidence.detail ? ` · ${o.evidence.detail}` : ''}
                  {o.evidence.count !== null ? ` · ${o.evidence.count} record(s)` : ''}
                </Typography>
              }
            />
          </ListItem>
        ))}
      </List>
    </Paper>
  );
};

const AIAnalyst = () => {
  const [options, setOptions] = useState<MarketOption[]>([]);
  const [selected, setSelected] = useState<MarketOption | null>(null);
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AnalystResponse | null>(null);

  // Markets come from observed history, shared with Market Pulse.
  useEffect(() => {
    const controller = new AbortController();
    getMarketPulseOptions(controller.signal)
      .then((res) => {
        setOptions(res.options);
        if (res.options.length === 1) setSelected(res.options[0]);
      })
      .catch((err) => {
        if (!isAxiosError(err) || err.code !== 'ERR_CANCELED') {
          setError('Unable to load observed markets. Is the backend running?');
        }
      })
      // An aborted (StrictMode) request must not end the loading state early.
      .finally(() => { if (!controller.signal.aborted) setLoadingOptions(false); });
    return () => controller.abort();
  }, []);

  const run = async () => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    // A failed rerun must not leave the previous analysis on screen.
    setData(null);
    try {
      setData(await getAnalysis({
        market: selected?.market ?? undefined,
        location: selected?.location ?? undefined,
      }));
    } catch (err) {
      const detail = isAxiosError(err) ? err.response?.data?.detail : null;
      setError(detail || 'Unable to generate the analysis.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <PageHeader
        title="AI Analyst"
        subtitle="Evidence-grounded analysis of a Market Pulse snapshot. Every statement traces back to recorded observations."
      />

      <Paper sx={{ p: 3, mb: 4 }}>
        <Grid container spacing={2} sx={{ alignItems: 'center' }}>
          <Grid size={{ xs: 12, sm: 9 }}>
            <Autocomplete
              size="small" options={options} value={selected}
              onChange={(_, v) => { setSelected(v); setData(null); setError(null); }}
              // Omitting a missing filter would analyse every market at once.
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
              noOptionsText="No markets have been observed yet."
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 3 }}>
            <Button
              fullWidth variant="contained" sx={{ height: 40 }}
              startIcon={loading
                ? <CircularProgress size={20} color="inherit" />
                : <AutoAwesomeOutlinedIcon />}
              onClick={run} disabled={loading || loadingOptions || !selected}
            >
              Analyze
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      {data && !data.has_data && (
        <EmptyState
          title="Nothing to analyse for this selection"
          description={data.detail ?? 'No observations have been recorded for this market and location.'}
          icon={<AutoAwesomeOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
        />
      )}

      {data && data.has_data && (
        <>
          {/* ---- provenance ---- */}
          <Box sx={{ mb: 2, display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
            <Tooltip title="Every factual statement below is computed from the Market Pulse snapshot by the backend. A language model is never asked to produce one.">
              <Chip size="small" variant="outlined" color="success"
                    label={`Analysis generated from the current Market Pulse snapshot`} />
            </Tooltip>
            <Chip size="small" variant="outlined"
                  label={data.analysis_mode === 'assisted'
                    ? 'Facts + AI narrative summary'
                    : 'Facts only (deterministic)'} />
            <Chip size="small" variant="outlined"
                  color={data.provider_configured ? 'info' : 'default'}
                  label={data.provider_configured
                    ? `AI provider: ${data.provider_name ?? 'configured'}`
                    : 'AI provider not configured'} />
          </Box>

          {/* ---- executive summary ---- */}
          {data.summary && (
            <Paper variant="outlined" elevation={0} sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>Executive summary</Typography>
              <Typography variant="body2">{data.summary}</Typography>
              <Typography variant="caption" color="text.disabled" sx={{ mt: 1, display: 'block' }}>
                Written by the configured AI provider from the computed facts
                below, and validated before display.
              </Typography>
            </Paper>
          )}

          {data.summary_rejected && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                The AI summary was withheld
              </Typography>
              {data.summary_rejection_reason} The factual analysis below is
              unaffected — it is computed by the backend, not generated.
            </Alert>
          )}

          {!data.provider_configured && (
            <Alert severity="info" sx={{ mb: 2 }}>
              No AI provider is configured, so no narrative summary was produced.
              The analysis below is computed directly from the Market Pulse
              snapshot and does not require one.
            </Alert>
          )}

          {data.provider_error && !data.summary_rejected && data.provider_configured && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              {data.provider_error} The factual analysis below is unaffected.
            </Alert>
          )}

          <Divider sx={{ mb: 2 }} />

          <Section title="Market overview" items={data.market_overview} />
          <Section title="Competitor observations" items={data.competitor_observations} />
          <Section title="Product observations" items={data.product_observations} />
          <Section title="Price analysis" items={data.price_analysis} />
          <Section title="Visibility observations" items={data.visibility_observations} />
          <Section title="Trend analysis" items={data.trend_analysis} />
          <Section title="Data quality" items={data.data_quality} />

          <Paper variant="outlined" elevation={0} sx={{ p: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              Evidence ({data.evidence.length} reference{data.evidence.length === 1 ? '' : 's'})
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Each statement above traces to a section of the Market Pulse
              snapshot and the records behind it.
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {Array.from(new Set(data.evidence.map((e) => e.section))).map((s) => (
                <Chip key={s} size="small" variant="outlined" label={s.replace(/_/g, ' ')} />
              ))}
            </Box>
          </Paper>
        </>
      )}

      {!data && !error && !loadingOptions && (
        <EmptyState
          title={options.length === 0
            ? 'No observation history yet'
            : 'Select a market and location'}
          description={options.length === 0
            ? 'The analyst reads what Competitors and Products have recorded. Run a search in either module to build history — the analyst makes no external requests of its own.'
            : 'Choose an observed market and location, then run the analysis.'}
          icon={<AutoAwesomeOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
        />
      )}
    </Box>
  );
};

export default AIAnalyst;
