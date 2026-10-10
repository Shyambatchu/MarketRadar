import { useEffect, useState } from 'react';
import { Autocomplete, Box, TextField, Typography } from '@mui/material';

import { getMarketPulseOptions } from '../../services/marketPulseApi';
import type { MarketOption } from '../../types/marketPulse';
import { errorMessage, isCanceled } from '../../utils/format';

const scopeLabel = (o: MarketOption): string =>
  `${o.market ?? 'Unspecified market'} — ${o.location ?? 'no location'}`;

interface MarketScopeSelectProps {
  /** `null` means every market. */
  value: MarketOption | null;
  onChange: (value: MarketOption | null) => void;
  label?: string;
  allLabel?: string;
  disabled?: boolean;
}

/**
 * A market/location picker whose choices come from observation history, so a
 * selection always refers to something actually recorded. Clearing it means
 * "all markets" rather than an invented category.
 */
const MarketScopeSelect = ({
  value, onChange, label = 'Market and location', allLabel = 'All markets', disabled,
}: MarketScopeSelectProps) => {
  const [options, setOptions] = useState<MarketOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getMarketPulseOptions(controller.signal)
      .then((res) => setOptions(res.options))
      .catch((err) => {
        if (!isCanceled(err)) setError(errorMessage(err, 'Observed markets could not be loaded.'));
      })
      // An aborted (StrictMode) request must not end the loading state early.
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  return (
    <Autocomplete
      size="small"
      options={options}
      value={value}
      onChange={(_, v) => onChange(v)}
      disabled={disabled}
      getOptionLabel={scopeLabel}
      isOptionEqualToValue={(a, b) => a.market === b.market && a.location === b.location}
      loading={loading}
      renderInput={(params) => (
        <TextField
          {...params} label={label}
          placeholder={loading ? 'Loading observed markets…' : allLabel}
          error={Boolean(error)}
          helperText={error ?? (value ? undefined : `Showing: ${allLabel}. Clear the field to return to it.`)}
          // Merge, never replace: params.slotProps carries the input ref the
          // Autocomplete needs; overwriting it detached the input.
          slotProps={{
            ...params.slotProps,
            inputLabel: { ...params.slotProps?.inputLabel, shrink: true },
          }}
        />
      )}
      renderOption={(props, o) => (
        <li {...props} key={`${o.market}-${o.location}`}>
          <Box>
            <Typography variant="body2">{o.market ?? 'Unspecified market'}</Typography>
            <Typography variant="caption" color="text.secondary">
              {o.location ?? 'no location'} · {o.merchants} merchant(s)
            </Typography>
          </Box>
        </li>
      )}
      noOptionsText="No markets have been observed yet."
    />
  );
};

export default MarketScopeSelect;
