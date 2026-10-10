import { useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, Collapse, Link, List, ListItem,
  ListItemText, Paper, TextField, Typography,
} from '@mui/material';
import QuestionAnswerOutlinedIcon from '@mui/icons-material/QuestionAnswerOutlined';

import { askAnalyst } from '../../services/analystApi';
import type { AnalystAnswer, CitedStatement, EvidenceItem } from '../../types/analyst';
import { errorMessage, formatDate, humanize } from '../../utils/format';

const SUGGESTIONS = [
  'What changed in this market during the selected period?',
  'Which competitors have the most relevant offers?',
  'Which products have unusual price differences?',
  'What opportunities should be investigated next?',
  'Which findings have weak or conflicting evidence?',
];

const KIND_COLOR: Record<string, 'success' | 'warning' | 'info' | 'default'> = {
  observation: 'success',
  price_alert: 'warning',
  news: 'info',
};

// Provider URLs are untrusted text; a malformed one must not break the panel.
const hostOf = (url: string): string => {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
};

interface Props {
  market: string | null | undefined;
  location: string | null | undefined;
  disabled: boolean;
}

/**
 * Questions answered only from numbered, stored evidence. The evidence list
 * comes back with every answer, so a citation like [F3] can always be opened
 * and checked against its source.
 */
