import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Divider, Grid,
  Link, List, ListItemButton, ListItemText, Paper, Skeleton, Tab, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Tabs, TextField, Tooltip,
  Typography,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import TravelExploreOutlinedIcon from '@mui/icons-material/TravelExploreOutlined';
import BookmarkAddOutlinedIcon from '@mui/icons-material/BookmarkAddOutlined';
import RestartAltIcon from '@mui/icons-material/RestartAlt';

import PageHeader from '../../components/PageHeader/PageHeader';
import { searchOrganic, getRecentSearches } from '../../services/serpapiApi';
import type { RecentSearch } from '../../services/serpapiApi';
import { listSavedSearches, saveSearch } from '../../services/intelligenceApi';
import type { SavedSearch } from '../../types/intelligence';
import type { SerpLocalResult, SerpSearchResponse } from '../../types/serpapi';
import {
  errorMessage, formatDate, formatDateTime, humanize, isCanceled,
} from '../../utils/format';

const bestPosition = (positions: (number | null)[]): number | null => {
  const known = positions.filter((p): p is number => p !== null);
  return known.length > 0 ? Math.min(...known) : null;
};

const MarketResearch = () => {
  const [searchParams] = useSearchParams();
  // Prefilled from the URL (the Reports page links here), never auto-run:
  // a search spends a credit and only the user decides that.
  const [query, setQuery] = useState(() => searchParams.get('q') ?? '');
  const [location, setLocation] = useState(() => searchParams.get('location') ?? '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<SerpSearchResponse | null>(null);
  const [tabIndex, setTabIndex] = useState(0);

  const [recentSearches, setRecentSearches] = useState<RecentSearch[]>([]);
  const [recentLoading, setRecentLoading] = useState(true);
  const [recentError, setRecentError] = useState<string | null>(null);
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [savedLoading, setSavedLoading] = useState(true);
  const [savedError, setSavedError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const searchController = useRef<AbortController | null>(null);

  const loadRecent = useCallback(async (signal?: AbortSignal) => {
    try {
      setRecentSearches(await getRecentSearches(signal));
      setRecentError(null);
    } catch (err) {
      if (!isCanceled(err)) setRecentError(errorMessage(err, 'Recent searches could not be loaded.'));
    } finally {
      if (!signal?.aborted) setRecentLoading(false);
    }
  }, []);

  const loadSaved = useCallback(async (signal?: AbortSignal) => {
    try {
      setSavedSearches((await listSavedSearches('research', signal)).saved_searches);
      setSavedError(null);
    } catch (err) {
      if (!isCanceled(err)) setSavedError(errorMessage(err, 'Saved searches could not be loaded.'));
    } finally {
      if (!signal?.aborted) setSavedLoading(false);
    }
  }, []);

  // Both lists are free reads, loaded on arrival so the page is useful
  // before any credit is spent.
  useEffect(() => {
    const controller = new AbortController();
    void Promise.resolve().then(() => Promise.all([
      loadRecent(controller.signal), loadSaved(controller.signal),
    ]));
    return () => {
      controller.abort();
      searchController.current?.abort();
    };
  }, [loadRecent, loadSaved]);

  // One path for every search (button, recent, saved, related chip), so each
  // reports errors identically. A newer search aborts the older one, so a
  // slow response can never overwrite a later result.
  const handleSearch = async (searchQuery: string = query, searchLocation: string = location) => {
    const q = searchQuery.trim();
    if (!q) return;
    searchController.current?.abort();
    const controller = new AbortController();
    searchController.current = controller;

    setQuery(searchQuery);
    setLocation(searchLocation);
    setLoading(true);
    setError(null);
    setResults(null);
    setSaveMessage(null);
    setTabIndex(0);

    try {
      const data = await searchOrganic(q, searchLocation.trim() || undefined, controller.signal);
      if (controller.signal.aborted) return;
      setResults(data);
      loadRecent();
    } catch (err) {
      if (isCanceled(err) || controller.signal.aborted) return;
      setError(errorMessage(err, 'Unable to retrieve search results. Try again in a moment.'));
    } finally {
      if (searchController.current === controller) {
        setLoading(false);
        searchController.current = null;
      }
    }
  };

  const handleNewSearch = () => {
    searchController.current?.abort();
    setResults(null);
    setError(null);
    setSaveMessage(null);
    setQuery('');
    setLocation('');
  };

  const handleSave = async () => {
    if (!results) return;
    setSaving(true);
    setSaveMessage(null);
    try {
      const res = await saveSearch({
        module: 'research',
        query: results.query,
        location: results.location ?? undefined,
      });
      setSaveMessage({ ok: true, text: res.created ? 'Search saved.' : 'This search was already saved.' });
      loadSaved();
    } catch (err) {
      setSaveMessage({ ok: false, text: errorMessage(err, 'The search could not be saved.') });
    } finally {
      setSaving(false);
    }
  };

  const localArray: SerpLocalResult[] = results?.local_results ?? [];
  const relatedQuestions = results?.related_questions ?? [];
  const relatedSearches = results?.related_searches ?? [];

  const domainsMap: Record<string, { appearances: number; bestPos: number | null; positions: number[] }> = {};
  results?.results.forEach((r) => {
    if (!r.domain) return;
    const entry = domainsMap[r.domain] ?? { appearances: 0, bestPos: null, positions: [] };
    entry.appearances += 1;
    if (r.position !== null) {
      entry.positions.push(r.position);
      entry.bestPos = entry.bestPos === null ? r.position : Math.min(entry.bestPos, r.position);
    }
    domainsMap[r.domain] = entry;
  });

  const domainStats = Object.entries(domainsMap).map(([domain, stat]) => ({
    domain,
    appearances: stat.appearances,
    bestPos: stat.bestPos,
    avgPos: stat.positions.length > 0
      ? (stat.positions.reduce((a, b) => a + b, 0) / stat.positions.length).toFixed(1)
      : null,
  })).sort((a, b) => (a.bestPos ?? Infinity) - (b.bestPos ?? Infinity));

  const topOrganicPos = results ? bestPosition(results.results.map((r) => r.position)) : null;
  const topLocalPos = bestPosition(localArray.map((r) => r.position));
  const resolution = results?.location_resolution ?? null;

  const sidePanel = (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>Saved searches</Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
        Click one to fill the form and run it.
      </Typography>
      {savedLoading ? (
        <CircularProgress size={20} />
      ) : savedError ? (
        <Alert severity="warning" sx={{ py: 0 }}>{savedError}</Alert>
      ) : savedSearches.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          Nothing saved yet. Run a search and choose “Save search”.
        </Typography>
      ) : (
        <List dense disablePadding>
          {savedSearches.map((s) => (
            <ListItemButton key={s.id} disabled={loading} sx={{ px: 1, borderRadius: 1 }}
                            onClick={() => handleSearch(s.query, s.location ?? '')}>
              <ListItemText
                primary={s.label || s.query}
                secondary={`${s.location || 'No location'} · saved ${formatDate(s.created_at)}`}
                slotProps={{ primary: { noWrap: true, title: s.query } }}
              />
            </ListItemButton>
          ))}
        </List>
      )}

      <Divider sx={{ my: 2 }} />

      <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>Recent searches</Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
        Re-running a recent search is usually a cached result.
      </Typography>
      {recentLoading ? (
        <CircularProgress size={20} />
      ) : recentError ? (
        <Alert severity="warning" sx={{ py: 0 }}>{recentError}</Alert>
      ) : recentSearches.length === 0 ? (
        <Typography variant="body2" color="text.secondary">No searches have been run yet.</Typography>
      ) : (
        <List dense disablePadding>
          {recentSearches.map((s) => (
            <ListItemButton key={s.id} disabled={loading} sx={{ px: 1, borderRadius: 1 }}
                            onClick={() => handleSearch(s.query, s.location ?? '')}>
              <ListItemText
                primary={s.query}
                secondary={`${s.location || 'No location'} · ${s.organic_count} organic · ${s.local_count} local · ${formatDate(s.searched_at)}`}
                slotProps={{ primary: { noWrap: true, title: s.query } }}
              />
            </ListItemButton>
          ))}
        </List>
      )}
    </Paper>
  );

  return (
    <Box>
      <PageHeader
        title="Market Research"
        subtitle="See who is visible in search and local results for any topic, and what people ask about it."
      />

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 8, lg: 9 }} sx={{ minWidth: 0 }}>
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box component="form" onSubmit={(e) => { e.preventDefault(); handleSearch(); }}>
              <Grid container spacing={2} sx={{ alignItems: 'center' }}>
                <Grid size={{ xs: 12, sm: 5 }}>
                  <TextField
                    fullWidth label="What are you researching?" size="small" autoFocus
                    value={query} onChange={(e) => setQuery(e.target.value)}
                    disabled={loading} placeholder="e.g. specialty coffee roasters"
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <TextField
                    fullWidth label="Location (optional)" size="small"
                    value={location} onChange={(e) => setLocation(e.target.value)}
                    disabled={loading} placeholder="e.g. Austin, Texas"
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 3 }}>
                  <Button
                    fullWidth type="submit" variant="contained" sx={{ height: 40 }}
                    startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SearchIcon />}
                    disabled={loading || !query.trim()}
                  >
                    Search
                  </Button>
                </Grid>
              </Grid>
            </Box>

            {(results || error) && (
            <Box sx={{ mt: 1.5, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
              <Box sx={{ flexGrow: 1 }} />
              {/* The cache indicator describes this result, not an account balance. */}
              {results?.cache_hit && (
                <Chip size="small" label="Cached result" color="success" variant="outlined" />
              )}
              {results && (
                <Button size="small" variant="outlined" startIcon={<BookmarkAddOutlinedIcon />}
                        onClick={handleSave} disabled={saving}>
                  Save search
                </Button>
              )}
              <Button size="small" startIcon={<RestartAltIcon />} onClick={handleNewSearch}>
                New search
              </Button>
            </Box>
            )}
            {saveMessage && (
              <Alert severity={saveMessage.ok ? 'success' : 'error'} sx={{ mt: 2 }}
                     onClose={() => setSaveMessage(null)}>
                {saveMessage.text}
              </Alert>
            )}
          </Paper>

          {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

          {loading && (
            <Paper variant="outlined" sx={{ p: 2, mb: 3 }} aria-busy="true" aria-label="Searching">
              {[0, 1, 2, 3, 4].map((i) => (
                <Box key={i} sx={{ mb: 2 }}>
                  <Skeleton width="55%" height={24} />
                  <Skeleton width="30%" height={16} />
                  <Skeleton width="90%" height={16} />
                </Box>
              ))}
            </Paper>
          )}

          {!results && !error && !loading && (
            <Paper variant="outlined" sx={{ p: { xs: 3, md: 5 }, mb: 3, textAlign: 'center', borderStyle: 'dashed' }}>
              <TravelExploreOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
              <Typography variant="h6" sx={{ mb: 0.5 }}>Research any market</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2, maxWidth: 520, mx: 'auto' }}>
                See who ranks in search, which local businesses appear, and what people ask about a topic.
                Try one of these:
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center', flexWrap: 'wrap' }}>
                {['specialty coffee roasters', 'bike repair shops', 'organic grocery delivery', 'pet grooming'].map((example) => (
                  <Chip key={example} label={example} variant="outlined" clickable
                        onClick={() => setQuery(example)} />
                ))}
              </Box>
            </Paper>
          )}

          {results && resolution?.ambiguous && (
            <Alert severity="warning" sx={{ mb: 3 }}>
              “{resolution.requested}” was ambiguous and was searched as {resolution.canonical_name}.
              {resolution.alternatives.length > 0 && ` Other matches: ${resolution.alternatives.join('; ')}.`}
            </Alert>
          )}

          {results && (
            <Box sx={{ mb: 3 }}>
              <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
                <Tabs value={tabIndex} onChange={(_, v) => setTabIndex(v)}
                      variant="scrollable" scrollButtons="auto" aria-label="market research tabs">
                  <Tab label={`Organic Results (${results.results.length})`} />
                  <Tab label={`Local Results (${localArray.length})`} />
                  <Tab label={`Domains (${domainStats.length})`} />
                  <Tab label={`Related questions (${relatedQuestions.length})`} />
                  <Tab label="Search Insights" />
                </Tabs>
              </Box>

              {tabIndex === 0 && (
                <TableContainer component={Paper}>
                  {results.results.length > 0 ? (
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell width="60">Pos</TableCell>
                          <TableCell width="180">Domain</TableCell>
                          <TableCell>Title & Snippet</TableCell>
                          <TableCell>URL</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {results.results.map((res, i) => (
                          <TableRow key={res.link ?? i}>
                            <TableCell>
                              <Typography variant="body2" sx={{ fontWeight: 600 }}>{res.position ?? '—'}</Typography>
                            </TableCell>
                            <TableCell>
                              <Chip label={res.domain || 'Not reported'} size="small" sx={{ bgcolor: 'background.default' }} />
                            </TableCell>
                            <TableCell>
                              <Typography variant="subtitle2" sx={{ mb: 0.5 }}>{res.title}</Typography>
                              <Typography variant="body2" color="text.secondary">{res.snippet}</Typography>
                            </TableCell>
                            <TableCell>
                              {res.link ? (
                                <Link href={res.link} target="_blank" rel="noopener" color="primary" underline="hover">
                                  Visit
                                </Link>
                              ) : (
                                <Typography variant="caption" color="text.disabled">No link</Typography>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <Box sx={{ p: 4, textAlign: 'center' }}>
                      <Typography variant="body2" color="text.secondary">
                        The search ran successfully and returned no organic results.
                      </Typography>
                    </Box>
                  )}
                </TableContainer>
              )}

              {tabIndex === 1 && (
                <TableContainer component={Paper}>
                  {localArray.length > 0 ? (
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell width="60">Pos</TableCell>
                          <TableCell>Business</TableCell>
                          <TableCell>Category</TableCell>
                          <TableCell>Rating</TableCell>
                          <TableCell>Reviews</TableCell>
                          <TableCell>Address</TableCell>
                          <TableCell>Website</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {localArray.map((res, i) => (
                          <TableRow key={res.place_id ?? i}>
                            <TableCell>
                              <Typography variant="body2" sx={{ fontWeight: 600 }}>{res.position ?? '—'}</Typography>
                            </TableCell>
                            <TableCell>
                              <Typography variant="subtitle2">{res.title ?? '—'}</Typography>
                            </TableCell>
                            <TableCell>
                              <Typography variant="caption" color="text.secondary">{res.type ?? '—'}</Typography>
                            </TableCell>
                            <TableCell>{res.rating ?? 'N/A'}</TableCell>
                            <TableCell>{res.reviews ?? 'N/A'}</TableCell>
                            <TableCell>
                              <Typography variant="body2" color="text.secondary">{res.address ?? '—'}</Typography>
                            </TableCell>
                            <TableCell>
                              {res.website ? (
                                <Link href={res.website} target="_blank" rel="noopener" color="primary" underline="hover">
                                  Visit
                                </Link>
                              ) : (
                                <Typography variant="caption" color="text.disabled">Not reported</Typography>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <Box sx={{ p: 4, textAlign: 'center' }}>
                      <Typography variant="body2" color="text.secondary">
                        This search returned no local results.
                      </Typography>
                    </Box>
                  )}
                </TableContainer>
              )}

              {tabIndex === 2 && (
                <TableContainer component={Paper}>
                  {domainStats.length > 0 ? (
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Domain</TableCell>
                          <TableCell align="right">Appearances</TableCell>
                          <TableCell align="right">Best Position</TableCell>
                          <TableCell align="right">Avg Position</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {domainStats.map((stat) => (
                          <TableRow key={stat.domain}>
                            <TableCell>
                              <Typography variant="body2" sx={{ fontWeight: 600 }}>{stat.domain}</Typography>
                            </TableCell>
                            <TableCell align="right">{stat.appearances}</TableCell>
                            <TableCell align="right">{stat.bestPos ?? '—'}</TableCell>
                            <TableCell align="right">{stat.avgPos ?? '—'}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <Box sx={{ p: 4, textAlign: 'center' }}>
                      <Typography variant="body2" color="text.secondary">
                        No organic result reported a domain.
                      </Typography>
                    </Box>
                  )}
                </TableContainer>
              )}

              {tabIndex === 3 && (
                <Paper sx={{ p: 2 }}>
                  <Alert severity="info" sx={{ mb: 2 }}>
                    “People also ask” questions come from the same Google response at no
                    extra cost. They are research leads, not evidence.
                  </Alert>
                  {relatedQuestions.length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                      Google returned no related questions for this search.
                    </Typography>
                  ) : (
                    relatedQuestions.map((rq, i) => (
                      <Box key={`${rq.question}-${i}`} sx={{ py: 1.5, borderTop: i ? 1 : 0, borderColor: 'divider' }}>
                        <Typography variant="subtitle2">{rq.question}</Typography>
                        {rq.snippet && (
                          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                            {rq.snippet}
                          </Typography>
                        )}
                        {rq.link && (
                          <Link href={rq.link} target="_blank" rel="noopener" underline="hover" variant="caption"
                                sx={{ wordBreak: 'break-all' }}>
                            {rq.title || rq.link}
                          </Link>
                        )}
                      </Box>
                    ))
                  )}
                </Paper>
              )}

              {tabIndex === 4 && (
                <Box>
                  <Grid container spacing={2} sx={{ mb: 3 }}>
                    {[
                      ['Organic Results', results.results.length],
                      ['Local Results', localArray.length],
                      ['Unique Domains', domainStats.length],
                      ['Best organic / local position',
                        `${topOrganicPos ?? '—'} / ${topLocalPos ?? '—'}`],
                    ].map(([label, value]) => (
                      <Grid size={{ xs: 12, sm: 6, md: 3 }} key={label}>
                        <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', height: '100%' }}>
                          <CardContent>
                            <Typography color="text.secondary" gutterBottom variant="subtitle2">{label}</Typography>
                            <Typography variant="h4">{value}</Typography>
                          </CardContent>
                        </Card>
                      </Grid>
                    ))}
                  </Grid>

                  {/* Only facts the response itself carries. */}
                  <Paper sx={{ p: 3 }} elevation={0} variant="outlined">
                    <Typography variant="h6" sx={{ mb: 2 }}>Data Source Transparency</Typography>
                    <Grid container spacing={2}>
                      <Grid size={{ xs: 6, sm: 4 }}>
                        <Typography variant="caption" color="text.secondary">Search</Typography>
                        <Typography variant="body2">{results.query}</Typography>
                      </Grid>
                      <Grid size={{ xs: 6, sm: 4 }}>
                        <Typography variant="caption" color="text.secondary">Engine</Typography>
                        <Typography variant="body2">{results.engine}</Typography>
                      </Grid>
                      <Grid size={{ xs: 6, sm: 4 }}>
                        <Typography variant="caption" color="text.secondary">Searched at</Typography>
                        <Typography variant="body2">{formatDateTime(results.searched_at)}</Typography>
                      </Grid>
                      <Grid size={{ xs: 6, sm: 4 }}>
                        <Typography variant="caption" color="text.secondary">Location requested</Typography>
                        <Typography variant="body2">{results.location || 'Not set'}</Typography>
                      </Grid>
                      <Grid size={{ xs: 6, sm: 4 }}>
                        <Typography variant="caption" color="text.secondary">Location searched</Typography>
                        <Typography variant="body2">{results.resolved_location || 'Not set'}</Typography>
                        {resolution?.ambiguous && (
                          <Tooltip title={resolution.alternatives.length > 0
                            ? `Other matches: ${resolution.alternatives.join('; ')}`
                            : 'No alternatives were reported.'}>
                            <Chip size="small" color="warning" variant="outlined" label="ambiguous" sx={{ mt: 0.5 }} />
                          </Tooltip>
                        )}
                      </Grid>
                      <Grid size={{ xs: 6, sm: 4 }}>
                        <Typography variant="caption" color="text.secondary">Cache</Typography>
                        <Typography variant="body2">
                          {results.cache_hit ? 'Recent cached result' : 'Fresh result'}
                        </Typography>
                      </Grid>
                      <Grid size={{ xs: 6, sm: 4 }}>
                        <Typography variant="caption" color="text.secondary">Provider status</Typography>
                        <Typography variant="body2">{humanize(results.provider_status)}</Typography>
                      </Grid>
                    </Grid>
                  </Paper>
                </Box>
              )}

              {relatedSearches.length > 0 && (
                <Paper variant="outlined" sx={{ p: 2, mt: 3 }}>
                  <Typography variant="subtitle2">Related searches</Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                    Research leads from the same search, not evidence. Click one to search it.
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    {relatedSearches.map((rs) => (
                      <Chip key={rs} label={rs} size="small" variant="outlined" clickable disabled={loading}
                            onClick={() => handleSearch(rs, results.location ?? '')} />
                    ))}
                  </Box>
                </Paper>
              )}
            </Box>
          )}
        </Grid>

        <Grid size={{ xs: 12, md: 4, lg: 3 }}>
          {sidePanel}
        </Grid>
      </Grid>
    </Box>
  );
};

export default MarketResearch;
