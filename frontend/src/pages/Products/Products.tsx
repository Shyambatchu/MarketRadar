import { useState, useEffect, useRef } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogContent,
  DialogTitle, Divider, Grid, IconButton, Link, Paper, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, TextField, Tooltip,
  Typography,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import CloseIcon from '@mui/icons-material/Close';
import Inventory2OutlinedIcon from '@mui/icons-material/Inventory2Outlined';
import { isAxiosError } from 'axios';

import PageHeader from '../../components/PageHeader/PageHeader';
import EmptyState from '../../components/EmptyState/EmptyState';
import {
  getProductObservation, listProductObservations, searchProducts,
} from '../../services/productApi';
import type {
  ProductEvidence, ProductObservationRecord, ProductSearchResponse,
} from '../../types/product';

/**
 * Colours describe evidence strength, never product quality.
 * "unknown" means we could not establish the product from the evidence — it
 * does not mean the merchant does not sell it.
 */
const PRODUCT_STATUS_COLOR: Record<string, 'success' | 'warning' | 'default'> = {
  found: 'success',
  not_found: 'warning',
  unknown: 'default',
};

const PRODUCT_STATUS_HELP: Record<string, string> = {
  found: 'The merchant\'s own site identifies this product.',
  not_found: 'A result specifically contradicted the request — a different size, variant or model.',
  unknown: 'Not enough evidence either way. This is not a claim that the merchant does not stock it.',
};

const PRICE_STATUS_HELP: Record<string, string> = {
  verified: 'A single, product-specific price on a product page.',
  unavailable: 'Product evidence exists, but no price could be attributed to this exact product.',
  unknown: 'No product was established, so no price could be considered.',
};

const SCOPE_HELP: Record<string, string> = {
  catalog: 'The merchant\'s catalogue lists this product. It is not proof that a physical store holds stock.',
  store_inventory: 'Evidence covers stock at a specific physical store.',
  marketplace_listing: 'A marketplace listing attributed to this merchant.',
};

const formatDate = (value: string | null): string =>
  value ? new Date(value).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  }) : '—';

const formatPrice = (price: number | null, currency: string | null): string =>
  price === null ? '—'
    : currency === 'USD' || !currency ? `$${price.toFixed(2)}`
      : `${price.toFixed(2)} ${currency}`;

/** A saved record and a live evidence row share the fields the table shows. */
type Row = {
  key: string;
  id: number | null;
  merchant: string;
  merchantDomain: string | null;
  productName: string | null;
  observedSize: string | null;
  sizeConfirmed: boolean;
  productStatus: string;
  priceStatus: string;
  verificationReason: string | null;
  price: number | null;
  currency: string | null;
  evidenceScope: string;
  inventoryConfirmed: boolean;
  sourceUrl: string | null;
  pageType: string | null;
  observedAt: string;
  market?: string | null;
};

const fromEvidence = (e: ProductEvidence, i: number): Row => ({
  key: `e${i}`, id: null, merchant: e.merchant, merchantDomain: e.merchant_domain,
  productName: e.product_name, observedSize: e.observed_size,
  sizeConfirmed: e.size_confirmed, productStatus: e.product_status,
  priceStatus: e.price_status, verificationReason: e.verification_reason,
  price: e.price, currency: e.currency, evidenceScope: e.evidence_scope,
  inventoryConfirmed: e.inventory_confirmed, sourceUrl: e.source_url,
  pageType: e.page_type, observedAt: e.observed_at,
});

const fromRecord = (r: ProductObservationRecord): Row => ({
  key: `r${r.id}`, id: r.id, merchant: r.merchant_name ?? '—',
  merchantDomain: r.merchant_domain, productName: r.product_name,
  observedSize: r.observed_size, sizeConfirmed: r.size_confirmed,
  productStatus: r.product_status, priceStatus: r.price_status,
  verificationReason: r.verification_reason, price: r.price, currency: r.currency,
  evidenceScope: r.evidence_scope, inventoryConfirmed: r.inventory_confirmed,
  sourceUrl: r.source_url, pageType: r.page_type, observedAt: r.observed_at,
  market: r.market,
});

