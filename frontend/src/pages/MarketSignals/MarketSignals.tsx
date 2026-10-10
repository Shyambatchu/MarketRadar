import { useSearchParams } from 'react-router-dom';
import { Box, Tab, Tabs } from '@mui/material';

import PageHeader from '../../components/PageHeader/PageHeader';
import InterestTab from './InterestTab';
import NewsTab from './NewsTab';

type SignalsTab = 'interest' | 'news';

const MarketSignals = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab: SignalsTab = searchParams.get('tab') === 'news' ? 'news' : 'interest';
  // `q` only prefills the inputs. Running a search spends a credit, so it is
  // never started by opening a link.
  const initialQuery = searchParams.get('q') ?? '';

  const changeTab = (next: SignalsTab) => {
    const params = new URLSearchParams(searchParams);
    params.set('tab', next);
    setSearchParams(params, { replace: true });
  };

  return (
    <Box>
      <PageHeader
        title="Market Signals"
        subtitle="Relative search interest from Google Trends and recent coverage from Google News."
      />

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={tab} onChange={(_, v: SignalsTab) => changeTab(v)} aria-label="market signals tabs">
          <Tab value="interest" label="Search interest" />
          <Tab value="news" label="News" />
        </Tabs>
      </Box>

      {/* Both stay mounted so switching tabs never discards a paid-for result. */}
      <Box sx={{ display: tab === 'interest' ? 'block' : 'none' }}>
        <InterestTab initialQuery={initialQuery} />
      </Box>
      <Box sx={{ display: tab === 'news' ? 'block' : 'none' }}>
        <NewsTab initialQuery={initialQuery} />
      </Box>
    </Box>
  );
};

export default MarketSignals;
