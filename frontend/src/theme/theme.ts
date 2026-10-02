import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#4F46E5', // Indigo 600
      light: '#818CF8', // Indigo 400
      dark: '#3730A3', // Indigo 800
      contrastText: '#FFFFFF',
    },
    secondary: {
      main: '#475569', // Slate 600
      light: '#94A3B8', // Slate 400
      dark: '#1E293B', // Slate 800
      contrastText: '#FFFFFF',
    },
    background: {
      default: '#F8FAFC', // Slate 50
      paper: '#FFFFFF',
    },
    text: {
      primary: '#0F172A', // Slate 900
      secondary: '#475569', // Slate 600
      disabled: '#94A3B8', // Slate 400
    },
    success: {
      main: '#10B981', // Emerald 500
      light: '#D1FAE5', // Emerald 100
      dark: '#047857', // Emerald 700
    },
    warning: {
      main: '#F59E0B', // Amber 500
      light: '#FEF3C7', // Amber 100
      dark: '#B45309', // Amber 700
    },
    error: {
      main: '#EF4444', // Red 500
      light: '#FEE2E2', // Red 100
      dark: '#B91C1C', // Red 700
    },
    info: {
      main: '#3B82F6', // Blue 500
      light: '#DBEAFE', // Blue 100
      dark: '#1D4ED8', // Blue 700
    },
    divider: '#E2E8F0', // Slate 200
  },
  shape: {
    borderRadius: 8,
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: { fontSize: '2rem', fontWeight: 700, lineHeight: 1.2, letterSpacing: '-0.02em' },
    h2: { fontSize: '1.75rem', fontWeight: 600, lineHeight: 1.3, letterSpacing: '-0.01em' },
    h3: { fontSize: '1.5rem', fontWeight: 600, lineHeight: 1.3 },
    h4: { fontSize: '1.25rem', fontWeight: 600, lineHeight: 1.4 },
    h5: { fontSize: '1.125rem', fontWeight: 600, lineHeight: 1.4 },
    h6: { fontSize: '1rem', fontWeight: 600, lineHeight: 1.4 },
    subtitle1: { fontSize: '1rem', fontWeight: 500, lineHeight: 1.5 },
    subtitle2: { fontSize: '0.875rem', fontWeight: 500, lineHeight: 1.57 },
    body1: { fontSize: '1rem', fontWeight: 400, lineHeight: 1.5 },
    body2: { fontSize: '0.875rem', fontWeight: 400, lineHeight: 1.43 },
    caption: { fontSize: '0.75rem', fontWeight: 400, lineHeight: 1.66 },
    overline: { fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' },
    button: { textTransform: 'none', fontWeight: 500 },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          boxShadow: 'none',
          '&:hover': {
            boxShadow: 'none',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
          border: '1px solid #E2E8F0',
          backgroundImage: 'none',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
        elevation1: {
          boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
          border: '1px solid #E2E8F0',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#FFFFFF',
          color: '#0F172A',
          boxShadow: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
          borderBottom: '1px solid #E2E8F0',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: '#F8FAFC',
          borderRight: '1px solid #E2E8F0',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontWeight: 600,
          backgroundColor: '#F8FAFC',
          color: '#475569',
          borderBottom: '1px solid #E2E8F0',
        },
        body: {
          borderBottom: '1px solid #E2E8F0',
        },
      },
    },
  },
});

export default theme;
