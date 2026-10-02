import React, { useRef, useState } from 'react';
import { 
  Box, Typography, TextField, Button, Grid, Paper, Alert,
  CircularProgress, Table, Tooltip, IconButton, TableBody, TableCell, TableContainer,
  TableHead, TableRow, MenuItem
} from '@mui/material';
import { isAxiosError } from 'axios';
import SearchIcon from '@mui/icons-material/Search';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import PageHeader from '../../components/PageHeader/PageHeader';
import { searchLocalPrices } from '../../services/priceApi';
import type { LocalPriceSearchResponse } from '../../services/priceApi';

const RADIUS_OPTIONS = [5, 10, 15, 25];
const MAX_RADIUS = RADIUS_OPTIONS[RADIUS_OPTIONS.length - 1];

// Lowest/average/highest describe nothing until two distinct prices exist.
const MIN_PRICES_FOR_STATISTICS = 2;

const formatMiles = (distance: number | null | undefined) =>
  distance === null || distance === undefined ? '—' : `${distance} mi`;

/** The backend's own explanation, which says *why* a search failed. */
const errorMessage = (err: unknown): string => {
  if (isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === 'string' && detail) return detail;
    const status = err.response?.status;
    if (status === 502) return 'The search provider failed to respond. Try again in a moment.';
    if (status === 503) return 'Live market data is not configured (missing SerpApi key).';
    if (!err.response) return 'The MarketRadar server could not be reached.';
  }
  return 'An error occurred fetching local prices.';
};

