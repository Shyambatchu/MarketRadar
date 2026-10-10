import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Chip, CircularProgress,
  Dialog, DialogActions, DialogContent, DialogTitle, Grid, MenuItem, Paper, Skeleton, Snackbar,
  Stack, Tab, Table, TableBody, TableCell, TableHead, TableRow, Tabs, TextField, Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import RefreshIcon from '@mui/icons-material/Refresh';
import LightbulbOutlinedIcon from '@mui/icons-material/LightbulbOutlined';
import HelpOutlineIcon from '@mui/icons-material/HelpOutlineOutlined';

import PageHeader from '../../components/PageHeader/PageHeader';
import ExportButton from '../../components/ExportButton/ExportButton';
import MarketScopeSelect from '../../components/MarketScopeSelect/MarketScopeSelect';
import {
  exportUrl, getOpportunitySources, getScoringMethod, listOpportunities, refreshOpportunities,
} from '../../services/intelligenceApi';
import type {
  Opportunity, OpportunityListResponse, OpportunitySources, OpportunityStatus, ScoringMethod,
} from '../../types/intelligence';
import type { MarketOption } from '../../types/marketPulse';
import { errorMessage, formatDateTime, isCanceled } from '../../utils/format';
import OpportunityCard from './OpportunityCard';
import { CATEGORY, scoreBand } from './opportunityDisplay';
import OpportunitySourcesPanel from './OpportunitySourcesPanel';

type StatusTab = 'active' | Exclude<OpportunityStatus, 'new'>;

const TABS: { value: StatusTab; label: string }[] = [
  { value: 'active', label: 'To review' },
  { value: 'saved', label: 'Saved' },
  { value: 'reviewed', label: 'Reviewed' },
  { value: 'dismissed', label: 'Dismissed' },
];

const MIN_SCORES = [
  { value: 0, label: 'All priorities' },
  { value: 35, label: 'Medium and high' },
  { value: 60, label: 'High only' },
];

// The backend's default (no status) already excludes dismissed leads.
const statusParam = (tab: StatusTab): OpportunityStatus | undefined =>
  tab === 'active' ? undefined : tab;

const INPUT_LABEL: Record<string, string> = {
  impact: 'Size of change', confidence: 'Evidence strength', freshness: 'How recent', relevance: 'Relevance to you',
};

const Summary = ({ label, value, tone }: { label: string; value: React.ReactNode; tone?: string }) => (
  <Paper variant="outlined" sx={{ p: 2, height: '100%' }}>
    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
      {label}
    </Typography>
    <Typography variant="h5" sx={{ fontWeight: 700, mt: 0.5, color: tone ?? 'text.primary' }}>{value}</Typography>
  </Paper>
);

