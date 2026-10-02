import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import theme from './theme/theme';
import AppLayout from './layouts/AppLayout';
import Dashboard from './pages/Dashboard/Dashboard';
import MarketResearch from './pages/MarketResearch/MarketResearch';
import PriceIntelligence from './pages/PriceIntelligence/PriceIntelligence';
import Competitors from './pages/Competitors/Competitors';
import Products from './pages/Products/Products';
import Trends from './pages/Trends/Trends';
import MarketPulse from './pages/MarketPulse/MarketPulse';
import AIAnalyst from './pages/AIAnalyst/AIAnalyst';
import EmptyState from './components/EmptyState/EmptyState';

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
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Router>
    </ThemeProvider>
  );
}

export default App;