const PriceIntelligence = () => {
  const [product, setProduct] = useState('');
  const [area, setArea] = useState('');
  const [radius, setRadius] = useState(25);
  const [referenceStore, setReferenceStore] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<LocalPriceSearchResponse | null>(null);

  // Only the newest request may render. Comparing against the live form
  // fields instead would blank out results as soon as the user edits an
  // input, and would let a slow earlier response overwrite a newer one.
  const requestIdRef = useRef(0);

  const handleSearch = async (e?: React.FormEvent, radiusOverride?: number) => {
    if (e) e.preventDefault();
    if (!product.trim() || !area.trim()) return;
    const searchRadius = radiusOverride ?? radius;

    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    setData(null);

    try {
      const response = await searchLocalPrices(product, area, searchRadius, referenceStore.trim() || undefined);
      if (requestId !== requestIdRef.current) return;
      setData(response);
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setError(errorMessage(err));
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  };

  const REASON_LABELS: Record<string, string> = {
    price_not_product_specific: 'The only price found was on a category or brand listing page, so it cannot be tied to this exact product.',
    merchant_identity_uncertain: 'The listing could not be tied to this specific store with enough confidence.',
    price_range: 'The source showed a price range rather than a single price.',
    ambiguous_price: 'Several unrelated prices appeared alongside this product.',
    size_unverified: 'The requested size could not be confirmed in the available evidence.',
    price_unavailable: 'The merchant lists the product but publishes no price.',
    different_product: 'The evidence describes a different product.',
    different_variant: 'The evidence describes a different variant of this product.',
    different_model: 'The evidence describes a different model or age.',
    different_size: 'The evidence describes a different size.',
    accessory_or_related_item: 'The evidence describes an accessory or related item, not the product itself.',
    insufficient_evidence: 'No evidence about this product was found for this merchant.',
  };

  const STAGE_LABELS: Record<string, string> = {
    search_center: 'Location resolution',
    merchant_discovery: 'Merchant discovery',
    merchant_website_evidence: 'Merchant website evidence',
    shopping_evidence: 'Shopping evidence',
  };

  return (
    <Box>
      <PageHeader 
        title="Price Intelligence" 
        subtitle="Compare prices for the same product across nearby stores."
      />

      <Paper sx={{ p: 3, mb: 4 }}>
        <form onSubmit={handleSearch}>
          <Grid container spacing={3} sx={{ alignItems: 'center' }}>
            <Grid size={{xs: 12, md: 4}}>
              <TextField
                fullWidth
                label="Product Name"
                value={product}
                onChange={(e) => setProduct(e.target.value)}
                placeholder="e.g. Apple iPhone 15 Pro 256GB"
                required
              />
            </Grid>
            
            <Grid size={{xs: 12, md: 3}}>
              <TextField
                fullWidth
                label="Location (City, State or ZIP)"
                value={area}
                onChange={(e) => setArea(e.target.value)}
                placeholder="e.g. San Francisco, CA"
                required
              />
            </Grid>

            <Grid size={{xs: 12, md: 2}}>
              <TextField
                select
                fullWidth
                label="Radius"
                value={radius}
                onChange={(e) => setRadius(Number(e.target.value))}
              >
                {RADIUS_OPTIONS.map((r) => (
                  <MenuItem key={r} value={r}>
                    {r} miles
                  </MenuItem>
                ))}
              </TextField>
            </Grid>

            <Grid size={{xs: 12, md: 3}}>
              <TextField
                fullWidth
                label="Reference Store (Optional)"
                value={referenceStore}
                onChange={(e) => setReferenceStore(e.target.value)}
                placeholder="e.g. Target"
              />
            </Grid>
            
            <Grid size={{xs: 12, md: 12}}>
              <Button
                type="submit"
                variant="contained"
                size="large"
                fullWidth
                disabled={loading || !product.trim() || !area.trim()}
                startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SearchIcon />}
                sx={{ height: 56 }}
              >
                Compare
              </Button>
            </Grid>
          </Grid>
        </form>
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 4 }}>
          {error}
        </Alert>
      )}

      {data && (
        <Box sx={{ mt: 4 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Results for <strong>{data.searched_product}</strong> within {data.searched_radius} miles
            of <strong>{data.search_center?.name || data.searched_area}</strong>.
          </Typography>
          {data.stages.filter((s) => s.status === 'error' || s.status === 'degraded').map((s) => (
            <Alert key={s.stage} severity={s.status === 'error' ? 'error' : 'warning'} sx={{ mb: 2 }}>
              <strong>{STAGE_LABELS[s.stage] || s.stage}</strong>{' '}
              {s.status === 'error'
                ? 'could not be completed, so results from this source are missing rather than absent.'
                : 'completed with reduced coverage.'}
              {s.detail ? ` (${s.detail})` : ''}
            </Alert>
          ))}

          {data.mixed_size_statistics && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Verified prices cover more than one size ({data.verified_sizes.join(', ')}).
              Add a size to your search to compare like for like.
            </Alert>
          )}

          {data.verified_local_prices > 0 && (
            <Grid container spacing={3} sx={{ mb: 4 }}>
              {data.reference_store && (
                <Grid size={{xs: 12, md: 6}}>
                  <Box sx={{ bgcolor: 'background.paper', border: 1, borderColor: 'divider', p: 3, borderRadius: 2 }}>
                    <Typography variant="subtitle2" sx={{ opacity: 0.8, mb: 1 }}>
                      Reference Store ({data.reference_store.merchant}) Price:
                    </Typography>
                    {data.reference_price && data.lowest_price !== null ? (
                      <>
                        <Typography variant="h4" sx={{ mb: 1 }}>
                          ${data.reference_price.toFixed(2)}
                        </Typography>
                        <Typography variant="body1" sx={{
                          color: data.lowest_price < data.reference_price ? 'warning.main' : 'success.main',
                          fontWeight: 'bold'
                        }}>
                          Lowest other store vs. reference: {(data.lowest_price - data.reference_price) > 0 ? '+' : ''}
                          ${(data.lowest_price - data.reference_price).toFixed(2)}
                        </Typography>
                      </>
                    ) : (
                      <Typography variant="h6" sx={{ opacity: 0.9 }}>
                        Price unavailable
                      </Typography>
                    )}
                  </Box>
                </Grid>
              )}
              <Grid size={{xs: 12, md: data.reference_store ? 6 : 12}}>
                <Box sx={{ bgcolor: 'primary.dark', p: 3, borderRadius: 2, color: 'white' }}>
                  {new Set(data.verified_price_observations.map((o) => o.price)).size >= MIN_PRICES_FOR_STATISTICS ? (
                    <>
                      <Typography variant="subtitle2" sx={{ opacity: 0.8, mb: 1 }}>
                        Lowest Verified Nearby Competitor:
                      </Typography>
                      <Typography variant="h4" sx={{ mb: 1 }}>
                        ${data.lowest_price?.toFixed(2) || '---'}
                      </Typography>
                      <Typography variant="body1">
                        Average: ${data.average_price?.toFixed(2) || '---'} | Highest: ${data.highest_price?.toFixed(2) || '---'}
                      </Typography>
                    </>
                  ) : (
                    <>
                      <Typography variant="subtitle2" sx={{ opacity: 0.8, mb: 1 }}>
                        One distinct verified price:
                      </Typography>
                      <Typography variant="h4" sx={{ mb: 1 }}>
                        ${data.lowest_price?.toFixed(2) || '---'}
                      </Typography>
                      <Typography variant="body2" sx={{ opacity: 0.9 }}>
                        Too few verified prices to state a lowest, average or highest.
                      </Typography>
                    </>
                  )}
                </Box>
              </Grid>
            </Grid>
          )}

          {(() => {
            if (data.nearby_merchants_discovered === 0) {
              return (
                <Paper sx={{ p: 4, textAlign: 'center', mb: 4 }}>
                  <Typography variant="h6" gutterBottom>No nearby stores found</Typography>
                  <Typography color="text.secondary" sx={{ mb: 3 }}>Try changing location or increasing the radius.</Typography>
                  {data.searched_radius < MAX_RADIUS && (
                    <Button
                      variant="outlined"
                      disabled={loading}
                      onClick={() => { setRadius(MAX_RADIUS); handleSearch(undefined, MAX_RADIUS); }}
                    >
                      Search again within {MAX_RADIUS} miles
                    </Button>
                  )}
                </Paper>
              );
            }
            if (data.product_evidence_found > 0 && data.verified_local_prices === 0) {
              return (
                <Paper sx={{ p: 4, textAlign: 'center', mb: 4 }}>
                  <Typography variant="h6" gutterBottom>Product found, but no verified prices</Typography>
                  <Typography color="text.secondary">The product appears in nearby merchants' online catalogues, but no price could be verified. Catalogue evidence does not confirm stock at a store.</Typography>
                </Paper>
              );
            }
            if (data.product_evidence_found === 0) {
              return (
                <Paper sx={{ p: 4, textAlign: 'center', mb: 4 }}>
                  <Typography variant="h6" gutterBottom>No product evidence found</Typography>
                  <Typography color="text.secondary">No verified product evidence was found at the discovered merchants. This does not establish that they do not sell it.</Typography>
                </Paper>
              );
            }
            return null;
          })()}

          {data.verified_local_prices > 0 && (
            <Box sx={{ mb: 6 }}>
              <Typography variant="h6" sx={{ mb: 2 }}>Verified Price Comparison</Typography>
              <TableContainer component={Paper}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Store</TableCell>
                      <TableCell>Distance</TableCell>
                      <TableCell>Product</TableCell>
                      <TableCell>Size</TableCell>
                      <TableCell align="right">Price</TableCell>
                      <TableCell>Source</TableCell>
                      <TableCell>Evidence</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.verified_price_observations.map((obs, idx) => (
                      <TableRow key={idx}>
                        <TableCell><Typography variant="subtitle2">{obs.merchant}</Typography></TableCell>
                        <TableCell>{formatMiles(obs.distance)}</TableCell>
                        <TableCell>{obs.product_name}</TableCell>
                        <TableCell>{obs.size || '---'}</TableCell>
                        <TableCell align="right"><Typography variant="body2" sx={{ fontWeight: 'bold' }}>${obs.price?.toFixed(2)}</Typography></TableCell>
                        <TableCell>
                          {obs.source_type === 'merchant_website_indexed' ? 'Merchant website' : 
                           obs.source_type === 'google_shopping' ? 'Google Shopping' : 
                           obs.source_type}
                        </TableCell>
                        <TableCell>
                          <Tooltip
                            arrow
                            placement="top"
                            title={obs.evidence_scope === 'catalog'
                              ? "Found in this merchant's online catalogue. This does not confirm stock at the physical address."
                              : 'Found in a shopping listing attributed to this merchant.'}
                          >
                            <Typography variant="body2" color="text.secondary">
                              {obs.evidence_scope === 'catalog' ? 'Catalogue' : 'Listing'}
                            </Typography>
                          </Tooltip>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )}

          {data.nearby_merchants_discovered > 0 && (
            <Box sx={{ mb: 6 }}>
              <Typography variant="h6" sx={{ mb: 2 }}>Nearby Physical Stores ({data.nearby_merchants_discovered})</Typography>
              <TableContainer component={Paper}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Store</TableCell>
                      <TableCell>Distance</TableCell>
                      <TableCell>Product</TableCell>
                      <TableCell align="right">Price</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.nearby_merchants.map((merchant, idx) => (
                      <TableRow key={idx}>
                        <TableCell><Typography variant="subtitle2">{merchant.merchant}</Typography></TableCell>
                        <TableCell>{formatMiles(merchant.distance)}</TableCell>
                        <TableCell>
                          {merchant.product_status === 'found' ? (
                            <Typography variant="body2">{merchant.product_name || 'Product found'} ✓</Typography>
                          ) : (
                            <Typography variant="body2" color="text.secondary">—</Typography>
                          )}
                        </TableCell>
                        <TableCell align="right">
                          {merchant.price_status === 'verified' ? (
                            <Typography variant="body2" color="success.main" sx={{ fontWeight: 'bold' }}>
                              ${merchant.price?.toFixed(2)}
                            </Typography>
                          ) : (
                            <Typography variant="body2" color="text.secondary">—</Typography>
                          )}
                        </TableCell>
                        <TableCell>
                          <Box sx={{ display: 'flex', alignItems: 'center' }}>
                            <Typography variant="body2" color={merchant.price_status === 'verified' ? 'success.main' : 'text.secondary'}>
                              {merchant.price_status === 'verified' ? '✓ Verified' : 
                               merchant.product_status === 'found' && merchant.price_status === 'unavailable' ? 'Price unavailable' :
                               merchant.product_status === 'not_found' ? 'Product not found in sources' : 'Unable to verify'}
                            </Typography>
                            {merchant.price_status !== 'verified' && (
                              <Tooltip title={
                                <React.Fragment>
                                  <Typography variant="body2" gutterBottom>
                                    {merchant.verification_reason && REASON_LABELS[merchant.verification_reason]
                                      ? REASON_LABELS[merchant.verification_reason]
                                      : merchant.product_status === 'found'
                                        ? 'Evidence indicates the merchant lists the product, but MarketRadar could not verify a current price.'
                                        : 'MarketRadar could not confidently identify this exact product in the available sources.'}
                                  </Typography>
                                  {merchant.evidence_scope === 'catalog' && (
                                    <Typography variant="caption" color="inherit" sx={{ display: 'block', mt: 1, opacity: 0.8 }}>
                                      Evidence covers the merchant's online catalogue, not confirmed stock at this address.
                                    </Typography>
                                  )}
                                </React.Fragment>
                              } arrow placement="top">
                                <IconButton size="small" sx={{ ml: 0.5, p: 0 }}>
                                  <InfoOutlinedIcon fontSize="inherit" color="action" />
                                </IconButton>
                              </Tooltip>
                            )}
                          </Box>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )}

        </Box>
      )}
    </Box>
  );
};

export default PriceIntelligence;

