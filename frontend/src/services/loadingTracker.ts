/**
 * Drives the one global progress bar: it is on while any API request is in
 * flight, and from the moment a menu item is clicked until the new page has
 * rendered.
 *
 * Navigation needs its own signal because React Router performs navigations
 * inside a React transition: with lazy-loaded pages the old page stays on
 * screen (and the URL-derived location stays old) until the new page's code
 * has arrived. A loader that only watched the location would appear after the
 * wait it is meant to cover.
 *
 * Background polling (the health check) is excluded: a bar that blinks every
 * 30 seconds would read as constant loading.
 */
type Listener = (busy: boolean) => void;

let inFlight = 0;
let navigating = false;
let navigationTimeout: ReturnType<typeof setTimeout> | undefined;
const listeners = new Set<Listener>();

// A navigation that never completes (a failed chunk load is caught by the
// error boundary) must not leave the bar running forever.
const NAVIGATION_TIMEOUT_MS = 15000;

const busy = () => inFlight > 0 || navigating;
const notify = () => {
  const value = busy();
  listeners.forEach((listener) => listener(value));
};

export const QUIET_PATHS = ['/health'];

export const isQuiet = (url: string | undefined): boolean =>
  !!url && QUIET_PATHS.some((path) => url.endsWith(path) || url.includes(`${path}?`));

export const requestStarted = () => {
  inFlight += 1;
  notify();
};

export const requestFinished = () => {
  inFlight = Math.max(0, inFlight - 1);
  notify();
};

/** Call when the user starts a navigation (e.g. clicks a menu item). */
export const beginNavigation = () => {
  navigating = true;
  clearTimeout(navigationTimeout);
  navigationTimeout = setTimeout(endNavigation, NAVIGATION_TIMEOUT_MS);
  notify();
};

/** Called once the new route has rendered. */
export const endNavigation = () => {
  clearTimeout(navigationTimeout);
  if (!navigating) return;
  navigating = false;
  notify();
};

export const subscribe = (listener: Listener): (() => void) => {
  listeners.add(listener);
  listener(busy());
  return () => { listeners.delete(listener); };
};

/** Test helper: reset all state between tests. */
export const resetLoadingTracker = () => {
  inFlight = 0;
  navigating = false;
  clearTimeout(navigationTimeout);
  notify();
};
