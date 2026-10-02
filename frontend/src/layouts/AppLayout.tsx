import { useState, useEffect } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { 
  Box, Drawer, AppBar, Toolbar, List, Typography, IconButton, 
  ListItem, ListItemButton, ListItemIcon, ListItemText, useTheme, useMediaQuery,
  ListSubheader
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import DashboardOutlinedIcon from '@mui/icons-material/DashboardOutlined';
import SearchOutlinedIcon from '@mui/icons-material/SearchOutlined';
import StorefrontOutlinedIcon from '@mui/icons-material/StorefrontOutlined';
import TrendingUpOutlinedIcon from '@mui/icons-material/TrendingUpOutlined';
import ShowChartOutlinedIcon from '@mui/icons-material/ShowChartOutlined';
import AttachMoneyOutlinedIcon from '@mui/icons-material/AttachMoneyOutlined';
import Inventory2OutlinedIcon from '@mui/icons-material/Inventory2Outlined';
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';

import Logo from '../components/Logo/Logo';

import StatusIndicator from '../components/StatusIndicator/StatusIndicator';
import api from '../services/api';
import { isAxiosError } from 'axios';

const drawerWidth = 260;

const navGroups = [
  {
    title: 'OVERVIEW',
    items: [
      { text: 'Dashboard', path: '/', icon: <DashboardOutlinedIcon /> },
    ]
  },
  {
    title: 'RESEARCH',
    items: [
      { text: 'Market Research', path: '/research', icon: <SearchOutlinedIcon /> },
      { text: 'Competitors', path: '/competitors', icon: <StorefrontOutlinedIcon /> },
      { text: 'Trends', path: '/trends', icon: <TrendingUpOutlinedIcon /> },
      { text: 'Market Pulse', path: '/pulse', icon: <ShowChartOutlinedIcon /> },
    ]
  },
  {
    title: 'INTELLIGENCE',
    items: [
      { text: 'Price Intelligence', path: '/prices', icon: <AttachMoneyOutlinedIcon /> },
      { text: 'Products', path: '/products', icon: <Inventory2OutlinedIcon /> },
      { text: 'AI Analyst', path: '/analyst', icon: <AutoAwesomeOutlinedIcon /> },
    ]
  }
];

const AppLayout = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [backendStatus, setBackendStatus] = useState<'connected' | 'unavailable' | 'checking'>('checking');
  const location = useLocation();
  const navigate = useNavigate();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('md'));

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  useEffect(() => {
    const controller = new AbortController();
    // Only the first check shows "checking"; the 30-s re-checks keep the last
    // known status instead of flickering through it.
    const checkHealth = async () => {
      try {
        const response = await api.get('/health', { signal: controller.signal });
        if (response.data && response.data.status === 'ok') {
          setBackendStatus('connected');
        } else {
          setBackendStatus('unavailable');
        }
      } catch (err) {
        if (!isAxiosError(err) || err.code !== 'ERR_CANCELED') {
          setBackendStatus('unavailable');
        }
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => {
      clearInterval(interval);
      controller.abort();
    };
  }, []);

  const getPageTitle = () => {
    if (location.pathname === '/') return 'Dashboard';
    for (const group of navGroups) {
      const match = group.items.find(item => item.path === location.pathname);
      if (match) return `${group.title} / ${match.text}`;
    }
    return 'MarketRadar';
  };

  const drawer = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Toolbar sx={{ px: 2, py: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
        <Logo size={34} />
      </Toolbar>
      
      <Box sx={{ overflow: 'auto', flex: 1, py: 2 }}>
        {navGroups.map((group, groupIdx) => (
          <List 
            key={groupIdx} 
            subheader={
              <ListSubheader sx={{ bgcolor: 'transparent', lineHeight: '32px', fontWeight: 600, letterSpacing: '0.05em', fontSize: '0.75rem', color: 'text.disabled' }}>
                {group.title}
              </ListSubheader>
            }
            sx={{ mb: 1 }}
          >
            {group.items.map((item) => {
              const active = location.pathname === item.path;
              return (
                <ListItem key={item.text} disablePadding sx={{ px: 2, mb: 0.5 }}>
                  <ListItemButton 
                    selected={active}
                    onClick={() => {
                      navigate(item.path);
                      if (!isDesktop) setMobileOpen(false);
                    }}
                    sx={{ 
                      borderRadius: 1.5,
                      py: 1,
                      '&.Mui-selected': {
                        bgcolor: 'primary.light',
                        color: 'primary.dark',
                        '& .MuiListItemIcon-root': { color: 'primary.dark' },
                        '&:hover': { bgcolor: 'primary.light' }
                      },
                      '&:hover': {
                        bgcolor: 'action.hover'
                      }
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: 40, color: active ? 'primary.dark' : 'text.secondary' }}>
                      {item.icon}
                    </ListItemIcon>
                    <ListItemText primary={item.text} sx={{ '& .MuiListItemText-primary': { fontSize: '0.875rem', fontWeight: active ? 600 : 500 } }} />
                  </ListItemButton>
                </ListItem>
              );
            })}
          </List>
        ))}
      </Box>

      <Box sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider', bgcolor: 'background.paper' }}>
        <StatusIndicator status={backendStatus} />
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar 
        position="fixed" 
        elevation={0}
        sx={{ 
          width: { md: `calc(100% - ${drawerWidth}px)` }, 
          ml: { md: `${drawerWidth}px` } 
        }}
      >
        <Toolbar sx={{ justifyContent: 'space-between', minHeight: '64px !important' }}>
          <Box sx={{ display: "flex", alignItems: "center" }}>
            <IconButton
              color="inherit"
              edge="start"
              onClick={handleDrawerToggle}
              sx={{ mr: 2, display: { md: 'none' }, color: 'text.primary' }}
            >
              <MenuIcon />
            </IconButton>
            <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.secondary', display: { xs: 'none', sm: 'block' }, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              {getPageTitle()}
            </Typography>
          </Box>
        </Toolbar>
      </AppBar>
      
      <Box component="nav" sx={{ width: { md: drawerWidth }, flexShrink: { md: 0 } }}>
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{ display: { xs: 'block', md: 'none' }, '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth } }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{ display: { xs: 'none', md: 'block' }, '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth, borderRight: '1px solid', borderColor: 'divider' } }}
          open
        >
          {drawer}
        </Drawer>
      </Box>
      
      <Box component="main" sx={{ flexGrow: 1, p: { xs: 2, md: 4 }, mt: '64px', width: { xs: '100%', md: `calc(100% - ${drawerWidth}px)` } }}>
        <Outlet />
      </Box>
    </Box>
  );
};

export default AppLayout;
