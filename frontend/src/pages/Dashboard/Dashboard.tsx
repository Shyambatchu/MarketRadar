import { useNavigate } from 'react-router-dom';
import { Box, Typography, Grid, Paper, IconButton } from '@mui/material';
import SearchOutlinedIcon from '@mui/icons-material/SearchOutlined';
import StorefrontOutlinedIcon from '@mui/icons-material/StorefrontOutlined';
import TrendingUpOutlinedIcon from '@mui/icons-material/TrendingUpOutlined';
import AttachMoneyOutlinedIcon from '@mui/icons-material/AttachMoneyOutlined';
import Inventory2OutlinedIcon from '@mui/icons-material/Inventory2Outlined';
import InsightsOutlinedIcon from '@mui/icons-material/InsightsOutlined';
import PsychologyOutlinedIcon from '@mui/icons-material/PsychologyOutlined';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import InsertChartOutlinedIcon from '@mui/icons-material/InsertChartOutlined';

const Dashboard = () => {
  const navigate = useNavigate();

  const cards = [
    {
      title: 'Start Market Research',
      description: 'Search and analyze market visibility across search engines and local results.',
      icon: <SearchOutlinedIcon sx={{ color: 'primary.main', fontSize: 28 }} />,
      path: '/research',
      iconBg: 'primary.light',
    },
    {
      title: 'Analyze Competitors',
      description: 'Identify the businesses competing in a market and place, with the evidence for each.',
      icon: <StorefrontOutlinedIcon sx={{ color: 'success.dark', fontSize: 28 }} />,
      path: '/competitors',
      iconBg: 'success.light',
    },
    {
      title: 'Find Products',
      description: "Check which merchants' catalogues list a product, and at what verified price.",
      icon: <Inventory2OutlinedIcon sx={{ color: 'info.dark', fontSize: 28 }} />,
      path: '/products',
      iconBg: 'info.light',
    },
    {
      title: 'Track Trends',
      description: 'See what changed between distinct measurements, and what cannot be compared yet.',
      icon: <TrendingUpOutlinedIcon sx={{ color: 'warning.dark', fontSize: 28 }} />,
      path: '/trends',
      iconBg: 'warning.light',
    },
    {
      title: 'Compare Local Prices',
      description: 'Compare verified prices for one product across nearby stores.',
      icon: <AttachMoneyOutlinedIcon sx={{ color: 'secondary.dark', fontSize: 28 }} />,
      path: '/prices',
      iconBg: 'secondary.light',
    },
    {
      title: 'Market Pulse',
      description: 'A factual snapshot of one observed market and location.',
      icon: <InsightsOutlinedIcon sx={{ color: 'primary.dark', fontSize: 28 }} />,
      path: '/pulse',
      iconBg: 'primary.light',
    },
    {
      title: 'AI Analyst',
      description: 'Evidence-referenced statements computed from a Market Pulse snapshot.',
      icon: <PsychologyOutlinedIcon sx={{ color: 'success.dark', fontSize: 28 }} />,
      path: '/analyst',
      iconBg: 'success.light',
    },
  ];

  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', mt: 2 }}>
      <Box sx={{ mb: 6 }}>
        <Typography variant="h1" sx={{ fontSize: '2.25rem', mb: 1, color: 'text.primary' }}>
          Welcome to MarketRadar
        </Typography>
        <Typography variant="subtitle1" color="text.secondary" sx={{ fontSize: '1.125rem' }}>
          Monitor markets, competitors, pricing, trends and search visibility.
        </Typography>
      </Box>

      <Grid container spacing={3} sx={{ mb: 6 }}>
        {cards.map((card, idx) => (
          <Grid key={idx} size={{xs: 12, sm: 6, md: 3}}>
            <Paper
              role="link"
              tabIndex={0}
              aria-label={card.title}
              onClick={() => navigate(card.path)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  navigate(card.path);
                }
              }}
              sx={{
                p: 3,
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                cursor: 'pointer',
                transition: 'all 0.2s ease-in-out',
                '&:hover': {
                  transform: 'translateY(-2px)',
                  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
                  borderColor: 'primary.main'
                },
              }}
            >
              <Box
                sx={{
                  width: 48,
                  height: 48,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  bgcolor: card.iconBg,
                  mb: 2,
                  opacity: 0.8
                }}
              >
                {card.icon}
              </Box>
              <Typography variant="h6" sx={{ mb: 1, fontWeight: 600 }}>
                {card.title}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ flexGrow: 1, mb: 2, lineHeight: 1.5 }}>
                {card.description}
              </Typography>
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 'auto' }}>
                <IconButton size="small" sx={{ pointerEvents: 'none' }}>
                  <ChevronRightIcon />
                </IconButton>
              </Box>
            </Paper>
          </Grid>
        ))}
      </Grid>

      <Paper 
        elevation={0}
        sx={{ 
          p: 3, 
          display: 'flex', 
          alignItems: 'flex-start',
          gap: 2,
          bgcolor: 'primary.light',
          border: 'none',
          borderRadius: 2,
          opacity: 0.9
        }}
      >
        <Box sx={{ p: 1, bgcolor: '#fff', borderRadius: '50%', display: 'flex' }}>
          <InsertChartOutlinedIcon color="primary" />
        </Box>
        <Box>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, color: 'primary.dark', mb: 0.5 }}>
            Ready to get started?
          </Typography>
          <Typography variant="body2" sx={{ color: 'primary.dark' }}>
            Use the navigation menu to explore different modules or start with a market research search.
          </Typography>
        </Box>
      </Paper>
    </Box>
  );
};

export default Dashboard;
