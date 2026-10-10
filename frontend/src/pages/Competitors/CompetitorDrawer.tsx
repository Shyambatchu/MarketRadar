import {
  Alert, Avatar, Box, Button, Chip, CircularProgress, Divider, Drawer, IconButton, Link,
  Paper, Rating, Stack, Tooltip, Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';

import type { Competitor } from '../../types/competitor';
import { formatDate, humanize } from '../../utils/format';
import { ReviewPanel, type ReviewUpdate } from './CompetitorReview';
import {
  SOURCE_LABEL, STATUS_COLOR, STATUS_HELP, STATUS_LABEL, avatarColor, displayName, initials,
  locationText, sourceLabel,
} from './competitorDisplay';

interface Props {
  competitor: Competitor | null;
  loading: boolean;
  error: string | null;
  reviewBusy: boolean;
  reviewError: string | null;
  onReview: (competitor: Competitor, update: ReviewUpdate) => void;
  onClose: () => void;
}

const Fact = ({ label, value }: { label: string; value: React.ReactNode }) => (
  <Box sx={{ minWidth: 0 }}>
    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>{label}</Typography>
    <Typography variant="body2" component="div" sx={{ wordBreak: 'break-word' }}>{value}</Typography>
  </Box>
);

/**
 * Everything known about one business, in a side panel so the list stays in
 * view behind it: your review first, then the key facts, then each piece of
 * discovery evidence with its source.
 */
const CompetitorDrawer = ({
  competitor: c, loading, error, reviewBusy, reviewError, onReview, onClose,
}: Props) => (
  <Drawer
    anchor="right" open={c !== null} onClose={onClose}
    slotProps={{ paper: { sx: { width: { xs: '100%', sm: 520 } } } }}
  >
    {c && (
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <Box sx={{ p: 2.5, display: 'flex', gap: 1.5, alignItems: 'flex-start', borderBottom: 1, borderColor: 'divider' }}>
          <Avatar sx={{ bgcolor: avatarColor(c.name), width: 48, height: 48, fontWeight: 600 }}>
            {initials(displayName(c))}
          </Avatar>
          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            <Typography variant="h6" sx={{ lineHeight: 1.3 }}>{displayName(c)}</Typography>
            {c.display_name && c.display_name !== c.name && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                Discovered as {c.name}
              </Typography>
            )}
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mt: 0.5 }}>
              <Tooltip title={STATUS_HELP[c.status] ?? ''}>
                <Chip size="small" variant="outlined" color={STATUS_COLOR[c.status] ?? 'default'}
                      label={STATUS_LABEL[c.status] ?? c.status} />
              </Tooltip>
              {c.rating !== null && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Rating value={c.rating} precision={0.1} readOnly size="small" />
                  <Typography variant="caption" color="text.secondary">
                    {c.rating.toFixed(1)}{c.reviews !== null ? ` · ${c.reviews.toLocaleString()} reviews` : ''}
                  </Typography>
                </Box>
              )}
            </Box>
          </Box>
          <IconButton onClick={onClose} aria-label="Close details"><CloseIcon /></IconButton>
        </Box>

        <Box sx={{ p: 2.5, overflowY: 'auto', flexGrow: 1 }}>
          {(c.website || c.domain) && (
            <Button size="small" variant="outlined" endIcon={<OpenInNewIcon />} sx={{ mb: 2 }}
                    href={c.website ?? `https://${c.domain}`} target="_blank" rel="noopener noreferrer">
              Visit {c.domain ?? 'website'}
            </Button>
          )}

          <Paper variant="outlined" sx={{ p: 2, mb: 2.5 }}>
            <ReviewPanel
              key={`${c.id}|${c.display_name ?? ''}|${c.review_note ?? ''}`}
              competitor={c} busy={reviewBusy} error={reviewError} onReview={onReview}
            />
          </Paper>

          {error && <Alert severity="warning" sx={{ mb: 2 }}>{error} Showing the summary from the list.</Alert>}

          <Typography variant="subtitle2" sx={{ mb: 1.5 }}>At a glance</Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2, mb: 2.5 }}>
            <Fact label="Address" value={locationText(c) ?? (
              <Typography variant="body2" color="warning.main" component="span">Location not verified</Typography>)} />
            <Fact label="Markets" value={c.markets.join(', ') || 'Not recorded'} />
            <Fact label="Searched locations" value={c.locations.join(', ') || 'Not recorded'} />
            <Fact label="Found via" value={sourceLabel(c)} />
            <Fact label="Best search position" value={c.best_position ?? '—'} />
            <Fact label="Identity match" value={`${humanize(c.match_method)} · ${c.match_confidence}`} />
            <Fact label="First seen" value={formatDate(c.first_seen_at)} />
            <Fact label="Last seen" value={formatDate(c.last_seen_at)} />
          </Box>

          {c.status_reason && (
            <Alert severity="info" sx={{ mb: 2 }}>
              {STATUS_HELP[c.status]} Reason: {humanize(c.status_reason)}.
            </Alert>
          )}
          {!c.domain && c.website && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Its web presence is a page on another platform (
              <Link href={c.website} target="_blank" rel="noopener noreferrer">{c.website}</Link>
              ), kept as evidence but not treated as its own domain.
            </Alert>
          )}

          <Divider sx={{ mb: 2 }} />
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
            <Typography variant="subtitle2">
              Discovery evidence ({c.evidence.length || c.evidence_count})
            </Typography>
            {loading && <CircularProgress size={14} />}
          </Box>
          {c.evidence.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              {loading ? 'Loading evidence…'
                : error && c.evidence_count > 0
                  ? `${c.evidence_count} evidence rows are recorded but could not be loaded.`
                  : 'No evidence rows are recorded for this business.'}
            </Typography>
          ) : (
            <Stack spacing={1.25}>
              {c.evidence.map((e, i) => (
                <Paper key={i} variant="outlined" sx={{ p: 1.5 }}>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 0.5 }}>
                    <Chip size="small" variant="outlined"
                          label={SOURCE_LABEL[e.discovery_method] ?? humanize(e.discovery_method)} />
                    {e.position !== null && (
                      <Typography variant="caption" color="text.secondary">Position {e.position}</Typography>
                    )}
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
                      {formatDate(e.observed_at)}
                    </Typography>
                  </Box>
                  {e.title && <Typography variant="body2" sx={{ fontWeight: 500 }}>{e.title}</Typography>}
                  {e.snippet && (
                    <Typography variant="caption" color="text.secondary" sx={{
                      display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
                    }}>
                      {e.snippet}
                    </Typography>
                  )}
                  {e.source_url && (
                    <Link href={e.source_url} target="_blank" rel="noopener noreferrer" variant="caption"
                          sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5, wordBreak: 'break-all' }}>
                      <OpenInNewIcon sx={{ fontSize: 13 }} />
                      {e.source_domain ?? e.source_url}
                    </Link>
                  )}
                </Paper>
              ))}
            </Stack>
          )}
        </Box>
      </Box>
    )}
  </Drawer>
);

export default CompetitorDrawer;
