import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, Grid, Link, MenuItem, Paper,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField,
  Typography,
} from '@mui/material';
import NewspaperOutlinedIcon from '@mui/icons-material/NewspaperOutlined';
import BookmarkAddOutlinedIcon from '@mui/icons-material/BookmarkAddOutlined';

import EmptyState from '../../components/EmptyState/EmptyState';
import { listSavedNews, saveSearch, searchNews } from '../../services/intelligenceApi';
import type { NewsArticle, NewsSearchResponse } from '../../types/intelligence';
import { errorMessage, formatDate, formatDateTime, isCanceled } from '../../utils/format';

const COUNTRY_PATTERN = /^[a-z]{2}$/;

const published = (a: NewsArticle): string =>
  a.published_at ? formatDateTime(a.published_at) : (a.published_label || 'Date not reported');

const NewsTab = ({ initialQuery }: { initialQuery: string }) => {
  const [query, setQuery] = useState(initialQuery);
  const [country, setCountry] = useState('us');
  const [sort, setSort] = useState<'relevance' | 'date'>('relevance');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<NewsSearchResponse | null>(null);
  const [saveMessage, setSaveMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  const [collected, setCollected] = useState<NewsArticle[]>([]);
  const [collectedTotal, setCollectedTotal] = useState(0);
  const [collectedLoading, setCollectedLoading] = useState(true);
  const [collectedError, setCollectedError] = useState<string | null>(null);
  const [filterInput, setFilterInput] = useState('');
  const [activeFilter, setActiveFilter] = useState('');

  const searchController = useRef<AbortController | null>(null);
  const collectedController = useRef<AbortController | null>(null);

  // Collected news is read from the database: free, so it loads on arrival.
  const loadCollected = useCallback(async (filter: string) => {
    collectedController.current?.abort();
    const controller = new AbortController();
    collectedController.current = controller;
    setCollectedLoading(true);
    setCollectedError(null);
    try {
      const res = await listSavedNews(filter || undefined, controller.signal);
      if (controller.signal.aborted) return;
      setCollected(res.articles);
      setCollectedTotal(res.total);
    } catch (err) {
      if (!isCanceled(err)) setCollectedError(errorMessage(err, 'Collected news could not be loaded.'));
    } finally {
      if (collectedController.current === controller) setCollectedLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(() => loadCollected(''));
    return () => {
      collectedController.current?.abort();
      searchController.current?.abort();
    };
  }, [loadCollected]);

  const countryValue = country.trim().toLowerCase();
  const countryInvalid = !COUNTRY_PATTERN.test(countryValue);

  const handleSearch = async () => {
    const q = query.trim();
    if (!q || countryInvalid) return;
    searchController.current?.abort();
    const controller = new AbortController();
    searchController.current = controller;
    setLoading(true);
    setError(null);
    setResult(null);
    setSaveMessage(null);
    try {
      const res = await searchNews({ q, gl: countryValue, sort }, controller.signal);
      if (controller.signal.aborted) return;
      setResult(res);
      // The search stores what it found, so the collection has changed.
      loadCollected(activeFilter);
    } catch (err) {
      if (!isCanceled(err)) setError(errorMessage(err));
    } finally {
      if (searchController.current === controller) setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!result) return;
    setSaving(true);
    setSaveMessage(null);
    try {
      const res = await saveSearch({ module: 'news', query: result.query });
      setSaveMessage({ ok: true, text: res.created ? 'Search saved.' : 'This search was already saved.' });
    } catch (err) {
      setSaveMessage({ ok: false, text: errorMessage(err, 'The search could not be saved.') });
    } finally {
      setSaving(false);
    }
  };

  const applyFilter = (value: string) => {
    setActiveFilter(value);
    loadCollected(value);
  };

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box component="form" onSubmit={(e) => { e.preventDefault(); handleSearch(); }}>
          <Grid container spacing={2} sx={{ alignItems: 'flex-start' }}>
            <Grid size={{ xs: 12, md: 5 }}>
              <TextField
                fullWidth size="small" label="Query" value={query}
                onChange={(e) => setQuery(e.target.value)} disabled={loading}
                placeholder="e.g. specialty coffee prices"
              />
            </Grid>
            <Grid size={{ xs: 6, md: 2 }}>
              <TextField
                fullWidth size="small" label="Country" value={country}
                onChange={(e) => setCountry(e.target.value)} disabled={loading}
                error={countryInvalid}
                helperText={countryInvalid ? 'Two letters, e.g. us, gb, in' : '2-letter code'}
                slotProps={{ htmlInput: { maxLength: 2 } }}
              />
            </Grid>
            <Grid size={{ xs: 6, md: 2 }}>
              <TextField
                select fullWidth size="small" label="Sort" value={sort} disabled={loading}
                onChange={(e) => setSort(e.target.value as 'relevance' | 'date')}
              >
                <MenuItem value="relevance">Relevance</MenuItem>
                <MenuItem value="date">Date</MenuItem>
              </TextField>
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <Button
                fullWidth type="submit" variant="contained" sx={{ height: 40 }}
                startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <NewspaperOutlinedIcon />}
                disabled={loading || !query.trim() || countryInvalid}
              >
                Search news
              </Button>
            </Grid>
          </Grid>
        </Box>
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      {result && (
        <Box sx={{ mb: 4 }}>
          <Box sx={{ mb: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <Typography variant="h6" sx={{ flexGrow: 1 }}>
              News for “{result.query}”
              <Typography component="span" variant="body2" color="text.secondary">
                {' '}· {result.gl.toUpperCase()} · sorted by {result.sort} · {result.total} article(s)
              </Typography>
            </Typography>
            {result.cache_hit && <Chip size="small" label="Cached result" color="success" variant="outlined" />}
            <Button size="small" variant="outlined" startIcon={<BookmarkAddOutlinedIcon />}
                    onClick={handleSave} disabled={saving}>
              Save search
            </Button>
          </Box>
          {saveMessage && (
            <Alert severity={saveMessage.ok ? 'success' : 'error'} sx={{ mb: 2 }}
                   onClose={() => setSaveMessage(null)}>
              {saveMessage.text}
            </Alert>
          )}
          {result.detail && <Alert severity="info" sx={{ mb: 2 }}>{result.detail}</Alert>}

          {result.articles.length === 0 ? (
            <EmptyState
              title="No news articles for this query"
              description="The search ran successfully and Google News returned no articles."
              icon={<NewspaperOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
            />
          ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell width="50">Pos</TableCell>
                    <TableCell>Headline</TableCell>
                    <TableCell>Source</TableCell>
                    <TableCell>Published</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {result.articles.map((a, i) => (
                    <TableRow key={a.link || i} hover>
                      <TableCell>{a.position ?? '—'}</TableCell>
                      <TableCell>
                        {a.link ? (
                          <Link href={a.link} target="_blank" rel="noopener noreferrer" underline="hover">
                            {a.title}
                          </Link>
                        ) : a.title}
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{a.source_name ?? 'Not reported'}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption">{published(a)}</Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>
      )}

      <Box sx={{ mb: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h6">Collected news</Typography>
          <Typography variant="caption" color="text.secondary">
            Every article a news search has returned, stored with when it was first and last seen.
            Reading this list is free.
          </Typography>
        </Box>
        <Box component="form" sx={{ display: 'flex', gap: 1 }}
             onSubmit={(e) => { e.preventDefault(); applyFilter(filterInput.trim()); }}>
          <TextField size="small" label="Filter by query" value={filterInput}
                     onChange={(e) => setFilterInput(e.target.value)} />
          <Button type="submit" size="small" variant="outlined" disabled={collectedLoading}>Apply</Button>
          {activeFilter && (
            <Button size="small" onClick={() => { setFilterInput(''); applyFilter(''); }}>Clear</Button>
          )}
        </Box>
      </Box>

      {collectedLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}><CircularProgress size={28} /></Box>
      ) : collectedError ? (
        <Alert severity="error">{collectedError}</Alert>
      ) : collected.length === 0 ? (
        <EmptyState
          title={activeFilter ? `No collected news for “${activeFilter}”` : 'No news collected yet'}
          description={activeFilter
            ? 'The filter matches the exact query a news search was run with. Try the full query text, or clear the filter.'
            : 'Run a news search above. The articles it returns are stored here with their source and dates.'}
          icon={<NewspaperOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
        />
      ) : (
        <>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
            {collectedTotal > collected.length
              ? `Showing the newest ${collected.length} of ${collectedTotal}.`
              : `${collectedTotal} article(s), newest first.`}
          </Typography>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Headline</TableCell>
                  <TableCell>Source</TableCell>
                  <TableCell>Query</TableCell>
                  <TableCell>Published</TableCell>
                  <TableCell>First seen</TableCell>
                  <TableCell>Last seen</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {collected.map((a, i) => (
                  <TableRow key={a.id ?? i} hover>
                    <TableCell>
                      {a.link ? (
                        <Link href={a.link} target="_blank" rel="noopener noreferrer" underline="hover">
                          {a.title}
                        </Link>
                      ) : a.title}
                    </TableCell>
                    <TableCell><Typography variant="body2">{a.source_name ?? 'Not reported'}</Typography></TableCell>
                    <TableCell><Typography variant="caption" color="text.secondary">{a.query ?? '—'}</Typography></TableCell>
                    <TableCell><Typography variant="caption">{published(a)}</Typography></TableCell>
                    <TableCell><Typography variant="caption">{formatDate(a.first_seen_at)}</Typography></TableCell>
                    <TableCell><Typography variant="caption">{formatDate(a.last_seen_at)}</Typography></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}
    </Box>
  );
};

export default NewsTab;
