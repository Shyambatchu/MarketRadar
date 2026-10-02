import { Box, Typography, Breadcrumbs, Link } from '@mui/material';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  breadcrumbs?: { label: string; href?: string }[];
  action?: React.ReactNode;
}

const PageHeader: React.FC<PageHeaderProps> = ({ title, subtitle, breadcrumbs, action }) => {
  return (
    <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <Box>
        {breadcrumbs && breadcrumbs.length > 0 && (
          <Breadcrumbs separator={<NavigateNextIcon fontSize="small" />} aria-label="breadcrumb" sx={{ mb: 1 }}>
            {breadcrumbs.map((bc, idx) => {
              const isLast = idx === breadcrumbs.length - 1;
              return isLast || !bc.href ? (
                <Typography key={idx} color="text.primary" variant="body2" sx={{ fontWeight: 500 }}>
                  {bc.label}
                </Typography>
              ) : (
                <Link key={idx} underline="hover" color="text.secondary" href={bc.href} variant="body2">
                  {bc.label}
                </Link>
              );
            })}
          </Breadcrumbs>
        )}
        <Typography variant="h1" gutterBottom sx={{ fontSize: '1.875rem' }}>
          {title}
        </Typography>
        {subtitle && (
          <Typography variant="subtitle1" color="text.secondary">
            {subtitle}
          </Typography>
        )}
      </Box>
      {action && <Box>{action}</Box>}
    </Box>
  );
};

export default PageHeader;
