import {
  Avatar, Box, Chip, IconButton, Paper, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Tooltip, Typography,
} from '@mui/material';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import StarRoundedIcon from '@mui/icons-material/StarRounded';

import type { Competitor } from '../../types/competitor';
import { formatDate } from '../../utils/format';
import { ReviewActions, ReviewChip, type ReviewUpdate } from './CompetitorReview';
import {
  STATUS_COLOR, STATUS_HELP, STATUS_LABEL, avatarColor, displayName, initials, locationText,
} from './competitorDisplay';

interface Props {
  rows: Competitor[];
  busyId: number | null;
  onReview: (competitor: Competitor, update: ReviewUpdate) => void;
  onOpen: (competitor: Competitor) => void;
}

/**
 * A compact list for scanning many businesses. Six columns instead of ten:
 * everything else is one click away in the details drawer. The whole row
 * opens it, except the review buttons.
 */
const CompetitorTable = ({ rows, busyId, onReview, onOpen }: Props) => (
  <TableContainer component={Paper} variant="outlined">
    <Table size="small" sx={{ minWidth: 720 }}>
      <TableHead>
        <TableRow sx={{ '& th': { fontWeight: 600, color: 'text.secondary', whiteSpace: 'nowrap' } }}>
          <TableCell>Business</TableCell>
          <TableCell>Market · location</TableCell>
          <TableCell>Rating</TableCell>
          <TableCell>Identity</TableCell>
          <TableCell>Your review</TableCell>
          <TableCell>Last seen</TableCell>
          <TableCell padding="checkbox" />
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((c, i) => {
          const name = displayName(c);
          const place = locationText(c);
          return (
            <TableRow
              key={c.id ?? `row-${i}`} hover onClick={() => onOpen(c)}
              sx={{ cursor: 'pointer', opacity: c.review_status === 'rejected' ? 0.6 : 1 }}
            >
              <TableCell sx={{ maxWidth: 280 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                  <Avatar sx={{ bgcolor: avatarColor(c.name), width: 30, height: 30, fontSize: 12, fontWeight: 600 }}>
                    {initials(name)}
                  </Avatar>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography variant="body2" noWrap title={name} sx={{ fontWeight: 600 }}>{name}</Typography>
                    <Typography variant="caption" color="text.secondary" noWrap sx={{ display: 'block' }}>
                      {c.domain ?? 'No website reported'}
                    </Typography>
                  </Box>
                </Box>
              </TableCell>
              <TableCell sx={{ maxWidth: 240 }}>
                <Typography variant="body2" noWrap title={c.markets.join(', ')}>
                  {c.markets.join(', ') || '—'}
                </Typography>
                <Typography variant="caption" noWrap sx={{ display: 'block' }}
                            color={place ? 'text.secondary' : 'warning.main'} title={place ?? undefined}>
                  {place ?? 'Location not verified'}
                </Typography>
              </TableCell>
              <TableCell sx={{ whiteSpace: 'nowrap' }}>
                {c.rating !== null ? (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
                    <StarRoundedIcon sx={{ fontSize: 18, color: 'warning.main' }} />
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>{c.rating.toFixed(1)}</Typography>
                    {c.reviews !== null && (
                      <Typography variant="caption" color="text.secondary">&nbsp;({c.reviews.toLocaleString()})</Typography>
                    )}
                  </Box>
                ) : <Typography variant="caption" color="text.disabled">—</Typography>}
              </TableCell>
              <TableCell>
                <Tooltip title={STATUS_HELP[c.status] ?? ''}>
                  <Chip size="small" variant="outlined" color={STATUS_COLOR[c.status] ?? 'default'}
                        label={STATUS_LABEL[c.status] ?? c.status} />
                </Tooltip>
              </TableCell>
              <TableCell onClick={(e) => e.stopPropagation()} sx={{ whiteSpace: 'nowrap' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <ReviewChip competitor={c} />
                  <ReviewActions competitor={c} busy={busyId === c.id} onReview={onReview} />
                </Box>
              </TableCell>
              <TableCell sx={{ whiteSpace: 'nowrap' }}>
                <Typography variant="caption" color="text.secondary">{formatDate(c.last_seen_at)}</Typography>
              </TableCell>
              <TableCell padding="checkbox">
                <IconButton size="small" aria-label={`Open details for ${name}`}
                            onClick={(e) => { e.stopPropagation(); onOpen(c); }}>
                  <ChevronRightIcon fontSize="small" />
                </IconButton>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  </TableContainer>
);

export default CompetitorTable;
