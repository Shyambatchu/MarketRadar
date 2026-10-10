import { useEffect, useMemo, useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogContentText, DialogTitle, Grid, IconButton, Link,
  Paper, Skeleton, Stack, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, TextField, Tooltip, Typography,
} from '@mui/material';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlined';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import BookmarkBorderIcon from '@mui/icons-material/BookmarkBorder';
import { Link as RouterLink } from 'react-router-dom';

import PageHeader from '../../components/PageHeader/PageHeader';
import EmptyState from '../../components/EmptyState/EmptyState';
import {
  createReport, deleteReport, deleteSavedSearch, listReports, listSavedSearches,
  reportUrl,
} from '../../services/intelligenceApi';
import type { ReportSummary, SavedSearch } from '../../types/intelligence';
import type { MarketOption } from '../../types/marketPulse';
import { errorMessage, formatDateTime, isCanceled } from '../../utils/format';
import MarketScopeSelect from '../../components/MarketScopeSelect/MarketScopeSelect';

const MODULE_LABEL: Record<SavedSearch['module'], string> = {
  research: 'Market Research',
  competitors: 'Competitors',
  products: 'Products',
  prices: 'Price Intelligence',
  interest: 'Search Interest',
  news: 'News',
};

const MODULE_ORDER: SavedSearch['module'][] = [
  'research', 'competitors', 'products', 'prices', 'interest', 'news',
];

const withParams = (path: string, params: Record<string, string | null | undefined>): string => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v) search.append(k, v); });
  const text = search.toString();
  return text ? `${path}?${text}` : path;
};

/** Where a saved search is re-run, using the query params each page reads. */
const runPath = (s: SavedSearch): string => {
  switch (s.module) {
    case 'research': return withParams('/research', { q: s.query, location: s.location });
    case 'competitors': return withParams('/competitors', { market: s.market ?? s.query, location: s.location });
    case 'products': return withParams('/products', { q: s.query, location: s.location });
    case 'prices': return withParams('/prices', { product: s.query, area: s.location });
    case 'interest': return withParams('/signals', { tab: 'interest', q: s.query });
    case 'news': return withParams('/signals', { tab: 'news', q: s.query });
    default: return '/';
  }
};

type PendingDelete =
  | { kind: 'report'; id: number; label: string }
  | { kind: 'search'; id: number; label: string };

const openReport = (id: number) => window.open(reportUrl(id), '_blank', 'noopener');