const Opportunities = () => {
  const [scope, setScope] = useState<MarketOption | null>(null);
  const [tab, setTab] = useState<StatusTab>('active');
  const [minScore, setMinScore] = useState(0);
  const [category, setCategory] = useState<string | null>(null);

  const [reloadKey, setReloadKey] = useState(0);
  const [result, setResult] = useState<{
    key: string; data: OpportunityListResponse | null; error: string | null;
  } | null>(null);
  const [sources, setSources] = useState<OpportunitySources | null>(null);
  const [method, setMethod] = useState<ScoringMethod | null>(null);
  const [methodOpen, setMethodOpen] = useState(false);

  // Opportunities are rebuilt from stored evidence when the page opens, so
  // the list is current without anyone pressing a button. It reads only
  // stored data, so it costs nothing.
  const [refreshing, setRefreshing] = useState(true);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const market = scope?.market ?? undefined;
  const location = scope?.location ?? undefined;
  const requestKey = JSON.stringify([tab, market, location, minScore, reloadKey]);
  const loading = refreshing || result?.key !== requestKey;
  const data = loading ? null : result?.data ?? null;
  const error = loading ? null : result?.error ?? null;

  // The rebuild itself. Callers set `refreshing` first (the initial state is
  // already true), so the effect below never sets state synchronously.
  const runRefresh = useCallback(async (announce: boolean) => {
    try {
      const res = await refreshOpportunities({ market, location });
      if (announce) {
        setToast(`Updated: ${res.total} opportunit${res.total === 1 ? 'y' : 'ies'} from your latest evidence.`);
      }
    } catch (err) {
      setRefreshError(errorMessage(err, 'Opportunities could not be updated; showing the last saved list.'));
    } finally {
      setRefreshing(false);
      setReloadKey((k) => k + 1);
    }
  }, [market, location]);

  useEffect(() => {
    // Deferred so a StrictMode double-mount in development rebuilds once.
    const timer = window.setTimeout(() => runRefresh(false), 0);
    return () => window.clearTimeout(timer);
  }, [runRefresh]);

  const refreshNow = () => {
    setRefreshing(true);
    setRefreshError(null);
    runRefresh(true);
  };

  const changeScope = (next: MarketOption | null) => {
    // A new scope rebuilds that scope's opportunities (see the effect above).
    setRefreshing(true);
    setScope(next);
    setCategory(null);
  };

  useEffect(() => {
    const controller = new AbortController();
    getScoringMethod(controller.signal).then(setMethod).catch(() => { /* dialog shows a fallback */ });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (refreshing) return undefined;
    const controller = new AbortController();
    listOpportunities({ status: statusParam(tab), market, location, min_score: minScore || undefined }, controller.signal)
      .then((res) => setResult({ key: requestKey, data: res, error: null }))
      .catch((err) => {
        if (!isCanceled(err)) setResult({ key: requestKey, data: null, error: errorMessage(err, 'Opportunities could not be loaded.') });
      });
    getOpportunitySources({ market, location }, controller.signal)
      .then(setSources)
      .catch(() => { /* the panel keeps its skeleton; the list still works */ });
    return () => controller.abort();
  }, [refreshing, tab, market, location, minScore, requestKey]);

  const handleUpdated = useCallback((updated: Opportunity) => {
    setResult((prev) => (prev?.data ? {
      ...prev,
      data: { ...prev.data, opportunities: prev.data.opportunities.map((o) => (o.id === updated.id ? updated : o)) },
    } : prev));
  }, []);

  const all = useMemo(() => data?.opportunities ?? [], [data]);
  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    all.forEach((o) => counts.set(o.category, (counts.get(o.category) ?? 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [all]);
  const shown = category ? all.filter((o) => o.category === category) : all;
  const activeTotal = sources ? Object.values(sources.active_by_category).reduce((a, b) => a + b, 0) : null;
  const noneYet = !loading && tab === 'active' && minScore === 0 && all.length === 0;

  return (
    <Box>
      <PageHeader
        title="Opportunities"
        subtitle="Leads worth investigating, built automatically from the market evidence you collect."
        action={(
          <Stack direction="row" spacing={1}>
            <ExportButton href={exportUrl('opportunities', { status: statusParam(tab), market, location })}
                          disabled={all.length === 0} />
            <Button variant="outlined" size="small" onClick={refreshNow} disabled={refreshing}
                    startIcon={refreshing ? <CircularProgress size={16} color="inherit" /> : <RefreshIcon />}>
              Update now
            </Button>
          </Stack>
        )}
      />

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 6, md: 3 }}>
          <Summary label="To review" value={activeTotal ?? <Skeleton width={40} />} />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <Summary label="High priority" tone="success.main"
                   value={loading ? <Skeleton width={40} /> : all.filter((o) => scoreBand(o.score).label === 'High priority').length} />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <Summary label="Evidence behind them"
                   value={sources ? `${sources.price_evidence.verified_prices + sources.search_interest.comparisons_collected}` : <Skeleton width={40} />} />
        </Grid>
        <Grid size={{ xs: 6, md: 3 }}>
          <Summary label="Last updated"
                   value={<Typography variant="body1" sx={{ fontWeight: 600 }}>
                     {refreshing ? 'Updating…' : formatDateTime(sources?.last_refreshed_at)}
                   </Typography>} />
        </Grid>
      </Grid>

      {/* Where the data comes from: open by default until there is something to review. */}
      <Accordion variant="outlined" disableGutters key={noneYet ? 'open' : 'closed'} defaultExpanded={noneYet}
                 sx={{ mb: 3, '&:before': { display: 'none' } }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>Where opportunities come from</Typography>
            <Typography variant="caption" color="text.secondary">
              They are not searched for. They are calculated from price checks and search-interest
              comparisons you run in other modules, then scored and ranked here.
            </Typography>
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <OpportunitySourcesPanel sources={sources} />
        </AccordionDetails>
      </Accordion>

      <Paper variant="outlined" sx={{ p: 1.5, mb: 2 }}>
        <Grid container spacing={1.5} sx={{ alignItems: 'flex-start' }}>
          <Grid size={{ xs: 12, md: 7 }}>
            <MarketScopeSelect value={scope} onChange={changeScope} />
          </Grid>
          <Grid size={{ xs: 12, sm: 7, md: 3 }}>
            <TextField select fullWidth size="small" label="Priority" value={minScore}
                       onChange={(e) => setMinScore(Number(e.target.value))}>
              {MIN_SCORES.map((s) => <MenuItem key={s.value} value={s.value}>{s.label}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid size={{ xs: 12, sm: 5, md: 2 }}>
            <Button fullWidth size="small" startIcon={<HelpOutlineIcon />} onClick={() => setMethodOpen(true)}
                    sx={{ height: 40 }}>
              How scoring works
            </Button>
          </Grid>
        </Grid>
        <Tabs value={tab} onChange={(_, v: StatusTab) => { setTab(v); setCategory(null); }}
              variant="scrollable" allowScrollButtonsMobile sx={{ mt: 1, minHeight: 40, '& .MuiTab-root': { minHeight: 40 } }}>
          {TABS.map((t) => <Tab key={t.value} value={t.value} label={t.label} />)}
        </Tabs>
        {categories.length > 1 && (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1.5 }}>
            <Chip size="small" label={`All types · ${all.length}`} color={category === null ? 'primary' : 'default'}
                  variant={category === null ? 'filled' : 'outlined'} onClick={() => setCategory(null)} />
            {categories.map(([key, count]) => (
              <Chip key={key} size="small" label={`${CATEGORY[key]?.label ?? key.replace(/_/g, ' ')} · ${count}`}
                    icon={CATEGORY[key]?.icon as React.ReactElement | undefined}
                    color={category === key ? 'primary' : 'default'} variant={category === key ? 'filled' : 'outlined'}
                    onClick={() => setCategory(key)} />
            ))}
          </Box>
        )}
      </Paper>

      {refreshError && <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setRefreshError(null)}>{refreshError}</Alert>}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}
               action={<Button color="inherit" size="small" onClick={() => setReloadKey((k) => k + 1)}>Retry</Button>}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Stack spacing={2} aria-busy="true" aria-label="Loading opportunities">
          {refreshing && (
            <Typography variant="body2" color="text.secondary">Building opportunities from your latest evidence…</Typography>
          )}
          {[0, 1, 2].map((i) => <Skeleton key={i} variant="rounded" height={150} />)}
        </Stack>
      ) : noneYet ? (
        <Paper variant="outlined" sx={{ p: { xs: 3, md: 4 }, textAlign: 'center', borderStyle: 'dashed' }}>
          <LightbulbOutlinedIcon sx={{ fontSize: 44, color: 'text.disabled', mb: 1 }} />
          <Typography variant="h6">No opportunities yet</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 560, mx: 'auto' }}>
            Opportunities appear once there is evidence to compare: the same product priced on two different
            days, several merchants priced at once, or a search-interest comparison. Use the sources above to
            collect it; this page updates itself when you come back.
          </Typography>
        </Paper>
      ) : shown.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="subtitle1">Nothing here</Typography>
          <Typography variant="body2" color="text.secondary">
            {tab === 'active' ? 'No opportunities match this priority or type.' : `No ${tab} opportunities for this selection.`}
          </Typography>
        </Paper>
      ) : (
        <>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
            {shown.length} opportunit{shown.length === 1 ? 'y' : 'ies'}, highest priority first.
            {' '}Scores rank leads for review; they are not a probability of success.
          </Typography>
          <Stack spacing={2}>
            {shown.map((o) => <OpportunityCard key={o.id} opportunity={o} onUpdated={handleUpdated} />)}
          </Stack>
        </>
      )}

      <Dialog open={methodOpen} onClose={() => setMethodOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>How opportunity scores work</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2 }}>
            Every opportunity gets a score from 0 to 100, combining four inputs. Each input is measured
            from the evidence on a 0–1 scale and weighted:
          </Typography>
          <Table size="small" sx={{ mb: 2 }}>
            <TableHead>
              <TableRow><TableCell>Input</TableCell><TableCell align="right">Weight</TableCell></TableRow>
            </TableHead>
            <TableBody>
              {Object.entries(method?.weights ?? {}).map(([name, weight]) => (
                <TableRow key={name}>
                  <TableCell>{INPUT_LABEL[name] ?? name}</TableCell>
                  <TableCell align="right">{Math.round(weight * 100)}%</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Typography variant="body2" sx={{ mb: 1 }}>
            <b>High priority</b> is 60 or more, <b>medium</b> 35–59, <b>low</b> below 35. If an input has
            no data it adds nothing, so a lead is never scored higher than its evidence supports.
          </Typography>
          <Alert severity="info">
            {method?.disclaimer ?? 'The score ranks leads for review. It is not a probability of commercial success.'}
          </Alert>
        </DialogContent>
        <DialogActions><Button onClick={() => setMethodOpen(false)}>Close</Button></DialogActions>
      </Dialog>

      <Snackbar open={Boolean(toast)} autoHideDuration={4000} onClose={() => setToast(null)}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
        <Alert severity="success" onClose={() => setToast(null)} variant="filled">{toast}</Alert>
      </Snackbar>
    </Box>
  );
};

export default Opportunities;
