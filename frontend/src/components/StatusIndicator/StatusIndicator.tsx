import { Box, Typography } from '@mui/material';
import CircleIcon from '@mui/icons-material/Circle';

interface StatusIndicatorProps {
  status: 'connected' | 'unavailable' | 'checking';
}

const StatusIndicator: React.FC<StatusIndicatorProps> = ({ status }) => {
  const getColor = () => {
    switch (status) {
      case 'connected': return 'success.main';
      case 'unavailable': return 'error.main';
      case 'checking': return 'text.secondary';
      default: return 'text.secondary';
    }
  };

  const getMessage = () => {
    switch (status) {
      case 'connected': return 'Backend Connected';
      case 'unavailable': return 'Backend Unavailable';
      case 'checking': return 'Checking connection...';
      default: return 'Unknown Status';
    }
  };

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <CircleIcon sx={{ fontSize: 10, color: getColor() }} />
      <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
        {getMessage()}
      </Typography>
    </Box>
  );
};

export default StatusIndicator;
