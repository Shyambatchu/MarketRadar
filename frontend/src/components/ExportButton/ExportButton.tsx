import { Button, Tooltip } from '@mui/material';
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';

interface ExportButtonProps {
  href: string;
  label?: string;
  disabled?: boolean;
}

/**
 * Downloads a CSV generated server-side from the same query the page shows,
 * so the file always matches the screen. A plain link: the browser handles
 * the download and no data passes through the page.
 */
const ExportButton: React.FC<ExportButtonProps> = ({ href, label = 'Export CSV', disabled }) => (
  <Tooltip title="Download as CSV (opens in Excel, Sheets or Numbers)">
    <span>
      <Button
        size="small" variant="outlined" component="a" href={disabled ? undefined : href}
        download disabled={disabled} startIcon={<FileDownloadOutlinedIcon />}
      >
        {label}
      </Button>
    </span>
  </Tooltip>
);

export default ExportButton;
