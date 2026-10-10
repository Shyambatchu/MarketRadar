import { Box, Grid, Paper, Skeleton } from '@mui/material';

/**
 * Placeholder shaped like a typical page (header, filter bar, cards, table)
 * while a page's code loads, so a menu click never shows a blank area.
 */
const PageSkeleton = () => (
  <Box aria-busy="true" aria-label="Loading page">
    <Skeleton variant="text" width={260} height={48} />
    <Skeleton variant="text" width={420} height={24} sx={{ mb: 3, maxWidth: '100%' }} />
    <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
      <Skeleton variant="rounded" height={40} />
    </Paper>
    <Grid container spacing={2} sx={{ mb: 3 }}>
      {[0, 1, 2, 3].map((i) => (
        <Grid key={i} size={{ xs: 12, sm: 6, md: 3 }}>
          <Skeleton variant="rounded" height={96} />
        </Grid>
      ))}
    </Grid>
    {[0, 1, 2, 3, 4].map((i) => (
      <Skeleton key={i} variant="rounded" height={44} sx={{ mb: 1 }} />
    ))}
  </Box>
);

export default PageSkeleton;
