import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import FiberNewOutlinedIcon from '@mui/icons-material/FiberNewOutlined';
import SensorsOutlinedIcon from '@mui/icons-material/SensorsOutlined';

/** Category → readable name and icon. */
export const CATEGORY: Record<string, { label: string; icon: React.ReactNode }> = {
  competitor_price_move: { label: 'Competitor price cut', icon: <TrendingDownIcon fontSize="small" /> },
  pricing_headroom: { label: 'Pricing headroom', icon: <TrendingUpIcon fontSize="small" /> },
  price_gap: { label: 'Price gap', icon: <CompareArrowsIcon fontSize="small" /> },
  new_competitor_offer: { label: 'New competitor offer', icon: <FiberNewOutlinedIcon fontSize="small" /> },
  rising_search_interest: { label: 'Rising search interest', icon: <SensorsOutlinedIcon fontSize="small" /> },
};

export const scoreBand = (score: number): { label: string; color: 'success' | 'warning' | 'default' } =>
  score >= 60 ? { label: 'High priority', color: 'success' }
    : score >= 35 ? { label: 'Medium priority', color: 'warning' }
      : { label: 'Low priority', color: 'default' };