const AskAnalyst = ({ market, location, disabled }: Props) => {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<AnalystAnswer | null>(null);
  const [focused, setFocused] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  const ask = async (text: string) => {
    const q = text.trim();
    if (q.length < 3 || loading) return;
    setQuestion(q);
    setLoading(true);
    setError(null);
    setAnswer(null);
    setFocused(null);
    try {
      setAnswer(await askAnalyst({ question: q, market, location }));
    } catch (err) {
      setError(errorMessage(err, 'The question could not be answered.'));
    } finally {
      setLoading(false);
    }
  };

  const byId = new Map((answer?.evidence ?? []).map((e) => [e.id, e]));
  const relevant = new Set(answer?.relevant_evidence ?? []);
  const cited = new Set([
    ...(answer?.facts ?? []), ...(answer?.interpretations ?? []), ...(answer?.hypotheses ?? []),
  ].flatMap((s) => s.citations));
  const shown: EvidenceItem[] = answer
    ? (showAll ? answer.evidence
      : answer.evidence.filter((e) => cited.has(e.id) || relevant.has(e.id)))
    : [];

  const cite = (id: string) => (
    <Chip key={id} size="small" label={id} variant={focused === id ? 'filled' : 'outlined'}
          color="primary" onClick={() => { setFocused(id); setShowAll(true); }}
          sx={{ ml: 0.5, height: 20, fontSize: 11 }} />
  );

  const statements = (title: string, items: CitedStatement[], help?: string) => items.length > 0 && (
    <Box sx={{ mb: 1.5 }}>
      <Typography variant="subtitle2">{title}</Typography>
      {help && <Typography variant="caption" color="text.secondary">{help}</Typography>}
      <List dense disablePadding>
        {items.map((s, i) => (
          <ListItem key={i} disableGutters sx={{ display: 'block' }}>
            <Typography variant="body2" component="span">{s.statement}</Typography>
            {s.citations.map(cite)}
          </ListItem>
        ))}
      </List>
    </Box>
  );

  return (
    <Paper sx={{ p: 3, mb: 4 }}>
      <Typography variant="h6" sx={{ mb: 0.5 }}>Ask the analyst</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Answers use only stored evidence for the selected market: computed observations,
        detected price changes and collected news. Every claim cites a numbered evidence item.
      </Typography>
      <Box sx={{ display: 'flex', gap: 1, flexDirection: { xs: 'column', sm: 'row' } }}>
        <TextField
          fullWidth size="small" label="Your question" value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') ask(question); }}
          disabled={disabled || loading}
          placeholder={disabled ? 'Select a market and location first' : 'e.g. Which prices changed most?'}
          slotProps={{ htmlInput: { maxLength: 500 } }}
        />
        <Button
          variant="contained" onClick={() => ask(question)}
          disabled={disabled || loading || question.trim().length < 3}
          startIcon={loading ? <CircularProgress size={18} color="inherit" /> : <QuestionAnswerOutlinedIcon />}
          sx={{ minWidth: 120 }}
        >
          Ask
        </Button>
      </Box>
      <Box sx={{ mt: 1.5, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        {SUGGESTIONS.map((s) => (
          <Chip key={s} size="small" label={s} variant="outlined" disabled={disabled || loading}
                onClick={() => ask(s)} />
        ))}
      </Box>

      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}

      {answer && (
        <Box sx={{ mt: 3 }}>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1.5 }}>
            <Chip size="small" color={answer.mode === 'assisted' ? 'info' : 'default'} variant="outlined"
                  label={answer.mode === 'assisted'
                    ? `Written by ${answer.provider_name ?? 'AI provider'}, validated against the evidence`
                    : 'Evidence only (no written answer)'} />
            {answer.confidence && (
              <Chip size="small" variant="outlined" label={`${answer.confidence} confidence`} />
            )}
            <Chip size="small" variant="outlined" label={`${answer.evidence.length} evidence items`} />
          </Box>

          {answer.answer_rejected && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              The written answer was withheld: {answer.rejection_reason} The relevant evidence is listed below.
            </Alert>
          )}
          {answer.provider_error && (
            <Alert severity="warning" sx={{ mb: 2 }}>{answer.provider_error}</Alert>
          )}
          {answer.detail && !answer.answer_rejected && (
            <Alert severity="info" sx={{ mb: 2 }}>{answer.detail}</Alert>
          )}

          {answer.answer && (
            <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
              <Typography variant="body1">{answer.answer}</Typography>
            </Paper>
          )}
          {statements('Facts', answer.facts, 'Restated from the evidence.')}
          {statements('Interpretations', answer.interpretations, 'Cautious readings of the evidence.')}
          {statements('Hypotheses to investigate', answer.hypotheses, 'Unproven — worth checking next.')}
          {answer.missing_data.length > 0 && (
            <Box sx={{ mb: 1.5 }}>
              <Typography variant="subtitle2">Missing data</Typography>
              <List dense disablePadding>
                {answer.missing_data.map((m, i) => (
                  <ListItem key={i} disableGutters><ListItemText primary={m} /></ListItem>
                ))}
              </List>
            </Box>
          )}

          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: 2 }}>
            <Typography variant="subtitle2">
              Evidence {showAll ? `(all ${answer.evidence.length})` : `(${shown.length} relevant)`}
            </Typography>
            <Button size="small" onClick={() => setShowAll((v) => !v)}>
              {showAll ? 'Show relevant only' : 'Show all evidence'}
            </Button>
          </Box>
          <Collapse in>
            <List dense disablePadding>
              {shown.map((e) => (
                <ListItem key={e.id} disableGutters alignItems="flex-start"
                          sx={{ bgcolor: focused === e.id ? 'action.selected' : undefined, borderRadius: 1, px: 1 }}>
                  <ListItemText
                    primary={(
                      <Box sx={{ display: 'flex', gap: 1, alignItems: 'baseline', flexWrap: 'wrap' }}>
                        <Chip size="small" label={e.id} />
                        <Chip size="small" variant="outlined" color={KIND_COLOR[e.kind] ?? 'default'}
                              label={humanize(e.kind)} />
                        <Typography variant="body2">{e.statement}</Typography>
                      </Box>
                    )}
                    secondary={(
                      <>
                        {e.observed_at ? `Observed ${formatDate(e.observed_at)}` : 'No observation date'}
                        {e.record_ids.length > 0 && ` · records ${e.record_ids.slice(0, 6).join(', ')}`}
                        {e.source_urls.slice(0, 3).map((u) => (
                          <span key={u}> · <Link href={u} target="_blank" rel="noopener">{hostOf(u)}</Link></span>
                        ))}
                      </>
                    )}
                  />
                </ListItem>
              ))}
              {shown.length === 0 && byId.size > 0 && (
                <Typography variant="body2" color="text.secondary">
                  No evidence item matched the question. Use "Show all evidence" to browse it.
                </Typography>
              )}
            </List>
          </Collapse>
        </Box>
      )}
    </Paper>
  );
};

export default AskAnalyst;
