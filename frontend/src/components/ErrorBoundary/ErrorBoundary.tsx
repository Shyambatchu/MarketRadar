import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Alert, AlertTitle, Box, Button } from '@mui/material';

interface ErrorBoundaryProps {
  children: ReactNode;
  // Changing this clears a caught error, so navigating to another page
  // recovers without a full reload.
  resetKey?: string;
}

interface ErrorBoundaryState {
  error: Error | null;
  resetKey?: string;
}

/**
 * Contains a render failure, or a page chunk that failed to load, to the page
 * area. Without it one exception unmounted the whole app, sidebar included,
 * and left a blank window with no way back.
 */
class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null, resetKey: this.props.resetKey };

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { error };
  }

  static getDerivedStateFromProps(props: ErrorBoundaryProps, state: ErrorBoundaryState) {
    return props.resetKey !== state.resetKey ? { error: null, resetKey: props.resetKey } : null;
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Page failed to render', error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    // A lazy page whose chunk is gone (typically after a rebuild) needs a
    // reload to fetch the new bundle; retrying the render cannot help.
    const chunkFailed = /dynamically imported module|Loading chunk|Importing a module script failed/i
      .test(error.message);

    return (
      <Box sx={{ maxWidth: 720 }}>
        <Alert
          severity="error"
          action={
            <Button
              color="inherit"
              size="small"
              onClick={() => (chunkFailed ? window.location.reload() : this.setState({ error: null }))}
            >
              {chunkFailed ? 'Reload' : 'Try again'}
            </Button>
          }
        >
          <AlertTitle>This page could not be displayed</AlertTitle>
          {chunkFailed
            ? 'The page could not be loaded, usually because the app was updated. Reload to fetch the latest version.'
            : 'Something went wrong while rendering this page. Other pages are unaffected. Your saved data is untouched.'}
        </Alert>
      </Box>
    );
  }
}

export default ErrorBoundary;
