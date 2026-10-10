import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import ExportButton from './ExportButton';

describe('ExportButton', () => {
  it('links to the server-side CSV', () => {
    render(<ExportButton href="http://api/export/competitors.csv?market=x" />);
    const link = screen.getByRole('link', { name: /export csv/i });
    expect(link).toHaveAttribute('href', 'http://api/export/competitors.csv?market=x');
    expect(link).toHaveAttribute('download');
  });

  it('has no target when disabled', () => {
    render(<ExportButton href="http://api/x.csv" disabled />);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });
});