const Products = () => {
  const [query, setQuery] = useState('');
  const [market, setMarket] = useState('');
  const [location, setLocation] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ProductSearchResponse | null>(null);
  const [saved, setSaved] = useState<ProductObservationRecord[]>([]);
  const [savedTotal, setSavedTotal] = useState(0);
  // A failed load is reported, never shown as an empty history.
  const [savedError, setSavedError] = useState<string | null>(null);
  const [detail, setDetail] = useState<ProductObservationRecord | null>(null);

  const isSearching = useRef(false);

  // Saved observations load on mount so the page is useful on arrival.
  // Database read only — no SerpApi credit.
  useEffect(() => {
    const controller = new AbortController();
    listProductObservations({}, controller.signal)
      .then((data) => { setSaved(data.observations); setSavedTotal(data.total); })
      .catch((err) => {
        if (!isAxiosError(err) || err.code !== 'ERR_CANCELED') {
          setSavedError(isAxiosError(err) && !err.response
            ? 'Saved product observations could not be loaded. Is the backend running?'
            : 'Saved product observations could not be loaded.');
        }
      });
    return () => controller.abort();
  }, []);

  const handleSearch = async () => {
    // A location is required: product evidence comes from the merchants in a
    // place, so without one there are no catalogues to search.
    if (!query.trim() || !location.trim() || isSearching.current) return;
    isSearching.current = true;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await searchProducts({
        query: query.trim(), market: market.trim(), location: location.trim(),
      });
      setResult(data);
      try {
        const list = await listProductObservations({});
        setSaved(list.observations);
      } catch {
        // Refreshing the saved list is cosmetic; the result stands.
      }
    } catch (err) {
      if (isAxiosError(err)) {
        const detailMessage = err.response?.data?.detail;
        // Each means something different and must not collapse into
        // "product not found".
        if (err.response?.status === 400) {
          setError(detailMessage || 'That search is missing something it needs. Provide a product and a location.');
        } else if (err.response?.status === 422) {
          setError(detailMessage || 'That location could not be matched to a supported search location.');
        } else if (err.response?.status === 502) {
          setError(detailMessage || 'The search provider did not respond, so no product evidence could be gathered. This is not the same as finding none.');
        } else if (err.response?.status === 503) {
          setError(detailMessage || 'Product discovery is not configured yet.');
        } else {
          setError(detailMessage || 'Unable to search for products. Try again in a moment.');
        }
      } else {
        setError('An unexpected error occurred.');
      }
    } finally {
      setLoading(false);
      isSearching.current = false;
    }
  };

  const openDetail = async (row: Row) => {
    if (row.id === null) return;
    try {
      setDetail(await getProductObservation(row.id));
    } catch {
      // Nothing more to show than the table already has.
    }
  };

  const showingSaved = !result;
  const rows: Row[] = result
    ? result.evidence.map(fromEvidence)
    : saved.map(fromRecord);
  const problemStages = result
    ? result.stages.filter((s) => s.status === 'error' || s.status === 'degraded')
    : [];

  return (
    <Box>
      <PageHeader
        title="Products"
        subtitle="Discover products and product evidence across merchants and markets."
      />

      <Paper sx={{ p: 3, mb: 4 }}>
        <Grid container spacing={2} sx={{ alignItems: 'center' }}>
          <Grid size={{ xs: 12, sm: 4 }}>
            <TextField
              fullWidth size="small" label="Product / Product Query"
              placeholder="e.g. Ridgeline Dark Roast 340g"
              value={query} onChange={(e) => setQuery(e.target.value)}
              disabled={loading}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 3 }}>
            <TextField
              fullWidth size="small" label="Market / Industry"
              placeholder="e.g. Coffee"
              value={market} onChange={(e) => setMarket(e.target.value)}
              disabled={loading}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 3 }}>
            <TextField
              fullWidth size="small" label="Location" required
              placeholder="e.g. Austin, Texas"
              value={location} onChange={(e) => setLocation(e.target.value)}
              disabled={loading}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 2 }}>
            <Button
              fullWidth variant="contained" sx={{ height: 40 }}
              startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SearchIcon />}
              onClick={handleSearch}
              disabled={loading || !query.trim() || !location.trim()}
            >
              Search
            </Button>
          </Grid>
        </Grid>

        {result && (
          <Box sx={{ mt: 2, display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            {result.location_resolved &&
              result.location_resolved !== result.location_requested && (
                <Typography variant="caption" color="text.secondary">
                  Location resolved to {result.location_resolved}
                </Typography>
              )}
            {result.cache_hit && (
              <Chip size="small" label="Cached result" color="success" variant="outlined" />
            )}
          </Box>
        )}
      </Paper>

      {problemStages.map((s) => (
        <Alert key={s.stage} severity={s.status === 'error' ? 'error' : 'warning'} sx={{ mb: 2 }}>
          {s.stage.replace(/_/g, ' ')}: {s.status}{s.detail ? ` — ${s.detail}` : ''}
        </Alert>
      ))}

      {error && <Alert severity="error" sx={{ mb: 4 }}>{error}</Alert>}

      {result && (
        <Paper variant="outlined" elevation={0} sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1.5 }}>Evidence funnel</Typography>
          <Grid container spacing={2}>
            {[
              ['Merchants considered', result.merchants_considered],
              ['Merchants searched', result.merchants_searched],
              ['No domain', result.merchants_without_domain],
              ['Rows examined', result.website_rows_examined],
              ['Off-domain rejected', result.off_domain_rejected],
              ['Listing pages', result.listing_pages_rejected],
              ['Found', result.products_found],
              ['Not found', result.products_not_found],
              ['Unknown', result.products_unknown],
              ['Prices verified', result.prices_verified],
            ].map(([label, value]) => (
              <Grid size={{ xs: 6, sm: 4, md: 'grow' }} key={label as string}>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                  {label}
                </Typography>
                <Typography variant="h6">{value}</Typography>
              </Grid>
            ))}
          </Grid>
        </Paper>
      )}

      {showingSaved && savedError ? (
        <Alert severity="error">{savedError}</Alert>
      ) : rows.length === 0 ? (
        <EmptyState
          title={showingSaved
            ? 'No product observations yet'
            : 'No product evidence was gathered for this search'}
          description={showingSaved
            ? 'Enter a product and a location (and optionally a market) to search merchant catalogues for product evidence.'
            : result && result.merchants_considered === 0
              ? 'No merchants were identified for this market and location, so there were no catalogues to search.'
              : 'Merchants were found, but none of their catalogues produced usable product evidence.'}
          icon={<Inventory2OutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />}
        />
      ) : (
        <>
          <Typography variant="h6" sx={{ mb: 2 }}>
            {showingSaved
              ? `Saved product observations (${savedTotal > saved.length
                ? `showing ${saved.length} of ${savedTotal}` : saved.length})`
              : `Product evidence (${rows.length})`}
          </Typography>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Product</TableCell>
                  <TableCell>Merchant</TableCell>
                  <TableCell>Domain</TableCell>
                  <TableCell>Variant / Size</TableCell>
                  <TableCell>Evidence</TableCell>
                  <TableCell align="right">Price</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Observed</TableCell>
                  {showingSaved && <TableCell />}
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.key} hover>
                    <TableCell>
                      <Typography variant="subtitle2">
                        {r.productName || <Box component="span" sx={{ color: 'text.disabled' }}>Not identified</Box>}
                      </Typography>
                      {r.market && (
                        <Typography variant="caption" color="text.secondary">{r.market}</Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{r.merchant}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {r.merchantDomain || 'Not reported'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {r.observedSize ? (
                        <Tooltip title={r.sizeConfirmed
                          ? 'The requested size was observed in the evidence.'
                          : 'A size was observed, but it is not the one requested — so no price is verified.'}>
                          <Chip size="small" variant="outlined" label={r.observedSize}
                                color={r.sizeConfirmed ? 'default' : 'warning'} />
                        </Tooltip>
                      ) : (
                        <Typography variant="caption" color="text.disabled">—</Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <Tooltip title={SCOPE_HELP[r.evidenceScope] ?? ''}>
                        <Chip size="small" variant="outlined"
                              label={r.evidenceScope === 'catalog' ? 'Catalogue'
                                : r.evidenceScope === 'store_inventory' ? 'Store inventory'
                                  : r.evidenceScope === 'marketplace_listing' ? 'Marketplace'
                                    : r.evidenceScope || 'Unknown'} />
                      </Tooltip>
                      {r.pageType && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                          {r.pageType} page
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell align="right">
                      {r.priceStatus === 'verified' ? (
                        <Tooltip title={PRICE_STATUS_HELP.verified}>
                          <Typography variant="body2" color="success.main">
                            {formatPrice(r.price, r.currency)}
                          </Typography>
                        </Tooltip>
                      ) : (
                        <Tooltip title={`${PRICE_STATUS_HELP[r.priceStatus] ?? ''}${
                          r.verificationReason ? ` (${r.verificationReason.replace(/_/g, ' ')})` : ''}`}>
                          <Typography variant="caption" color="text.secondary">
                            {r.priceStatus === 'unavailable' ? 'Unavailable' : '—'}
                          </Typography>
                        </Tooltip>
                      )}
                    </TableCell>
                    <TableCell>
                      <Tooltip title={`${PRODUCT_STATUS_HELP[r.productStatus] ?? ''}${
                        r.verificationReason ? ` (${r.verificationReason.replace(/_/g, ' ')})` : ''}`}>
                        <Chip size="small" variant="outlined"
                              label={r.productStatus.replace(/_/g, ' ')}
                              color={PRODUCT_STATUS_COLOR[r.productStatus] ?? 'default'} />
                      </Tooltip>
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {formatDate(r.observedAt)}
                      </Typography>
                    </TableCell>
                    {showingSaved && (
                      <TableCell>
                        <Button size="small" onClick={() => openDetail(r)}>Details</Button>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      {result && result.rejected_results.length > 0 && (
        <Box sx={{ mt: 4 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>
            Results that did not identify the product ({result.rejected_results.length})
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Kept visible so nothing is discarded silently. A near miss is not a
            match: a different size, variant or model is a different product.
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Merchant</TableCell>
                  <TableCell>Result</TableCell>
                  <TableCell>Page type</TableCell>
                  <TableCell>Reason</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {result.rejected_results.map((r, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      <Typography variant="caption">{r.merchant}</Typography>
                    </TableCell>
                    <TableCell>
                      {r.url ? (
                        <Link href={r.url} target="_blank" rel="noopener" underline="hover">
                          {r.title || r.url}
                        </Link>
                      ) : (r.title || '—')}
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption">{r.page_type || '—'}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {r.reason.replace(/_/g, ' ')}
                        {r.detail ? `: ${r.detail}` : ''}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      <Dialog open={detail !== null} onClose={() => setDetail(null)} maxWidth="md" fullWidth>
        {detail && (
          <>
            <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box>
                <Typography variant="h6">
                  {detail.product_name || 'Product not identified'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  searched as “{detail.product_query}”
                </Typography>
              </Box>
              <IconButton onClick={() => setDetail(null)} size="small">
                <CloseIcon />
              </IconButton>
            </DialogTitle>
            <DialogContent dividers>
              <Grid container spacing={2} sx={{ mb: 2 }}>
                {[
                  ['Merchant', detail.merchant_name || 'Not reported'],
                  ['Merchant domain', detail.merchant_domain || 'Not reported'],
                  ['Merchant identity', detail.merchant_match_status],
                  ['Market / Industry', detail.market || 'Not recorded'],
                  ['Location', detail.location_resolved || 'Not recorded'],
                  ['Product status', detail.product_status.replace(/_/g, ' ')],
                  ['Price status', detail.price_status],
                  ['Price', formatPrice(detail.price, detail.currency)],
                  ['Observed size', detail.observed_size || 'Not reported'],
                  ['Requested size confirmed', detail.size_confirmed ? 'Yes' : 'No'],
                  ['Evidence scope', detail.evidence_scope],
                  ['Inventory confirmed', detail.inventory_confirmed ? 'Yes' : 'No'],
                  ['Page type', detail.page_type || 'Not reported'],
                  ['Discovery method', (detail.discovery_method || '—').replace(/_/g, ' ')],
                  ['Identity match', detail.match_method.replace(/_/g, ' ')],
                  ['Observed', formatDate(detail.observed_at)],
                ].map(([label, value]) => (
                  <Grid size={{ xs: 6, sm: 4 }} key={label}>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      {label}
                    </Typography>
                    <Typography variant="body2">{value}</Typography>
                  </Grid>
                ))}
              </Grid>

              {detail.verification_reason && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  {PRODUCT_STATUS_HELP[detail.product_status]} Reason recorded:{' '}
                  {detail.verification_reason.replace(/_/g, ' ')}.
                </Alert>
              )}

              {detail.evidence_scope === 'catalog' && !detail.inventory_confirmed && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  This evidence comes from the merchant's catalogue. It shows the
                  merchant offers the product — it is not proof that any
                  physical store currently holds it in stock.
                </Alert>
              )}

              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle2" sx={{ mb: 1 }}>Source</Typography>
              {detail.source_url ? (
                <Link href={detail.source_url} target="_blank" rel="noopener" underline="hover">
                  {detail.source_url}
                </Link>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No source URL was recorded for this observation.
                </Typography>
              )}
              {detail.snippet && (
                <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                    Snippet as indexed — corroborates, but never establishes identity on its own
                  </Typography>
                  <Typography variant="body2">{detail.snippet}</Typography>
                </Paper>
              )}
            </DialogContent>
          </>
        )}
      </Dialog>
    </Box>
  );
};

export default Products;
