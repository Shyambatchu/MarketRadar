import {
  Avatar, Box, Button, Card, CardActions, CardContent, Chip, Divider, Link, Rating,
  Tooltip, Typography,
} from '@mui/material';
import PlaceOutlinedIcon from '@mui/icons-material/PlaceOutlined';
import LanguageOutlinedIcon from '@mui/icons-material/LanguageOutlined';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

import type { Competitor } from '../../types/competitor';
import { formatDate } from '../../utils/format';
import { ReviewActions, ReviewChip, type ReviewUpdate } from './CompetitorReview';
import {
  STATUS_COLOR, STATUS_HELP, STATUS_LABEL, avatarColor, displayName, initials, locationText,
} from './competitorDisplay';

interface Props {
  competitor: Competitor;
  busy: boolean;
  onReview: (competitor: Competitor, update: ReviewUpdate) => void;
  onOpen: (competitor: Competitor) => void;
}

/** One business at a glance: who it is, where, how well evidenced, your decision. */
const CompetitorCard = ({ competitor: c, busy, onReview, onOpen }: Props) => {
  const name = displayName(c);
  const place = locationText(c);
  const rejected = c.review_status === 'rejected';

  return (
    <Card
      variant="outlined"
      sx={{
        height: '100%', display: 'flex', flexDirection: 'column',
        opacity: rejected ? 0.6 : 1, transition: 'box-shadow 150ms, border-color 150ms',
        '&:hover': { borderColor: 'primary.light', boxShadow: 2 },
      }}
    >
      <CardContent sx={{ flexGrow: 1, pb: 1 }}>
        <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start', mb: 1.5 }}>
          <Avatar sx={{ bgcolor: avatarColor(c.name), width: 40, height: 40, fontSize: 15, fontWeight: 600 }}>
            {initials(name)}
          </Avatar>
          <Box sx={{ minWidth: 0, flexGrow: 1 }}>
            <Typography
              variant="subtitle1" component="h3" title={name}
              sx={{ fontWeight: 600, lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            >
              {name}
            </Typography>
            {c.display_name && c.display_name !== c.name && (
              <Typography variant="caption" color="text.secondary" noWrap sx={{ display: 'block' }}>
                Discovered as {c.name}
              </Typography>
            )}
            {c.domain ? (
              <Link href={c.website ?? `https://${c.domain}`} target="_blank" rel="noopener noreferrer"
                    underline="hover" variant="body2"
                    sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5, maxWidth: '100%' }}>
                <LanguageOutlinedIcon sx={{ fontSize: 14 }} />
                <Box component="span" sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.domain}
                </Box>
              </Link>
            ) : (
              <Typography variant="body2" color="text.disabled">No website reported</Typography>
            )}
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1, minHeight: 22 }}>
          {c.rating !== null ? (
            <>
              <Rating value={c.rating} precision={0.1} readOnly size="small" />
              <Typography variant="body2" sx={{ fontWeight: 600 }}>{c.rating.toFixed(1)}</Typography>
              {c.reviews !== null && (
                <Typography variant="caption" color="text.secondary">({c.reviews.toLocaleString()} reviews)</Typography>
              )}
            </>
          ) : (
            <Typography variant="caption" color="text.secondary">No rating reported</Typography>
          )}
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.75, mb: 1.5 }}>
          <PlaceOutlinedIcon sx={{ fontSize: 18, mt: '1px', color: place ? 'text.secondary' : 'warning.main' }} />
          {place ? (
            <Typography variant="body2" color="text.secondary" sx={{
              display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
            }}>
              {place}
            </Typography>
          ) : (
            <Tooltip title="No provider returned an address or coordinates, so the location could not be confirmed.">
              <Typography variant="body2" color="warning.main">Location not verified</Typography>
            </Tooltip>
          )}
        </Box>

        <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
          <Tooltip title={STATUS_HELP[c.status] ?? ''}>
            <Chip size="small" variant="outlined" color={STATUS_COLOR[c.status] ?? 'default'}
                  label={STATUS_LABEL[c.status] ?? c.status} />
          </Tooltip>
          {c.markets.slice(0, 2).map((m) => (
            <Chip key={m} size="small" label={m} sx={{ bgcolor: 'action.hover' }} />
          ))}
          {c.markets.length > 2 && (
            <Tooltip title={c.markets.slice(2).join(', ')}>
              <Chip size="small" label={`+${c.markets.length - 2}`} sx={{ bgcolor: 'action.hover' }} />
            </Tooltip>
          )}
        </Box>
      </CardContent>

      <Divider />
      <Box sx={{ px: 2, py: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
        <ReviewChip competitor={c} />
        <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto', textAlign: 'right' }}>
          Seen {formatDate(c.last_seen_at)} · {c.evidence_count} evidence
        </Typography>
      </Box>
      <CardActions sx={{ pt: 0, px: 1.5, pb: 1.5, justifyContent: 'space-between' }}>
        <ReviewActions competitor={c} busy={busy} onReview={onReview} labelled />
        <Button size="small" endIcon={<ChevronRightIcon />} onClick={() => onOpen(c)}>
          Details
        </Button>
      </CardActions>
    </Card>
  );
};

export default CompetitorCard;
