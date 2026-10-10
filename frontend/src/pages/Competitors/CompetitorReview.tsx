import { useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, IconButton, Stack, TextField,
  Tooltip, Typography,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutlineOutlined';
import BlockIcon from '@mui/icons-material/Block';
import RestartAltIcon from '@mui/icons-material/RestartAlt';

import type { Competitor } from '../../types/competitor';
import { formatDateTime } from '../../utils/format';

export type ReviewDecision = 'confirmed' | 'rejected' | 'unreviewed';
export type ReviewUpdate = {
  review_status?: ReviewDecision;
  display_name?: string;
  review_note?: string;
};

export const REVIEW_HELP =
  'Your review is separate from the identity status (verified / discovered / uncertain), '
  + 'which only describes how strongly the evidence identifies the business. '
  + 'A search result is never proof of competition: you decide. '
  + 'A rejected business is skipped by Products searches.';

const REVIEW_SUMMARY = 'Is this business a real competitor? Rejected businesses are skipped in product searches.';

/** The user's decision about a business, never inferred from the evidence. */
export const ReviewChip = ({ competitor }: { competitor: Competitor }) => {
  if (competitor.review_status === 'confirmed') {
    return <Chip size="small" color="success" label="Confirmed" />;
  }
  if (competitor.review_status === 'rejected') {
    return (
      <Chip size="small" label="Rejected"
            sx={{ textDecoration: 'line-through', color: 'text.secondary' }} />
    );
  }
  return <Chip size="small" variant="outlined" label="Unreviewed" />;
};

interface ReviewActionsProps {
  competitor: Competitor;
  busy: boolean;
  onReview: (competitor: Competitor, update: ReviewUpdate) => void;
  /** Text buttons instead of icons, where there is room (cards). */
  labelled?: boolean;
}

/** Quick confirm / reject / clear buttons for a table row. */
export const ReviewActions = ({ competitor, busy, onReview, labelled = false }: ReviewActionsProps) => {
  if (competitor.id === null) {
    return (
      <Tooltip title="This business was not saved, so it cannot be reviewed.">
        <Typography variant="caption" color="text.disabled">Not saved</Typography>
      </Tooltip>
    );
  }
  if (busy) return <CircularProgress size={18} />;
  const status = competitor.review_status;
  if (labelled) {
    return (
      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
        {status !== 'confirmed' && (
          <Button size="small" color="success" startIcon={<CheckCircleOutlineIcon />}
                  onClick={() => onReview(competitor, { review_status: 'confirmed' })}>
            Confirm
          </Button>
        )}
        {status !== 'rejected' && (
          <Button size="small" color="inherit" startIcon={<BlockIcon />} sx={{ color: 'text.secondary' }}
                  onClick={() => onReview(competitor, { review_status: 'rejected' })}>
            Reject
          </Button>
        )}
        {status !== null && (
          <Tooltip title="Clear your decision">
            <Button size="small" color="inherit" sx={{ color: 'text.secondary', minWidth: 0 }}
                    aria-label="Mark unreviewed"
                    onClick={() => onReview(competitor, { review_status: 'unreviewed' })}>
              Undo
            </Button>
          </Tooltip>
        )}
      </Box>
    );
  }
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', whiteSpace: 'nowrap' }}>
      {status !== 'confirmed' && (
        <Tooltip title="Confirm as a competitor">
          <IconButton size="small" color="success" aria-label="Confirm as a competitor"
                      onClick={() => onReview(competitor, { review_status: 'confirmed' })}>
            <CheckCircleOutlineIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      )}
      {status !== 'rejected' && (
        <Tooltip title="Reject: not a competitor (Products searches will skip it)">
          <IconButton size="small" aria-label="Reject as a competitor"
                      onClick={() => onReview(competitor, { review_status: 'rejected' })}>
            <BlockIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      )}
      {status !== null && (
        <Tooltip title="Clear your decision (mark unreviewed)">
          <IconButton size="small" aria-label="Mark unreviewed"
                      onClick={() => onReview(competitor, { review_status: 'unreviewed' })}>
            <RestartAltIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      )}
    </Box>
  );
};

interface ReviewPanelProps {
  competitor: Competitor;
  busy: boolean;
  error: string | null;
  onReview: (competitor: Competitor, update: ReviewUpdate) => void;
}

/**
 * The review section of the Details dialog. The parent keys it on the saved
 * values so the form re-initialises when another business opens or a save lands.
 */
export const ReviewPanel = ({ competitor, busy, error, onReview }: ReviewPanelProps) => {
  const [displayName, setDisplayName] = useState(competitor.display_name ?? '');
  const [note, setNote] = useState(competitor.review_note ?? '');

  if (competitor.id === null) {
    return (
      <Alert severity="info">
        This business was not saved, so it cannot be reviewed.
      </Alert>
    );
  }

  const textChanged = displayName.trim() !== (competitor.display_name ?? '')
    || note.trim() !== (competitor.review_note ?? '');
  const status = competitor.review_status;

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 1 }}>
        <Typography variant="subtitle2">Your review</Typography>
        <ReviewChip competitor={competitor} />
        {competitor.reviewed_at && (
          <Typography variant="caption" color="text.secondary">
            Last changed {formatDateTime(competitor.reviewed_at)}
          </Typography>
        )}
      </Box>
      <Tooltip title={REVIEW_HELP} placement="bottom-start">
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
          {REVIEW_SUMMARY}
        </Typography>
      </Tooltip>

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ mb: 2 }}>
        <Button size="small" variant={status === 'confirmed' ? 'contained' : 'outlined'}
                color="success" startIcon={<CheckCircleOutlineIcon />}
                disabled={busy || status === 'confirmed'}
                onClick={() => onReview(competitor, { review_status: 'confirmed' })}>
          Confirm competitor
        </Button>
        <Button size="small" variant={status === 'rejected' ? 'contained' : 'outlined'}
                color="inherit" startIcon={<BlockIcon />}
                disabled={busy || status === 'rejected'}
                onClick={() => onReview(competitor, { review_status: 'rejected' })}>
          Reject
        </Button>
        <Button size="small" variant="text" startIcon={<RestartAltIcon />}
                disabled={busy || status === null}
                onClick={() => onReview(competitor, { review_status: 'unreviewed' })}>
          Mark unreviewed
        </Button>
      </Stack>

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mb: 1 }}>
        <TextField
          size="small" fullWidth label="Display name"
          placeholder={competitor.name}
          value={displayName} onChange={(e) => setDisplayName(e.target.value)}
          disabled={busy}
        />
        <TextField
          size="small" fullWidth label="Note" multiline maxRows={4}
          placeholder="Why you confirmed or rejected it"
          value={note} onChange={(e) => setNote(e.target.value)}
          disabled={busy}
        />
      </Stack>
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <Button size="small" variant="contained" disabled={busy || !textChanged}
                onClick={() => onReview(competitor, {
                  display_name: displayName.trim(), review_note: note.trim(),
                })}>
          Save details
        </Button>
        {busy && <CircularProgress size={18} />}
      </Box>
      {error && <Alert severity="error" sx={{ mt: 1.5 }}>{error}</Alert>}
    </Box>
  );
};
