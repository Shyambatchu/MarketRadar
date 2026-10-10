import React, { useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Box, Typography, TextField, Button, Grid, Paper, Alert,
  CircularProgress, Table, Tooltip, TableBody, TableCell, TableContainer,
  TableHead, TableRow, MenuItem
} from '@mui/material';
import { isAxiosError } from 'axios';
import SearchIcon from '@mui/icons-material/Search';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import BookmarkAddOutlinedIcon from '@mui/icons-material/BookmarkAddOutlined';
import HistoryIcon from '@mui/icons-material/History';
import PageHeader from '../../components/PageHeader/PageHeader';
import { searchLocalPrices } from '../../services/priceApi';
import type { LocalPriceSearchResponse, NearbyMerchantStatus } from '../../services/priceApi';
import { saveSearch } from '../../services/intelligenceApi';
import { errorMessage as sharedErrorMessage, formatMoney } from '../../utils/format';
import PriceChanges from './PriceChanges';

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
    if (status === 502) return 'The search provider failed to respond, so no prices could be compared. This is not the same as finding none.';
    if (status === 503) return 'Live market data is not configured (missing SerpApi key).';
    if (!err.response) return 'The MarketRadar server could not be reached.';
  }
  return sharedErrorMessage(err, 'An error occurred fetching local prices.');
};

/**
 * The backend may attach a currency to a merchant row; the shared type does
 * not declare it yet, so it is read defensively.
 */
const merchantCurrency = (m: NearbyMerchantStatus, fallback: string | null): string | null => {
  const value = m.currency;
  return value ?? fallback;
};

