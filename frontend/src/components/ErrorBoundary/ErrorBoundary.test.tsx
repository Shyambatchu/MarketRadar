import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import ErrorBoundary from './ErrorBoundary';

const Boom = () => {
  throw new Error('render failed');
};

describe('ErrorBoundary', () => {
  it('contains a render failure instead of blanking the app', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    render(<ErrorBoundary resetKey="/a"><Boom /></ErrorBoundary>);
    expect(screen.getByText('This page could not be displayed')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });

  it('clears the error when the route changes', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const { rerender } = render(<ErrorBoundary resetKey="/a"><Boom /></ErrorBoundary>);
    rerender(<ErrorBoundary resetKey="/b"><p>next page</p></ErrorBoundary>);
    expect(screen.getByText('next page')).toBeInTheDocument();
  });

  it('offers a reload when a page chunk failed to load', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const ChunkFail = () => {
      throw new Error('Failed to fetch dynamically imported module: /assets/x.js');
    };
    render(<ErrorBoundary><ChunkFail /></ErrorBoundary>);
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument();
  });
});
