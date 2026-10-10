import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  isQuiet, requestFinished, requestStarted, resetLoadingTracker, subscribe,
} from './loadingTracker';

describe('loadingTracker', () => {
  afterEach(() => resetLoadingTracker());

  it('reports busy while any request is in flight', () => {
    const listener = vi.fn();
    const unsubscribe = subscribe(listener);
    expect(listener).toHaveBeenLastCalledWith(false);
    requestStarted();
    requestStarted();
    expect(listener).toHaveBeenLastCalledWith(true);
    requestFinished();
    expect(listener).toHaveBeenLastCalledWith(true);
    requestFinished();
    expect(listener).toHaveBeenLastCalledWith(false);
    unsubscribe();
  });

  it('never goes negative on an extra finish', () => {
    const listener = vi.fn();
    subscribe(listener);
    requestFinished();
    requestStarted();
    expect(listener).toHaveBeenLastCalledWith(true);
  });

  it('ignores background health polling', () => {
    expect(isQuiet('/health')).toBe(true);
    expect(isQuiet('/competitors')).toBe(false);
    expect(isQuiet(undefined)).toBe(false);
  });
});

describe('navigation loading', () => {
  afterEach(() => resetLoadingTracker());

  it('is busy from a menu click until the route renders', async () => {
    const { beginNavigation, endNavigation } = await import('./loadingTracker');
    const listener = vi.fn();
    subscribe(listener);
    beginNavigation();
    expect(listener).toHaveBeenLastCalledWith(true);
    endNavigation();
    expect(listener).toHaveBeenLastCalledWith(false);
  });

  it('stays busy while requests run after the route rendered', async () => {
    const { beginNavigation, endNavigation } = await import('./loadingTracker');
    const listener = vi.fn();
    subscribe(listener);
    beginNavigation();
    requestStarted();
    endNavigation();
    expect(listener).toHaveBeenLastCalledWith(true);
    requestFinished();
    expect(listener).toHaveBeenLastCalledWith(false);
  });
});
