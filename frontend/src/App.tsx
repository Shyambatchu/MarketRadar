import { lazy } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import theme from './theme/theme';
import AppLayout from './layouts/AppLayout';
import EmptyState from './components/EmptyState/EmptyState';

// Each page is its own chunk, so the first load only fetches the page in view.
const Dashboard = lazy(() => import('./pages/Dashboard/Dashboard'));
const MarketResearch = lazy(() => import('./pages/MarketResearch/MarketResearch'));
const PriceIntelligence = lazy(() => import('./pages/PriceIntelligence/PriceIntelligence'));
const Competitors = lazy(() => import('./pages/Competitors/Competitors'));
const Products = lazy(() => import('./pages/Products/Products'));
const Trends = lazy(() => import('./pages/Trends/Trends'));
const MarketPulse = lazy(() => import('./pages/MarketPulse/MarketPulse'));
const AIAnalyst = lazy(() => import('./pages/AIAnalyst/AIAnalyst'));
const Opportunities = lazy(() => import('./pages/Opportunities/Opportunities'));
const Reports = lazy(() => import('./pages/Reports/Reports'));
const MarketSignals = lazy(() => import('./pages/MarketSignals/MarketSignals'));
const Usage = lazy(() => import('./pages/Usage/Usage'));

const NotFound = () => (
  <EmptyState
    title="Page not found"
    description="This address does not match any MarketRadar page. Use the navigation to continue."
  />
);

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="research" element={<MarketResearch />} />
            <Route path="prices" element={<PriceIntelligence />} />
            <Route path="competitors" element={<Competitors />} />
            <Route path="products" element={<Products />} />
            <Route path="trends" element={<Trends />} />
            <Route path="pulse" element={<MarketPulse />} />
            <Route path="analyst" element={<AIAnalyst />} />
            <Route path="opportunities" element={<Opportunities />} />
            <Route path="reports" element={<Reports />} />
            <Route path="signals" element={<MarketSignals />} />
            <Route path="usage" element={<Usage />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Router>
    </ThemeProvider>
  );
}

export default App;
