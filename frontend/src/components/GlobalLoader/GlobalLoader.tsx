import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { LinearProgress } from '@mui/material';
import { endNavigation, subscribe } from '../../services/loadingTracker';

// Once shown, the bar stays at least this long, so a fast (cached) load
// still gives visible feedback instead of a flicker.
const MIN_VISIBLE_MS = 400;

/**
 * One progress bar for the whole app, pinned under the header. It is shown
 * from a menu click until the new page renders, and whenever page data is
 * loading.
 */
const GlobalLoader = () => {
  const location = useLocation();
  const [busy, setBusy] = useState(false);
  const [visible, setVisible] = useState(false);
  const shownAt = useRef(0);

  useEffect(() => subscribe(setBusy), []);

  // The new route has committed: the navigation part of the wait is over.
  useEffect(() => { endNavigation(); }, [location.pathname]);

  useEffect(() => {
    if (busy) {
      shownAt.current = Date.now();
      const show = window.setTimeout(() => setVisible(true), 0);
      return () => window.clearTimeout(show);
    }
    const remaining = Math.max(0, MIN_VISIBLE_MS - (Date.now() - shownAt.current));
    const hide = window.setTimeout(() => setVisible(false), remaining);
    return () => window.clearTimeout(hide);
  }, [busy]);

  if (!visible) return null;
  return (
    <LinearProgress
      aria-label="Loading data"
      sx={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 3, pointerEvents: 'none' }}
    />
  );
};

export default GlobalLoader;
