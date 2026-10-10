import { useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, Collapse, Dialog, DialogActions,
  DialogContent, DialogTitle, Divider, LinearProgress, Link, Paper, Stack, TextField,
  Tooltip, Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import BookmarkBorderIcon from '@mui/icons-material/BookmarkBorder';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import DoneAllIcon from '@mui/icons-material/DoneAll';
import CloseIcon from '@mui/icons-material/Close';
import RestoreIcon from '@mui/icons-material/Restore';
import EditNoteIcon from '@mui/icons-material/EditNote';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import LightbulbOutlinedIcon from '@mui/icons-material/LightbulbOutlined';

import { updateOpportunity } from '../../services/intelligenceApi';
import type { Opportunity, OpportunityStatus } from '../../types/intelligence';
import { errorMessage, formatDate } from '../../utils/format';
import { CATEGORY, scoreBand } from './opportunityDisplay';

const INPUTS = ['impact', 'confidence', 'freshness', 'relevance'] as const;

const INPUT_LABEL: Record<(typeof INPUTS)[number], string> = {
  impact: 'Size of change',
  confidence: 'Evidence strength',
  freshness: 'How recent',
  relevance: 'Relevance to you',
};

const INPUT_HELP: Record<(typeof INPUTS)[number], string> = {
  impact: 'How large the observed change is (price move, price gap or interest rise), scaled 0–1.',
  confidence: 'How strong the evidence is: the source confidence and the number of supporting observations.',
  freshness: 'Halves with each half-life since the evidence was observed.',
  relevance: 'Higher for businesses you confirmed as competitors; market-wide signals sit in between.',
};

interface OpportunityCardProps {
  opportunity: Opportunity;
  onUpdated: (updated: Opportunity) => void;
}

const OpportunityCard = ({ opportunity: o, onUpdated }: OpportunityCardProps) => {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteDraft, setNoteDraft] = useState('');

  const apply = async (key: string, update: { status?: OpportunityStatus; note?: string }) => {
    setBusy(key);
    setError(null);
    try {
      onUpdated(await updateOpportunity(o.id, update));
      return true;
    } catch (err) {
      setError(errorMessage(err, 'The opportunity could not be updated.'));
      return false;
    } finally {
      setBusy(null);
    }
  };

  const saveNote = async () => {
    if (await apply('note', { note: noteDraft.trim() })) setNoteOpen(false);
  };

  const missing = new Set(o.breakdown?.missing ?? []);
  const band = scoreBand(o.score);
  const category = CATEGORY[o.category] ?? { label: o.category.replace(/_/g, ' '), icon: <LightbulbOutlinedIcon fontSize="small" /> };
  const place = [o.market, o.location].filter(Boolean).join(' · ') || 'Market not recorded';
  const spinner = (key: string, icon: React.ReactNode) =>
    busy === key ? <CircularProgress size={16} color="inherit" /> : icon;
  const dismissed = o.status === 'dismissed';

  return (
    <Paper variant="outlined" sx={{
      p: { xs: 2, md: 2.5 }, opacity: dismissed ? 0.65 : 1,
      borderLeft: 4, borderLeftColor: `${band.color === 'default' ? 'grey.400' : `${band.color}.main`}`,
    }}>
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
        {/* Score: a ranking for review order, never a probability. */}
        <Tooltip title="Ranking score out of 100, used to order leads for review. It is not a probability of success.">
          <Box sx={{ textAlign: 'center', minWidth: 64 }}>
            <Box sx={{
              width: 60, height: 60, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              border: 3, borderColor: band.color === 'default' ? 'grey.400' : `${band.color}.main`, mx: 'auto',
            }}>
              <Typography variant="h6" component="p" sx={{ fontWeight: 700, lineHeight: 1 }}>{Math.round(o.score)}</Typography>
            </Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5, lineHeight: 1.2 }}>
              {band.label.replace(' priority', '')}
            </Typography>
          </Box>
        </Tooltip>

        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap', mb: 0.75, alignItems: 'center' }}>
            <Chip size="small" icon={category.icon as React.ReactElement} label={category.label} color="primary" variant="outlined" />
            <Chip size="small" variant="outlined" label={`${o.confidence} confidence`} />
            {o.status === 'saved' && <Chip size="small" color="primary" label="Saved" />}
            {o.status === 'reviewed' && <Chip size="small" color="success" label="Reviewed" />}
            {dismissed && <Chip size="small" label="Dismissed" />}
          </Stack>
          <Typography variant="subtitle1" component="h3" sx={{ fontWeight: 600, lineHeight: 1.35 }}>{o.title}</Typography>
          <Typography variant="caption" color="text.secondary">
            {place} · evidence from {formatDate(o.evidence_observed_at)}
          </Typography>

          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 1.5, mt: 1.5 }}>
            {o.relevance_note && (
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>Why it matters</Typography>
                <Typography variant="body2">{o.relevance_note}</Typography>
              </Box>
            )}
            {o.suggested_action && (
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>Suggested next step</Typography>
                <Typography variant="body2">{o.suggested_action}</Typography>
              </Box>
            )}
          </Box>
          {o.note && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1, fontStyle: 'italic' }}>
              Your note: {o.note}
            </Typography>
          )}

          <Stack direction="row" spacing={0.5} useFlexGap sx={{ flexWrap: 'wrap', mt: 1.5, ml: -0.75 }}>
            {dismissed ? (
              <Button size="small" disabled={busy !== null} startIcon={spinner('new', <RestoreIcon />)}
                      onClick={() => apply('new', { status: 'new' })}>
                Restore
              </Button>
            ) : (
              <>
                <Button size="small" disabled={busy !== null}
                        startIcon={spinner('saved', o.status === 'saved' ? <BookmarkIcon /> : <BookmarkBorderIcon />)}
                        onClick={() => apply('saved', { status: o.status === 'saved' ? 'new' : 'saved' })}>
                  {o.status === 'saved' ? 'Saved' : 'Save'}
                </Button>
                <Button size="small" color="success" disabled={busy !== null || o.status === 'reviewed'}
                        startIcon={spinner('reviewed', <DoneAllIcon />)}
                        onClick={() => apply('reviewed', { status: 'reviewed' })}>
                  {o.status === 'reviewed' ? 'Reviewed' : 'Mark reviewed'}
                </Button>
                <Button size="small" color="inherit" sx={{ color: 'text.secondary' }} disabled={busy !== null}
                        startIcon={spinner('dismissed', <CloseIcon />)}
                        onClick={() => apply('dismissed', { status: 'dismissed' })}>
                  Dismiss
                </Button>
              </>
            )}
            <Button size="small" color="inherit" sx={{ color: 'text.secondary' }} disabled={busy !== null}
                    startIcon={<EditNoteIcon />}
                    onClick={() => { setNoteDraft(o.note ?? ''); setNoteOpen(true); }}>
              {o.note ? 'Edit note' : 'Add note'}
            </Button>
            <Button size="small" sx={{ ml: { sm: 'auto' } }} onClick={() => setExpanded((v) => !v)}
                    endIcon={expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}>
              {expanded ? 'Hide details' : 'Why this score?'}
            </Button>
          </Stack>
          {error && <Alert severity="error" sx={{ mt: 1.5 }}>{error}</Alert>}
        </Box>
      </Box>

      <Collapse in={expanded} unmountOnExit>
        <Divider sx={{ my: 2 }} />
        <Typography variant="subtitle2" sx={{ mb: 1 }}>Score breakdown</Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, columnGap: 3, rowGap: 1.5, mb: 2 }}>
          {INPUTS.map((name) => {
            const value = o.breakdown?.inputs?.[name];
            const isMissing = value === null || value === undefined || missing.has(name);
            const points = o.breakdown?.contributions?.[name];
            const weight = o.breakdown?.weights?.[name];
            return (
              <Tooltip key={name} title={INPUT_HELP[name]} placement="top-start">
                <Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                    <Typography variant="body2">{INPUT_LABEL[name]}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {isMissing ? 'no data' : `${points?.toFixed(1) ?? '0'} of ${weight !== undefined ? Math.round(weight * 100) : '?'} pts`}
                    </Typography>
                  </Box>
                  <LinearProgress variant="determinate" value={isMissing ? 0 : Math.round((value ?? 0) * 100)}
                                  color={isMissing ? 'inherit' : 'primary'}
                                  sx={{ height: 6, borderRadius: 3, bgcolor: 'action.hover' }} />
                </Box>
              </Tooltip>
            );
          })}
        </Box>
        {missing.size > 0 && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
            Inputs with no data contribute nothing; the score is not inflated to compensate.
          </Typography>
        )}
        {o.evidence?.explanation && (
          <>
            <Typography variant="subtitle2" sx={{ mt: 1 }}>Evidence</Typography>
            <Typography variant="body2" sx={{ mb: 1 }}>{o.evidence.explanation}</Typography>
          </>
        )}
        {o.evidence?.source_urls?.length > 0 && (
          <Stack spacing={0.5}>
            {o.evidence.source_urls.map((url) => (
              <Link key={url} href={url} target="_blank" rel="noopener noreferrer" variant="body2"
                    sx={{ wordBreak: 'break-all', display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                <OpenInNewIcon sx={{ fontSize: 14 }} /> {url}
              </Link>
            ))}
          </Stack>
        )}
      </Collapse>

      <Dialog open={noteOpen} onClose={() => busy === null && setNoteOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Note</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>{o.title}</Typography>
          <TextField
            autoFocus fullWidth multiline minRows={3}
            value={noteDraft} onChange={(e) => setNoteDraft(e.target.value)}
            placeholder="Why this matters, who is following up…"
          />
          {error && noteOpen && <Alert severity="error" sx={{ mt: 1.5 }}>{error}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNoteOpen(false)} disabled={busy !== null}>Cancel</Button>
          <Button variant="contained" onClick={saveNote} disabled={busy !== null}
                  startIcon={busy === 'note' ? <CircularProgress size={16} color="inherit" /> : undefined}>
            Save note
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
};

export default OpportunityCard;