const PriceIntelligence = () => {
  const [searchParams] = useSearchParams();
  // Links from other pages prefill the form; nothing runs (or spends a
  // credit) until the user presses Compare.
  const [product, setProduct] = useState(() => searchParams.get('product') ?? '');
  const [area, setArea] = useState(() => searchParams.get('area') ?? '');
  const [radius, setRadius] = useState(25);
  const [referenceStore, setReferenceStore] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<LocalPriceSearchResponse | null>(null);
  // Bumped after a search so "Price changes" reloads with the new evidence.
  const [alertsRefresh, setAlertsRefresh] = useState(0);
  const [saveState, setSaveState] = useState<{ saving: boolean; message: string | null; error: boolean }>(
    { saving: false, message: null, error: false });

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
    setSaveState({ saving: false, message: null, error: false });

    try {
      const response = await searchLocalPrices(product.trim(), area.trim(), searchRadius, referenceStore.trim() || undefined);
      if (requestId !== requestIdRef.current) return;
      setData(response);
      if (response.persisted_observations > 0) setAlertsRefresh((n) => n + 1);
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setError(errorMessage(err));
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  };

  const handleSaveSearch = async () => {
    if (!data) return;
    setSaveState({ saving: true, message: null, error: false });
    try {
      const res = await saveSearch({
        module: 'prices', query: data.searched_product, location: data.searched_area || undefined,
      });
      setSaveState({
        saving: false, error: false,
        message: res.created ? 'Search saved.' : 'This search was already saved.',
      });
    } catch (err) {
      setSaveState({ saving: false, error: true, message: sharedErrorMessage(err, 'The search could not be saved.') });
    }
  };

  // Statistics need two or more distinct prices in a single currency.
  const distinctPrices = data
    ? new Set(data.verified_price_observations
      .filter((o) => o.price !== null)
      .map((o) => `${o.price}|${o.currency ?? ''}`)).size
    : 0;
  const singleObservation = data?.verified_price_observations.find((o) => o.price !== null) ?? null;
  const showStatistics = !!data && !data.mixed_currency_statistics
    && data.verified_local_prices >= MIN_PRICES_FOR_STATISTICS
    && distinctPrices >= MIN_PRICES_FOR_STATISTICS;
  const referenceCurrency = data?.reference_store
    ? merchantCurrency(data.reference_store, data.currency) : null;
  const hasReferencePrice = data?.reference_price !== null && data?.reference_price !== undefined;
  // A difference is only meaningful when both prices share a currency.
  const referenceDelta = data && hasReferencePrice && data.lowest_price !== null
    && !data.mixed_currency_statistics
    && (referenceCurrency === null || data.currency === null || referenceCurrency === data.currency)
    ? data.lowest_price - (data.reference_price as number) : null;

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
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ flexGrow: 1 }}>
              Results for <strong>{data.searched_product}</strong> within {data.searched_radius} miles
              of <strong>{data.search_center?.name || data.searched_area}</strong>.
            </Typography>
            <Button size="small" onClick={handleSaveSearch} disabled={saveState.saving}
                    startIcon={saveState.saving
                      ? <CircularProgress size={16} /> : <BookmarkAddOutlinedIcon />}>
              Save search
            </Button>
            {saveState.message && (
              <Typography variant="caption" color={saveState.error ? 'error' : 'success.main'}>
                {saveState.message}
              </Typography>
            )}
          </Box>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start', mb: 2 }}>
            <HistoryIcon fontSize="small" color="action" sx={{ mt: '2px' }} />
            <Typography variant="caption" color="text.secondary">
              {data.persisted_observations > 0
                ? `${data.persisted_observations} observation${data.persisted_observations === 1 ? '' : 's'} saved to history — they now feed Trends, Market Pulse and Price changes.`
                : 'Nothing was saved to history: this search found no product or price evidence worth recording.'}
            </Typography>
          </Box>
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

          {data.mixed_currency_statistics && data.verified_local_prices > 0 && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Verified prices were found in more than one currency, so no lowest, average
              or highest price was computed — they cannot be compared directly. Each
              price is listed below with its own currency.
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
                    {hasReferencePrice ? (
                      <>
                        <Typography variant="h4" sx={{ mb: 1 }}>
                          {formatMoney(data.reference_price, referenceCurrency)}
                        </Typography>
                        {referenceDelta !== null && showStatistics ? (
                          <Typography variant="body1" sx={{
                            color: referenceDelta < 0 ? 'warning.main' : 'success.main',
                            fontWeight: 'bold'
                          }}>
                            Lowest other store vs. reference: {referenceDelta > 0 ? '+' : ''}
                            {formatMoney(referenceDelta, data.currency ?? referenceCurrency)}
                          </Typography>
                        ) : (
                          <Typography variant="body2" color="text.secondary">
                            No comparison: too few comparable prices in one currency.
                          </Typography>
                        )}
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
                  {showStatistics ? (
                    <>
                      <Typography variant="subtitle2" sx={{ opacity: 0.8, mb: 1 }}>
                        Lowest Verified Nearby Competitor:
                      </Typography>
                      <Typography variant="h4" sx={{ mb: 1 }}>
                        {formatMoney(data.lowest_price, data.currency)}
                      </Typography>
                      <Typography variant="body1">
                        Average: {formatMoney(data.average_price, data.currency)} | Highest: {formatMoney(data.highest_price, data.currency)}
                      </Typography>
                      <Typography variant="caption" sx={{ opacity: 0.8 }}>
                        From {data.verified_local_prices} verified prices.
                      </Typography>
                    </>
                  ) : data.mixed_currency_statistics ? (
                    <>
                      <Typography variant="subtitle2" sx={{ opacity: 0.8, mb: 1 }}>
                        {data.verified_local_prices} verified prices in several currencies
                      </Typography>
                      <Typography variant="body2" sx={{ opacity: 0.9 }}>
                        No statistics were computed. See each price in the table below.
                      </Typography>
                    </>
                  ) : (
                    <>
                      <Typography variant="subtitle2" sx={{ opacity: 0.8, mb: 1 }}>
                        {distinctPrices <= 1 && data.verified_local_prices > 1
                          ? `One distinct verified price (seen ${data.verified_local_prices} times):`
                          : 'One verified price:'}
                      </Typography>
                      <Typography variant="h4" sx={{ mb: 1 }}>
                        {singleObservation
                          ? formatMoney(singleObservation.price, singleObservation.currency)
                          : formatMoney(data.lowest_price, data.currency)}
                      </Typography>
                      {singleObservation && (
                        <Typography variant="body2" sx={{ opacity: 0.9, mb: 0.5 }}>
                          at {singleObservation.merchant}
                        </Typography>
                      )}
                      <Typography variant="body2" sx={{ opacity: 0.9 }}>
                        One price is not a range, so no lowest, average or highest is stated.
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
              <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
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
                        <TableCell>{obs.size || '—'}</TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                            {formatMoney(obs.price, obs.currency)}
                          </Typography>
                          {!obs.currency && obs.price !== null && (
                            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                              currency not stated
                            </Typography>
                          )}
                        </TableCell>
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
              <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
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
                              {formatMoney(merchant.price, merchantCurrency(merchant, data.currency))}
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
                                <InfoOutlinedIcon
                                  fontSize="small" color="action" tabIndex={0}
                                  aria-label="Why this price could not be verified"
                                  sx={{ ml: 0.5, fontSize: '1rem', cursor: 'help' }}
                                />
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

      <PriceChanges product={data?.searched_product ?? null} refreshKey={alertsRefresh} />
    </Box>
  );
};

export default PriceIntelligence;

