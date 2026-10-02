import { useState, useEffect, useRef } from 'react';
import {
  Box, Typography, TextField, Button, Paper, CircularProgress, Alert, Chip,
  Tabs, Tab, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Link,
  Grid, Card, CardContent
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { isAxiosError } from 'axios';

import PageHeader from '../../components/PageHeader/PageHeader';
import { searchOrganic, getRecentSearches } from '../../services/serpapiApi';
import type { RecentSearch } from '../../services/serpapiApi';
import type { SerpSearchResponse } from '../../types/serpapi';

const MarketResearch = () => {
  const [query, setQuery] = useState('');
  const [location, setLocation] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<SerpSearchResponse | null>(null);
  const [tabIndex, setTabIndex] = useState(0);
  const [recentSearches, setRecentSearches] = useState<RecentSearch[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    const fetchInitialData = async () => {
      try {
        const recentData = await getRecentSearches(controller.signal);
        setRecentSearches(recentData);
      } catch (err) {
        if (!isAxiosError(err) || err.code !== 'ERR_CANCELED') {
          console.error("Failed to fetch initial data.");
        }
      }
    };
    fetchInitialData();
    return () => controller.abort();
  }, []);

  const isSearching = useRef(false);

  // One path for every search, so "Open" on a recent search reports errors
  // exactly as the Search button does instead of swallowing them.
  const handleSearch = async (searchQuery: string = query, searchLocation: string = location) => {
    if (!searchQuery.trim() || isSearching.current) return;
    isSearching.current = true;
    setLoading(true);
    setError(null);
    setResults(null);
    setTabIndex(0);

    try {
      const data = await searchOrganic(searchQuery, searchLocation);
      setResults(data);
      try {
        const rData = await getRecentSearches();
        setRecentSearches(rData);
      } catch {
        // Refreshing the recent-search list is cosmetic; the result stands.
      }
    } catch (err) {
      if (isAxiosError(err)) {
        const detail = err.response?.data?.detail;
        // 422 is a location that has no provider-supported equivalent; the
        // backend message already explains what to type instead. 502 is a
        // provider failure, which is not the same as finding no results.
        if (err.response?.status === 422) {
          setError(detail || 'That location could not be matched to a supported search location.');
        } else if (err.response?.status === 502) {
          setError(detail || 'The search provider did not respond. No results were retrieved.');
        } else {
          setError(detail || 'Unable to retrieve search results. Try again in a moment.');
        }
      } else {
        setError('An unexpected error occurred.');
      }
    } finally {
      setLoading(false);
      isSearching.current = false;
    }
  };

  const localResultsList = results?.local_results?.places || results?.local_results || [];
  const localArray = Array.isArray(localResultsList) ? localResultsList : [];

  const domainsMap: Record<string, { appearances: number; bestPos: number; totalPos: number }> = {};
  if (results) {
    results.results.forEach(r => {
      if (r.domain) {
        if (!domainsMap[r.domain]) {
          domainsMap[r.domain] = { appearances: 0, bestPos: 9999, totalPos: 0 };
        }
        domainsMap[r.domain].appearances += 1;
        domainsMap[r.domain].totalPos += (r.position || 0);
        if ((r.position || 9999) < domainsMap[r.domain].bestPos) {
          domainsMap[r.domain].bestPos = r.position || 9999;
        }
      }
    });
  }

  const domainStats = Object.entries(domainsMap).map(([domain, stat]) => ({
    domain,
    appearances: stat.appearances,
    bestPos: stat.bestPos,
    avgPos: (stat.totalPos / stat.appearances).toFixed(1)
  })).sort((a, b) => a.bestPos - b.bestPos);

  const topOrganicPos = results && results.results.length > 0 ? Math.min(...results.results.map(r => r.position || 9999)) : 'N/A';
  const topLocalPos = localArray.length > 0 ? Math.min(...localArray.map((r: any) => r.position || 9999)) : 'N/A';

  return (
    <Box>
      <PageHeader 
        title="Market Research" 
        subtitle="Search and analyze market visibility across search engines and local results."
      />

      <Paper sx={{ p: 3, mb: 4 }}>
        <Grid container spacing={2} sx={{ alignItems: 'center' }}>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              fullWidth
              label="Location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              disabled={loading}
              size="small"
              placeholder="e.g. New Jersey, United States"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              fullWidth
              label="Search Query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={loading}
              size="small"
              placeholder="e.g. coffee shops in New Jersey"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 2 }}>
            <Button
              fullWidth
              variant="contained"
              startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SearchIcon />}
              onClick={() => handleSearch()}
              disabled={loading || !query.trim()}
              sx={{ height: 40 }}
            >
              Search
            </Button>
          </Grid>
        </Grid>
        
        {/* No usage or quota figures here: Market Research does not depend on
            /api/serpapi/usage, which stays available for diagnostics. The cache
            indicator describes this result, not an account balance. */}
        {results?.cache_hit && (
          <Box sx={{ mt: 2, display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <Chip size="small" label="Cached result" color="success" variant="outlined" />
          </Box>
        )}
      </Paper>

      
      {recentSearches.length > 0 && !results && (
        <Box sx={{ mb: 4 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>Recent Searches</Typography>
          <Grid container spacing={2}>
            {recentSearches.map((search) => (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={search.id}>
                <Card variant="outlined" sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <CardContent sx={{ flexGrow: 1 }}>
                    <Typography variant="subtitle1" sx={{ fontWeight: "bold" }} noWrap title={search.query}>
                      {search.query}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }} noWrap>
                      {search.location || 'No location'}
                    </Typography>
                    <Typography variant="caption" sx={{ display: "block", mb: 2 }}>
                      {search.organic_count} organic · {search.local_count} local
                    </Typography>
                    
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 'auto' }}>
                      <Typography variant="caption" color="text.disabled">
                        {new Date(search.searched_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                      </Typography>
                      <Button 
                        size="small" 
                        variant="outlined" 
                        disabled={loading}
                        onClick={() => {
                          setQuery(search.query);
                          setLocation(search.location || '');
                          // Usually a cache hit, but it is a real search and
                          // reports failures like one.
                          handleSearch(search.query, search.location || '');
                        }}
                      >
                        Open
                      </Button>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 4, borderRadius: 2 }}>
          {error}
        </Alert>
      )}

      {results && (
        <Box sx={{ mb: 3 }}>
          <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
            <Tabs value={tabIndex} onChange={(_, v) => setTabIndex(v)} aria-label="market research tabs">
              <Tab label={`Organic Results (${results.results.length})`} />
              <Tab label={`Local Results (${localArray.length})`} />
              <Tab label={`Domains (${domainStats.length})`} />
              <Tab label="Search Insights" />
            </Tabs>
          </Box>

          {tabIndex === 0 && (
            <TableContainer component={Paper}>
              {results.results.length > 0 ? (
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell width="80">Pos</TableCell>
                      <TableCell width="200">Domain</TableCell>
                      <TableCell>Title & Snippet</TableCell>
                      <TableCell>URL</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {results.results.map((res, i) => (
                      <TableRow key={i}>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>{res.position}</Typography>
                        </TableCell>
                        <TableCell>
                          <Chip label={res.domain || 'N/A'} size="small" sx={{ bgcolor: 'background.default' }} />
                        </TableCell>
                        <TableCell>
                          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>{res.title}</Typography>
                          <Typography variant="body2" color="text.secondary">{res.snippet}</Typography>
                        </TableCell>
                        <TableCell>
                          <Link href={res.link || '#'} target="_blank" rel="noopener" color="primary" underline="hover">
                            Visit
                          </Link>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <Box sx={{ p: 4, textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">No data available for this search.</Typography>
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
                      <TableCell width="80">Pos</TableCell>
                      <TableCell>Business</TableCell>
                      <TableCell>Category</TableCell>
                      <TableCell>Rating</TableCell>
                      <TableCell>Reviews</TableCell>
                      <TableCell>Address</TableCell>
                      <TableCell>Website</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {localArray.map((res: any, i: number) => (
                      <TableRow key={i}>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>{res.position}</Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="subtitle2">{res.title}</Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption" color="text.secondary">{res.type}</Typography>
                        </TableCell>
                        <TableCell>
                          {res.rating ? res.rating : 'N/A'}
                        </TableCell>
                        <TableCell>
                          {res.reviews ? res.reviews : 'N/A'}
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" color="text.secondary">{res.address}</Typography>
                        </TableCell>
                        <TableCell>
                          {res.website || res.links?.website ? (
                            <Link href={res.website || res.links?.website} target="_blank" rel="noopener" color="primary" underline="hover">
                              Visit
                            </Link>
                          ) : 'N/A'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <Box sx={{ p: 4, textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">No local results returned.</Typography>
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
                    {domainStats.map((stat, i) => (
                      <TableRow key={i}>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>{stat.domain}</Typography>
                        </TableCell>
                        <TableCell align="right">{stat.appearances}</TableCell>
                        <TableCell align="right">{stat.bestPos}</TableCell>
                        <TableCell align="right">{stat.avgPos}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <Box sx={{ p: 4, textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">No data available for this search.</Typography>
                </Box>
              )}
            </TableContainer>
          )}

          {tabIndex === 3 && (
            <Box>
              <Grid container spacing={2} sx={{ mb: 4 }}>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                  <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}>
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom variant="subtitle2">Organic Results</Typography>
                      <Typography variant="h4">{results.results.length}</Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                  <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}>
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom variant="subtitle2">Local Results</Typography>
                      <Typography variant="h4">{localArray.length}</Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                  <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}>
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom variant="subtitle2">Unique Domains</Typography>
                      <Typography variant="h4">{domainStats.length}</Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                  <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}>
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom variant="subtitle2">Top Positions</Typography>
                      <Typography variant="h4">O: {topOrganicPos !== 9999 ? topOrganicPos : '-'} / L: {topLocalPos !== 9999 ? topLocalPos : '-'}</Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>

              <Paper sx={{ p: 3, mb: 4 }} elevation={0} variant="outlined">
                <Typography variant="h6" sx={{ mb: 2 }}>Data Source Transparency</Typography>
                <Grid container spacing={2}>
                  <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                    <Typography variant="caption" color="text.secondary">Search</Typography>
                    <Typography variant="body2">{results.query || query}</Typography>
                  </Grid>
                  <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                    <Typography variant="caption" color="text.secondary">Location</Typography>
                    <Typography variant="body2">{results.location || 'Not set'}</Typography>
                    {results.resolved_location && results.resolved_location !== results.location && (
                      <Typography variant="caption" color="text.disabled" sx={{ display: 'block' }}>
                        resolved to {results.resolved_location}
                      </Typography>
                    )}
                  </Grid>
                  <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                    <Typography variant="caption" color="text.secondary">Engine</Typography>
                    <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>{results.engine || 'google'}</Typography>
                  </Grid>
                  <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                    <Typography variant="caption" color="text.secondary">Language</Typography>
                    <Typography variant="body2">English (hl=en)</Typography>
                  </Grid>
                  <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                    <Typography variant="caption" color="text.secondary">Country</Typography>
                    <Typography variant="body2">United States (gl=us)</Typography>
                  </Grid>
                  <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                    <Typography variant="caption" color="text.secondary">Cache</Typography>
                    <Typography variant="body2">{results.cache_hit ? 'Hit' : 'Miss'}</Typography>
                  </Grid>
                </Grid>
              </Paper>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
};

export default MarketResearch;
