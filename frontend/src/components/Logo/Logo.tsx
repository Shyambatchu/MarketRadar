import { useId } from 'react';
import { Box, Typography } from '@mui/material';

/**
 * The MarketRadar mark: a radar sweep whose needle breaks out toward rising
 * bars. The gradient runs blue (where the sweep begins) to green (where the
 * needle points), so the shape reads as movement rather than decoration.
 *
 * Kept as inline SVG rather than an <img> so it inherits crisp rendering at
 * any size and can be recoloured later without new assets. The gradient and
 * mask ids are generated per instance — two logos on one page would otherwise
 * share ids and the second would render against the first's definitions.
 */
export const LogoMark = ({ size = 32 }: { size?: number }) => {
  const uid = useId().replace(/:/g, '');
  const grad = `mr-grad-${uid}`;
  const cut = `mr-cut-${uid}`;

  return (
    <Box
      component="svg"
      viewBox="0 0 64 64"
      role="img"
      aria-label="MarketRadar"
      sx={{ width: size, height: size, display: 'block', flexShrink: 0 }}
    >
      <defs>
        <linearGradient id={grad} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0%" stopColor="#1D4ED8" />
          <stop offset="45%" stopColor="#0EA5E9" />
          <stop offset="100%" stopColor="#4ADE80" />
        </linearGradient>

        {/* Cuts a margin around the bars out of the rings behind them. Both
            share the gradient, so without this they merge into one blob. */}
        <mask id={cut}>
          <rect width="64" height="64" fill="#fff" />
          <rect x="21.5" y="37.5" width="12.5" height="18" rx="5" fill="#000" />
          <rect x="31.5" y="30.5" width="12.5" height="25" rx="5" fill="#000" />
          <rect x="41.5" y="23.5" width="12.5" height="32" rx="5" fill="#000" />
        </mask>
      </defs>

      <g transform="translate(1.7 2.3)">
        {/* Radar rings. Each dash gap is rotated to sit under the needle, so
            the needle breaks out of the sweep rather than crossing it. */}
        <g fill="none" stroke={`url(#${grad})`} strokeLinecap="round" mask={`url(#${cut})`}>
          <circle cx="30" cy="30" r="23" strokeWidth="6"
                  strokeDasharray="124.4 20.1" transform="rotate(-20 30 30)" />
          <circle cx="30" cy="30" r="14.5" strokeWidth="5.5"
                  strokeDasharray="77.2 13.9" transform="rotate(-17.5 30 30)" />
        </g>

        {/* Needle. Outside the mask: it clears the bars on its own, and
            masking it would nibble the hub. */}
        <g stroke={`url(#${grad})`} strokeLinecap="round">
          <line x1="30" y1="30" x2="46" y2="14" strokeWidth="5.5" />
          <circle cx="30" cy="30" r="3.4" fill={`url(#${grad})`} stroke="none" />
          <circle cx="48.6" cy="11.4" r="5" fill={`url(#${grad})`} stroke="none" />
        </g>

        <g fill={`url(#${grad})`}>
          <rect x="24" y="40" width="7.5" height="13" rx="2.6" />
          <rect x="34" y="33" width="7.5" height="20" rx="2.6" />
          <rect x="44" y="26" width="7.5" height="27" rx="2.6" />
        </g>
      </g>
    </Box>
  );
};

interface LogoProps {
  /** Height of the mark in pixels. The wordmark scales with it. */
  size?: number;
  /** Show the "Discover · Track · Understand · Grow" line. */
  showTagline?: boolean;
  /** Inverts the wordmark for dark surfaces. The mark itself needs no change. */
  inverted?: boolean;
}

/** The mark plus the wordmark. */
const Logo = ({ size = 32, showTagline = false, inverted = false }: LogoProps) => (
  <Box sx={{ display: 'flex', alignItems: 'center', gap: size * 0.045 + 0.6 }}>
    <LogoMark size={size} />
    <Box sx={{ lineHeight: 1 }}>
      <Typography
        component="span"
        sx={{
          display: 'block',
          fontSize: size * 0.56,
          fontWeight: 700,
          letterSpacing: '-0.025em',
          lineHeight: 1.1,
          color: inverted ? '#F8FAFC' : 'text.primary',
        }}
      >
        Market
        <Box component="span" sx={{ color: inverted ? '#60A5FA' : '#2563EB' }}>
          Radar
        </Box>
      </Typography>
      {showTagline && (
        <Typography
          component="span"
          sx={{
            display: 'block',
            fontSize: Math.max(size * 0.17, 8),
            fontWeight: 500,
            letterSpacing: '0.18em',
            textTransform: 'uppercase',
            color: inverted ? 'rgba(248,250,252,0.65)' : 'text.secondary',
            mt: 0.4,
          }}
        >
          Discover · Track · Understand · Grow
        </Typography>
      )}
    </Box>
  </Box>
);

export default Logo;