const Reports = () => {
  const [scope, setScope] = useState<MarketOption | null>(null);
  const [title, setTitle] = useState('');
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [created, setCreated] = useState<ReportSummary | null>(null);

  const [reports, setReports] = useState<ReportSummary[] | null>(null);
  const [reportsError, setReportsError] = useState<string | null>(null);
  const [searches, setSearches] = useState<SavedSearch[] | null>(null);
  const [searchesError, setSearchesError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listReports(controller.signal)
      .then((res) => setReports(res.reports))
      .catch((err) => {
        if (!isCanceled(err)) setReportsError(errorMessage(err, 'Reports could not be loaded.'));
      });
    listSavedSearches(undefined, controller.signal)
      .then((res) => setSearches(res.saved_searches))
      .catch((err) => {
        if (!isCanceled(err)) setSearchesError(errorMessage(err, 'Saved searches could not be loaded.'));
      });
    return () => controller.abort();
  }, [reloadKey]);

  const groupedSearches = useMemo(() => {
    if (!searches) return [];
    return MODULE_ORDER
      .map((module) => ({ module, items: searches.filter((s) => s.module === module) }))
      .filter((g) => g.items.length > 0);
  }, [searches]);

  const handleGenerate = async () => {
    setGenerating(true);
    setGenerateError(null);
    setCreated(null);
    try {
      const report = await createReport({
        market: scope?.market ?? null,
        location: scope?.location ?? null,
        title: title.trim() || undefined,
      });
      setCreated(report);
      setReports((prev) => [report, ...(prev ?? [])]);
      setTitle('');
    } catch (err) {
      setGenerateError(errorMessage(err, 'The report could not be generated.'));
    } finally {
      setGenerating(false);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      if (pendingDelete.kind === 'report') {
        await deleteReport(pendingDelete.id);
        setReports((prev) => prev?.filter((r) => r.id !== pendingDelete.id) ?? prev);
        if (created?.id === pendingDelete.id) setCreated(null);
      } else {
        await deleteSavedSearch(pendingDelete.id);
        setSearches((prev) => prev?.filter((s) => s.id !== pendingDelete.id) ?? prev);
      }
      setPendingDelete(null);
    } catch (err) {
      setDeleteError(errorMessage(err, 'It could not be deleted.'));
    } finally {
      setDeleting(false);
    }
  };

  const retry = (
    <Button
      color="inherit" size="small"
      onClick={() => { setReportsError(null); setSearchesError(null); setReloadKey((k) => k + 1); }}
    >
      Retry
    </Button>
  );

  return (
    <Box>
      <PageHeader
        title="Reports"
        subtitle="Print-ready snapshots of stored evidence, plus the searches you saved for later."
      />

      <Paper sx={{ p: 3, mb: 4 }}>
        <Typography variant="h6" gutterBottom>Generate report</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          A report freezes the evidence as it is at generation time. Open it and use its
          “Print / Save as PDF” button to keep a PDF copy.
        </Typography>
        <Grid container spacing={2} sx={{ alignItems: 'flex-start' }}>
          <Grid size={{ xs: 12, sm: 5 }}>
            <MarketScopeSelect value={scope} onChange={setScope} disabled={generating} />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              size="small" fullWidth label="Title (optional)" value={title}
              onChange={(e) => setTitle(e.target.value)} disabled={generating}
              slotProps={{ htmlInput: { maxLength: 200 } }}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 3 }}>
            <Button
              fullWidth variant="contained" sx={{ height: 40 }} onClick={handleGenerate}
              disabled={generating}
              startIcon={generating ? <CircularProgress size={18} color="inherit" /> : <DescriptionOutlinedIcon />}
            >
              Generate
            </Button>
          </Grid>
        </Grid>
        {generateError && <Alert severity="error" sx={{ mt: 2 }}>{generateError}</Alert>}
        {created && (
          <Alert
            severity={created.has_data ? 'success' : 'warning'} sx={{ mt: 2 }}
            action={(
              <Button color="inherit" size="small" endIcon={<OpenInNewIcon />}
                      onClick={() => openReport(created.id)}>
                Open report
              </Button>
            )}
          >
            “{created.title}” was generated.
            {!created.has_data && ' No stored evidence matched this selection, so the report is empty.'}
          </Alert>
        )}
      </Paper>

      <Typography variant="h6" gutterBottom>Generated reports</Typography>
      {reportsError && <Alert severity="error" sx={{ mb: 2 }} action={retry}>{reportsError}</Alert>}
      {!reports && !reportsError && <Skeleton variant="rounded" height={160} sx={{ mb: 4 }} />}
      {reports && reports.length === 0 && (
        <Box sx={{ mb: 4 }}>
          <EmptyState
            title="No reports yet"
            description="Generate a report above to capture the current competitors, verified prices, price alerts and opportunities for a market."
            icon={<DescriptionOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
          />
        </Box>
      )}
      {reports && reports.length > 0 && (
        <TableContainer component={Paper} sx={{ mb: 4 }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Title</TableCell>
                <TableCell>Market</TableCell>
                <TableCell>Location</TableCell>
                <TableCell>Created</TableCell>
                <TableCell align="right">Competitors</TableCell>
                <TableCell align="right">Verified prices</TableCell>
                <TableCell align="right">Price alerts</TableCell>
                <TableCell align="right">Opportunities</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {reports.map((r) => (
                <TableRow key={r.id} hover>
                  <TableCell>
                    <Link component="button" variant="body2" onClick={() => openReport(r.id)}
                          sx={{ textAlign: 'left' }}>
                      {r.title}
                    </Link>
                    {!r.has_data && (
                      <Tooltip title="No stored evidence matched this report's market and location.">
                        <Chip size="small" color="warning" variant="outlined" label="No data" sx={{ ml: 1 }} />
                      </Tooltip>
                    )}
                  </TableCell>
                  <TableCell>{r.market ?? 'All markets'}</TableCell>
                  <TableCell>{r.location ?? 'All locations'}</TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>{formatDateTime(r.created_at)}</TableCell>
                  <TableCell align="right">{r.competitors}</TableCell>
                  <TableCell align="right">{r.verified_prices}</TableCell>
                  <TableCell align="right">{r.price_alerts}</TableCell>
                  <TableCell align="right">{r.opportunities}</TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                    <Tooltip title="Open in a new tab">
                      <IconButton size="small" onClick={() => openReport(r.id)} aria-label={`Open ${r.title}`}>
                        <OpenInNewIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete report">
                      <IconButton
                        size="small" aria-label={`Delete ${r.title}`}
                        onClick={() => { setDeleteError(null); setPendingDelete({ kind: 'report', id: r.id, label: r.title }); }}
                      >
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Typography variant="h6" gutterBottom>Saved searches</Typography>
      {searchesError && <Alert severity="error" sx={{ mb: 2 }} action={retry}>{searchesError}</Alert>}
      {!searches && !searchesError && <Skeleton variant="rounded" height={120} />}
      {searches && searches.length === 0 && (
        <EmptyState
          title="No saved searches"
          description="Save a search from Market Research, Competitors, Products, Price Intelligence or Market Signals to re-run it from here."
          icon={<BookmarkBorderIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
        />
      )}
      {groupedSearches.length > 0 && (
        <Stack spacing={2}>
          {groupedSearches.map((group) => (
            <TableContainer component={Paper} key={group.module}>
              <Typography variant="subtitle2" sx={{ px: 2, pt: 1.5 }}>
                {MODULE_LABEL[group.module]}
              </Typography>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Query</TableCell>
                    <TableCell>Location</TableCell>
                    <TableCell>Saved</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {group.items.map((s) => (
                    <TableRow key={s.id} hover>
                      <TableCell>
                        {s.label && <Typography variant="body2" sx={{ fontWeight: 500 }}>{s.label}</Typography>}
                        <Typography variant="body2" color={s.label ? 'text.secondary' : 'text.primary'}>
                          {s.query}{s.market && s.market !== s.query ? ` · ${s.market}` : ''}
                        </Typography>
                      </TableCell>
                      <TableCell>{s.location ?? '—'}</TableCell>
                      <TableCell sx={{ whiteSpace: 'nowrap' }}>{formatDateTime(s.created_at)}</TableCell>
                      <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                        <Tooltip title="Open the page with this search filled in.">
                          <Button size="small" component={RouterLink} to={runPath(s)} startIcon={<PlayArrowIcon />}>
                            Run
                          </Button>
                        </Tooltip>
                        <Tooltip title="Delete saved search">
                          <IconButton
                            size="small" aria-label={`Delete saved search ${s.query}`}
                            onClick={() => { setDeleteError(null); setPendingDelete({ kind: 'search', id: s.id, label: s.label ?? s.query }); }}
                          >
                            <DeleteOutlineIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ))}
        </Stack>
      )}

      <Dialog open={Boolean(pendingDelete)} onClose={() => !deleting && setPendingDelete(null)}>
        <DialogTitle>
          {pendingDelete?.kind === 'report' ? 'Delete report?' : 'Delete saved search?'}
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            “{pendingDelete?.label}” will be permanently deleted. This cannot be undone.
            {pendingDelete?.kind === 'report' && ' The stored evidence itself is not affected.'}
          </DialogContentText>
          {deleteError && <Alert severity="error" sx={{ mt: 2 }}>{deleteError}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingDelete(null)} disabled={deleting}>Cancel</Button>
          <Button
            color="error" variant="contained" onClick={confirmDelete} disabled={deleting}
            startIcon={deleting ? <CircularProgress size={16} color="inherit" /> : <DeleteOutlineIcon />}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Reports;
