import { Box, Typography, Button, Paper } from '@mui/material';
import InboxOutlinedIcon from '@mui/icons-material/InboxOutlined';

interface EmptyStateProps {
  title: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
}

const EmptyState: React.FC<EmptyStateProps> = ({ 
  title, 
  description, 
  actionText, 
  onAction,
  icon = <InboxOutlinedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />
}) => {
  return (
    <Paper 
      elevation={0}
      sx={{ 
        p: 6, 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        justifyContent: 'center',
        textAlign: 'center',
        backgroundColor: 'background.default',
        border: '1px dashed',
        borderColor: 'divider',
        borderRadius: 2
      }}
    >
      <Box sx={{ mb: 2 }}>{icon}</Box>
      <Typography variant="h6" gutterBottom color="text.primary">
        {title}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3, maxWidth: 400 }}>
        {description}
      </Typography>
      {actionText && onAction && (
        <Button variant="contained" onClick={onAction}>
          {actionText}
        </Button>
      )}
    </Paper>
  );
};

export default EmptyState;
